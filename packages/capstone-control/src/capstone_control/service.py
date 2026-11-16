"""Durable Control transitions; execution stays behind a public Agent port."""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json

from .contracts import (ContractError, identity, object_fields, positive_integer,
                        utc_deadline, validate_goal_request)


class Conflict(ValueError):
    """An operation identity or revision conflicts with stored state."""


class InvalidTransition(ValueError):
    """The requested action is not valid at this durable boundary."""


def fingerprint(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                             ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def public(goal):
    return deepcopy({key: value for key, value in goal.items() if not key.startswith('_')})


class ControlService:
    def __init__(self, store, *, now=None):
        self.store = store
        self.now = now or (lambda: datetime.now(timezone.utc))

    def create(self, workspace, request):
        from .contracts import text
        text(workspace, limit=128)
        request = validate_goal_request(request)
        goal_id = 'goal_' + fingerprint([workspace, request['operation_id']])[:32]
        digest = fingerprint(request)

        def create(current):
            if current is not None:
                old = current['_operations'][request['operation_id']]
                if old['digest'] != digest:
                    raise Conflict('operation identity has different content')
                return current, old['receipt']
            if utc_deadline(request['deadline_at']) <= self.now():
                raise InvalidTransition('deadline already expired')
            goal = {key: deepcopy(request[key]) for key in
                    ['objective', 'acceptance_criteria', 'max_delegations', 'deadline_at']}
            goal.update(schema='capstone-control-goal/1', workspace=workspace,
                        goal_id=goal_id, revision=1, objective_revision=1,
                        state='ready', reason=None, delegations_admitted=0,
                        acceptance=None, history=[], tasks=[])
            for task in request['tasks']:
                goal['tasks'].append({**task, 'revision': 1, 'state': 'pending',
                                      'generation': 0, 'delegation': None,
                                      'delivery': None, 'verification': None})
            receipt = public(goal)
            goal['_operations'] = {request['operation_id']: {'digest': digest, 'receipt': receipt}}
            return goal, receipt
        return self.store.transact(workspace, goal_id, create)

    def read(self, workspace, goal_id):
        return public(self.store.read(workspace, goal_id))

    def pending(self, workspace=None, limit=128, goal_id=None):
        goals = ([self.read(workspace, goal_id)] if goal_id is not None
                 else self.store.list(workspace, limit, active_only=True))
        return [{'goal_id': g['goal_id'], 'workspace': g['workspace'], 'task': deepcopy(t)}
                for g in goals
                for t in g['tasks'] if t['state'] in {'dispatching', 'running', 'waiting', 'resume_requested', 'revoke_requested'}][:limit]

    def delegation_request(self, workspace, goal_id, delegation_id):
        goal = self.read(workspace, goal_id)
        task = self._delegated_task(goal, delegation_id)
        return {**deepcopy(task['delegation']), 'objective': task['objective'],
                'delivery_requirements': deepcopy(task['delivery_requirements']),
                'required_products': deepcopy(task.get('required_products', [])),
                'mode': task['mode'], 'max_attempts': task['max_attempts'],
                'deadline_at': goal['deadline_at'],
                'context_products': [deepcopy(product) for previous in goal['tasks']
                    if previous['task_id'] in task['depends_on'] and previous['state'] == 'verified'
                    for product in previous['delivery']['products']]}

    def expire_pending(self, workspace, goal_id, delegation_id):
        """Revoke the exact operation: a lost admission acknowledgement may exist."""
        def change(goal):
            if goal is None:
                raise KeyError(goal_id)
            task = self._delegated_task(goal, delegation_id)
            if (task['state'] != 'dispatching' or task['delegation']['binding'] is not None
                    or self.now() < utc_deadline(goal['deadline_at'])):
                return goal, public(goal)
            task['state'] = 'revoke_requested'
            task['delegation']['requested_control'] = 'cancel'
            task['delegation']['control_revision'] += 1
            goal.update(state='pausing', reason='deadline_exhausted', revision=goal['revision'] + 1)
            return goal, public(goal)
        return self.store.transact(workspace, goal_id, change)

    @staticmethod
    def _delegated_task(goal, delegation_id):
        task = next((t for t in goal['tasks'] if t['delegation'] and
                     t['delegation']['delegation_id'] == delegation_id), None)
        if task is None:
            raise InvalidTransition('delegation is not current')
        return task

    def bind(self, workspace, goal_id, delegation_id, binding):
        object_fields(binding, {'thread_id', 'work_id'})
        for value in binding.values():
            identity(value)
        def change(goal):
            if goal is None:
                raise KeyError(goal_id)
            task = self._delegated_task(goal, delegation_id)
            old = task['delegation']['binding']
            if old is not None:
                if old != binding:
                    raise Conflict('execution binding mismatch')
                return goal, public(goal)
            if task['state'] not in {'dispatching', 'revoke_requested'}:
                raise InvalidTransition('delegation is not awaiting binding')
            task['delegation']['binding'] = deepcopy(binding)
            if task['state'] == 'dispatching':
                task['state'] = 'running'
            goal['revision'] += 1
            return goal, public(goal)
        return self.store.transact(workspace, goal_id, change)

    def observe(self, workspace, goal_id, delegation_id, observation):
        from .contracts import text
        object_fields(observation, {'sequence', 'state', 'summary', 'delivery'})
        if type(observation['sequence']) is not int or observation['sequence'] < 0:
            raise ContractError('nonnegative observation sequence required')
        if observation['state'] not in {'running', 'waiting', 'paused', 'completed', 'failed', 'cancelled', 'unknown'}:
            raise ContractError('invalid observed state')
        if observation['summary'] != '':
            text(observation['summary'], limit=4096)
        def change(goal):
            if goal is None:
                raise KeyError(goal_id)
            task = self._delegated_task(goal, delegation_id)
            if task['delegation']['binding'] is None and not (
                    task['state'] == 'revoke_requested' and
                    observation['state'] in {'paused', 'cancelled'}):
                raise InvalidTransition('unbound delegation cannot publish observations')
            old = task.get('observation')
            if old is not None and observation['sequence'] <= old['sequence']:
                if observation['sequence'] == old['sequence'] and observation != old:
                    raise Conflict('observation sequence has different content')
                return goal, public(goal)
            if task['state'] not in {'running', 'waiting', 'resume_requested', 'revoke_requested'}:
                return goal, public(goal)
            task['observation'] = deepcopy(observation)
            state = observation['state']
            if task['state'] == 'revoke_requested':
                # Terminal execution is an acknowledgement, never permission to
                # accept a late completion for the revoked delegation.
                if state in {'paused', 'cancelled', 'completed', 'failed'}:
                    kind = task['delegation']['requested_control']
                    task['state'] = 'cancelled' if kind == 'cancel' else 'paused'
                    if not any(t['state'] == 'revoke_requested' for t in goal['tasks']):
                        if goal['state'] == 'revising':
                            self._activate_revision(goal)
                        elif goal['reason'] == 'deadline_exhausted':
                            goal['state'] = 'paused'
                        else:
                            goal['state'] = 'cancelled' if kind == 'cancel' else 'paused'
            elif state == 'completed':
                self._settle_delivery(task, observation['delivery'])
            elif state in {'failed', 'unknown', 'cancelled'}:
                task['state'] = 'failed' if state == 'failed' else 'blocked'
                goal.update(state='paused', reason='delegation_' + state)
            elif state in {'waiting', 'paused'}:
                task['state'] = 'waiting'
                task['delegation']['requested_control'] = None
                goal.update(state='waiting', reason='agent_' + state)
            elif state == 'running':
                task['state'] = 'running'
                task['delegation']['requested_control'] = None
                goal.update(state='running', reason=None)
            goal['revision'] += 1
            return goal, public(goal)
        return self.store.transact(workspace, goal_id, change)

    @staticmethod
    def _settle_delivery(task, delivery):
        object_fields(delivery, {'answer_ref', 'products', 'status'})
        identity(delivery['answer_ref'])
        if delivery['status'] != 'completed' or not isinstance(delivery['products'], list):
            raise ContractError('completed persisted delivery required')
        content = {**deepcopy(delivery), 'revision': 1}
        if task['delivery'] is not None and task['delivery'] != content:
            raise Conflict('delivery changed after persistence')
        task.update(state='delivered', delivery=content)

    def command(self, workspace, command, *, actor='application:trusted'):
        object_fields(command, {'schema', 'operation_id', 'goal_id', 'expected_revision',
                                'kind', 'payload'})
        if command['schema'] != 'capstone-control-command/1':
            raise ContractError('unsupported Control command')
        identity(command['operation_id'])
        identity(command['goal_id'])
        positive_integer(command['expected_revision'])
        if not isinstance(command['kind'], str):
            raise ContractError('Control command kind must be text')
        if not isinstance(command['payload'], dict):
            raise ContractError('command payload must be an object')
        digest = fingerprint([command, actor])

        def change(goal):
            if goal is None:
                raise KeyError(command['goal_id'])
            old = goal['_operations'].get(command['operation_id'])
            if old is not None:
                if old['digest'] != digest:
                    raise Conflict('operation identity has different content')
                return goal, old['receipt']
            if goal['revision'] != command['expected_revision']:
                raise Conflict('stale Goal revision')
            self._apply(goal, command['kind'], command['payload'], actor=actor)
            goal['revision'] += 1
            receipt = {'schema': 'capstone-control-receipt/1',
                       'operation_id': command['operation_id'], 'goal': public(goal)}
            goal['_operations'][command['operation_id']] = {'digest': digest, 'receipt': receipt}
            return goal, receipt
        return self.store.transact(workspace, command['goal_id'], change)

    def _apply(self, goal, kind, payload, *, actor):
        if kind in {'pause', 'cancel', 'resume', 'delegate_next'}:
            object_fields(payload, set())
        if kind == 'delegate_next':
            self._delegate(goal)
        elif kind in {'pause', 'cancel'}:
            if goal['state'] in {'cancelled', 'accepted'}:
                raise InvalidTransition('Goal is terminal')
            active = [t for t in goal['tasks'] if t['state'] in {'dispatching', 'running', 'waiting', 'resume_requested', 'revoke_requested'}]
            goal.pop('_pending_tasks', None)
            for task in active:
                task['state'] = 'revoke_requested'
                task['delegation']['requested_control'] = kind
                task['delegation']['control_revision'] += 1
            goal['state'] = ('cancelling' if kind == 'cancel' else 'pausing') if active else (
                'cancelled' if kind == 'cancel' else 'paused')
            goal['reason'] = 'user_' + kind
        elif kind == 'resume':
            if goal['state'] not in {'paused', 'waiting'}:
                raise InvalidTransition('only a paused or waiting Goal can resume')
            if goal['reason'] in {'delegation_unknown', 'delegation_failed', 'delegation_cancelled'}:
                raise InvalidTransition('uncertain or failed execution requires explicit reconciliation')
            for task in goal['tasks']:
                if task['state'] in {'paused', 'waiting'}:
                    d = task['delegation']
                    if task['mode'] == 'goal' and d['binding'] is not None:
                        task['state'] = 'resume_requested'
                        d['requested_control'] = 'resume'
                        d['control_revision'] += 1
                    else:
                        task.setdefault('delegation_history', []).append(deepcopy(d))
                        task.update(state='pending', delegation=None)
            goal.update(state='ready', reason=None)
        elif kind == 'revise':
            self._revise(goal, payload)
        elif kind == 'verify_task':
            self._verify(goal, payload)
            next(t for t in goal['tasks'] if t['task_id'] == payload['task_id'])['verification']['actor'] = actor
        elif kind == 'accept':
            object_fields(payload, {'products'})
            if goal['state'] != 'delivered' or not all(t['state'] == 'verified' for t in goal['tasks']):
                raise InvalidTransition('all Tasks must be verified before acceptance')
            products = [p for t in goal['tasks'] for p in t['delivery']['products']]
            if fingerprint(payload['products']) != fingerprint(products):
                raise Conflict('acceptance must name exact delivered product versions')
            goal.update(state='accepted', acceptance={'goal_revision': goal['revision'],
                                                      'objective_revision': goal['objective_revision'], 'actor': actor,
                                                      'products': deepcopy(products)})
        else:
            raise ContractError('unsupported Control command kind')

    def _delegate(self, goal):
        if goal['state'] not in {'ready', 'running'}:
            raise InvalidTransition('Goal is not dispatchable')
        if any(t['state'] in {'dispatching', 'running', 'waiting', 'resume_requested', 'revoke_requested'} for t in goal['tasks']):
            raise InvalidTransition('an active delegation already owns execution')
        if self.now() >= utc_deadline(goal['deadline_at']):
            goal.update(state='paused', reason='deadline_exhausted')
            return
        if goal['delegations_admitted'] >= goal['max_delegations']:
            goal.update(state='paused', reason='delegation_budget_exhausted')
            return
        completed = {t['task_id'] for t in goal['tasks'] if t['state'] == 'verified'}
        task = next((t for t in goal['tasks'] if t['state'] == 'pending'
                     and set(t['depends_on']) <= completed), None)
        if task is None:
            raise InvalidTransition('no dependency-ready Task')
        task['generation'] += 1
        delegation_id = 'delegation_' + fingerprint([goal['goal_id'], goal['objective_revision'], task['task_id'],
                                                    task['revision'], task['generation']])[:32]
        task['delegation'] = dict(schema='capstone-agent-delegation/1',
            delegation_id=delegation_id, operation_id=delegation_id,
            goal_id=goal['goal_id'], goal_revision=goal['objective_revision'],
            task_id=task['task_id'], task_revision=task['revision'],
            generation=task['generation'], agent_id=task['agent_id'],
            binding=None, requested_control=None, control_revision=0)
        task['state'] = 'dispatching'
        goal['delegations_admitted'] += 1
        goal.update(state='running', reason=None)

    def _revise(self, goal, payload):
        object_fields(payload, {'objective', 'acceptance_criteria', 'tasks'})
        if goal['state'] in {'accepted', 'cancelled', 'cancelling', 'revising'}:
            raise InvalidTransition('Goal cannot revise from this state')
        if goal['reason'] == 'delegation_unknown':
            raise InvalidTransition('unknown execution outcome requires explicit reconciliation')
        checked = validate_goal_request(dict(schema='capstone-control-goal-create/1',
            operation_id='revision', max_delegations=goal['max_delegations'],
            deadline_at=goal['deadline_at'], **payload))
        goal['history'].append({key: deepcopy(goal[key]) for key in
            ['objective_revision', 'objective', 'acceptance_criteria', 'tasks', 'acceptance']})
        goal['objective_revision'] += 1
        goal['objective'] = checked['objective']
        goal['acceptance_criteria'] = checked['acceptance_criteria']
        goal['_pending_tasks'] = checked['tasks']
        goal['acceptance'] = None
        active = [t for t in goal['tasks'] if t['state'] in
                  {'dispatching', 'running', 'waiting', 'paused', 'resume_requested', 'revoke_requested'}
                  and t['delegation'] is not None]
        for task in active:
            task['state'] = 'revoke_requested'
            task['delegation']['requested_control'] = 'cancel'
            task['delegation']['control_revision'] += 1
        goal.update(state='revising', reason='objective_revised')
        if not active:
            self._activate_revision(goal)

    @staticmethod
    def _activate_revision(goal):
        previous = {t['task_id']: t['revision'] for t in goal['tasks']}
        goal['tasks'] = [{**task, 'revision': previous.get(task['task_id'], 0) + 1,
                          'state': 'pending', 'generation': 0, 'delegation': None,
                          'delivery': None, 'verification': None}
                         for task in goal.pop('_pending_tasks')]
        goal.update(state='ready', reason=None)

    def _verify(self, goal, payload):
        object_fields(payload, {'task_id', 'delivery_revision', 'checks'})
        identity(payload['task_id'])
        positive_integer(payload['delivery_revision'])
        task = next((t for t in goal['tasks'] if t['task_id'] == payload['task_id']), None)
        if task is None or task['state'] != 'delivered':
            raise InvalidTransition('Task has no current delivery')
        if payload['delivery_revision'] != task['delivery']['revision']:
            raise Conflict('stale delivery revision')
        checks = payload['checks']
        if not isinstance(checks, list) or not checks:
            raise ContractError('verification checks required')
        from .contracts import text
        for check in checks:
            object_fields(check, {'name', 'passed'})
            text(check['name'])
            if check['passed'] is not True:
                raise InvalidTransition('all verification checks must pass')
        task.update(state='verified', verification=deepcopy(payload))
        if all(t['state'] == 'verified' for t in goal['tasks']):
            goal['state'] = 'delivered'

    def deliver(self, workspace, goal_id, delegation_id, binding, delivery):
        """Trusted adapter call, never an unqualified model proposal."""
        object_fields(binding, {'thread_id', 'work_id'})
        for value in binding.values():
            identity(value)
        object_fields(delivery, {'answer_ref', 'products', 'status'})
        identity(delivery['answer_ref'])
        if delivery['status'] != 'completed' or not isinstance(delivery['products'], list):
            raise ContractError('completed persisted delivery required')

        def change(goal):
            if goal is None:
                raise KeyError(goal_id)
            task = next((t for t in goal['tasks'] if t['delegation'] and
                         t['delegation']['delegation_id'] == delegation_id), None)
            if task is None or task['state'] not in {'dispatching', 'running', 'delivered'}:
                raise InvalidTransition('delegation is no longer eligible to deliver')
            d = task['delegation']
            if d['goal_revision'] != goal['objective_revision'] or d['task_revision'] != task['revision']:
                raise Conflict('stale delegation version')
            if d['binding'] is not None and d['binding'] != binding:
                raise Conflict('execution binding mismatch')
            content = {**deepcopy(delivery), 'revision': 1}
            if task['delivery'] is not None:
                if task['delivery'] != content:
                    raise Conflict('delivery changed after persistence')
                return goal, public(goal)
            d['binding'] = deepcopy(binding)
            task.update(state='delivered', delivery=content)
            goal['revision'] += 1
            return goal, public(goal)
        return self.store.transact(workspace, goal_id, change)
