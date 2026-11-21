"""Durable Control transitions; execution stays behind a public Agent port."""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json

from .contracts import (ContractError, identity, object_fields, positive_integer, validate_delivery,
                        utc_deadline, validate_goal_request)


class Conflict(ValueError):
    """An operation identity or revision conflicts with stored state."""


class InvalidTransition(ValueError):
    """The requested action is not valid at this durable boundary."""


def fingerprint(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                             ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def public(goal):
    result = deepcopy({key: value for key, value in goal.items() if not key.startswith('_')})
    if '_mission' in goal:
        metadata = goal['_mission']
        result.update(application_kind='mission', mission_id=goal['goal_id'],
            origin=deepcopy(metadata['origin']), plan_revision=metadata.get('plan_revision', 1),
            plan_complete=bool(goal['tasks'] and goal['acceptance_criteria']))
        conclusion=metadata.get('plan_conclusion')
        from .mission import conclusion_satisfied
        satisfied = conclusion_satisfied(goal)
        conclusion_status = None if not conclusion else ('legacy_unverified' if 'criteria_verdicts' not in conclusion
            else 'stale' if conclusion.get('plan_revision') != metadata.get('plan_revision',1) else 'satisfied' if satisfied else 'incomplete')
        result.update(plan_concluded=satisfied, plan_conclusion_status=conclusion_status,
                      plan_conclusion=deepcopy(conclusion))
        review=metadata.get('organizer',{})
        current=next((r for r in review.get('records',[]) if r['intent']['review_id']==review.get('current_review_id')),None)
        result['organizer']=dict(max_reviews=review.get('max_reviews',8),reviews_admitted=review.get('reviews_admitted',0),
            state=current['state'] if current else 'idle',reason=(current or {}).get('reason'),
            suspended=review.get('suspended',False))
        if review.get('disposition') and (current is None or current['state'] not in {'pending','reserved','running'}):
            result['organizer'].update(state='waiting',reason=review['disposition']['reason'])
        from .mission import task_state
        result['task_state'] = task_state(result)
    return result


class ControlService:
    def __init__(self, store, *, now=None, admit_mission_reference=None, mission_execution_adapter=False,
                 admit_mission_task=None):
        self.store = store
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.admit_mission_reference = admit_mission_reference
        self.mission_execution_adapter = mission_execution_adapter
        self.admit_mission_task = admit_mission_task

    def create_mission(self, workspace, request):
        from .mission import create
        return create(self, workspace, request)

    def read_mission(self, workspace, mission_id):
        from .mission import projection
        return projection(self, self.store.read(workspace, mission_id))

    def command_mission(self, workspace, command, *, actor='application:trusted',
                        validate_task_equipment=False, excluded_skills=(), model_turn=None):
        from .mission import command as apply
        return apply(self, workspace, command, actor, validate_task_equipment=validate_task_equipment,
                     excluded_skills=excluded_skills, model_turn=model_turn)

    def pending_mission_reviews(self, workspace=None, limit=32):
        from .mission_reviews import pending
        return pending(self,workspace,limit)

    def reserve_mission_review(self,workspace,mission_id,review_id):
        from .mission_reviews import reserve
        return reserve(self,workspace,mission_id,review_id)

    def read_mission_review(self,workspace,mission_id,review_id):
        from .mission_reviews import read
        return read(self,workspace,mission_id,review_id)

    def acknowledge_mission_review(self,workspace,mission_id,review_id,binding):
        from .mission_reviews import acknowledge
        return acknowledge(self,workspace,mission_id,review_id,binding)

    def finish_mission_review(self,workspace,mission_id,review_id,*,attempt_id,phase,recovered=False):
        from .mission_reviews import finish
        return finish(self,workspace,mission_id,review_id,attempt_id,phase,recovered=recovered)

    def block_mission_review(self,workspace,mission_id,review_id,reason):
        from .mission_reviews import block
        return block(self,workspace,mission_id,review_id,reason)

    def release_mission_review(self,workspace,mission_id,review_id,reason='origin_paused_before_admission'):
        from .mission_reviews import release
        return release(self,workspace,mission_id,review_id,reason)

    def _event(self, kind, **references):
        return dict(kind=kind, recorded_at=self.now().isoformat(), **references)

    def read_events(self, workspace, goal_id, *, after=0, limit=50, through=None):
        return self.store.read_events(workspace, goal_id, after=after, limit=limit, through=through)

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
        return self.store.transact(workspace, goal_id, create,
            event=self._event('goal.created', operation_id=request['operation_id']))

    def read(self, workspace, goal_id):
        return public(self.store.read(workspace, goal_id))

    def _awaits_recovered_delivery(self, goal, task):
        observation = task.get('observation') or {}
        return ('_mission' in goal and goal['state'] in {'waiting_review', 'running', 'waiting'}
                and self.now() < utc_deadline(goal['deadline_at'])
                and task['state'] == 'blocked' and task['mode'] == 'single'
                and observation.get('state') == 'unknown'
                and task['delegation']['requested_control'] is None)

    def pending(self, workspace=None, limit=128, goal_id=None):
        goals = ([self.store.read(workspace, goal_id)] if goal_id is not None
                 else self.store.list(workspace, limit, active_only=True))
        return [{'goal_id': g['goal_id'], 'workspace': g['workspace'], 'task': deepcopy(t)}
                for g in goals
                for t in g['tasks'] if not t.get('origin_attempt_id') and (
                    t['state'] in {'dispatching', 'running', 'waiting', 'resume_requested', 'revoke_requested'}
                    or self._awaits_recovered_delivery(g, t))][:limit]

    def delegation_request(self, workspace, goal_id, delegation_id):
        goal = self.read(workspace, goal_id)
        task = self._delegated_task(goal, delegation_id)
        result = {**deepcopy(task['delegation']), 'objective': task['objective'],
                'delivery_requirements': deepcopy(task['delivery_requirements']),
                'required_products': deepcopy(task.get('required_products', [])),
                'mode': task['mode'], 'max_attempts': task['max_attempts'],
                'deadline_at': goal['deadline_at'],
                'context_products': [deepcopy(product) for previous in goal['tasks']
                    if previous['task_id'] in task['depends_on'] and previous['state'] == 'verified'
                    for product in previous['delivery']['products']]}
        if '_mission' in self.store.read(workspace, goal_id):
            metadata = self.store.read(workspace, goal_id)['_mission']
            result.update(schema='capstone-agent-delegation/2', equipment=deepcopy(task.get('equipment', [])),
                restrictions=deepcopy(task.get('restrictions', [])), mission_origin=deepcopy(metadata['origin']))
            for kind in ('authority', 'gateway'):
                field = kind + '_source'
                sources = [deepcopy(previous['delivery'][field]) for previous in goal['tasks']
                    if previous['task_id'] in task['depends_on'] and previous['state'] == 'verified'
                    and field in previous['delivery']]
                if sources:
                    result['context_' + kind + '_sources'] = sources
        if task.get('required_reference_sources'):
            result['required_reference_sources'] = deepcopy(task['required_reference_sources'])
        return result

    def expire_pending(self, workspace, goal_id, delegation_id):
        """Revoke the exact operation: a lost admission acknowledgement may exist."""
        def change(goal):
            if goal is None:
                raise KeyError(goal_id)
            task = self._delegated_task(goal, delegation_id)
            if (task['state'] not in {'dispatching', 'running', 'waiting', 'resume_requested'}
                    or self.now() < utc_deadline(goal['deadline_at'])):
                return goal, public(goal)
            task['state'] = 'revoke_requested'
            task['delegation']['requested_control'] = 'cancel'
            task['delegation']['control_revision'] += 1
            goal.update(state='pausing', reason='deadline_exhausted', revision=goal['revision'] + 1)
            return goal, public(goal)
        return self.store.transact(workspace, goal_id, change,
            event=self._event('deadline.expired', delegation_id=delegation_id))

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
        return self.store.transact(workspace, goal_id, change,
            event=self._event('delegation.bound', delegation_id=delegation_id))

    def observe(self, workspace, goal_id, delegation_id, observation, *, recovered=False):
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
            if (old is not None and task.get('delegation_history')
                    and task['state'] in {'running', 'waiting', 'resume_requested'}
                    and old['state'] in {'paused', 'cancelled', 'completed', 'failed'}
                    and task['delegation'].get('requested_control') is None):
                # Existing resumed records can still carry the prior stop
                # acknowledgement. Its sequence belongs to the old child.
                old = None
            if old is not None and observation['sequence'] <= old['sequence']:
                if observation['sequence'] == old['sequence'] and observation != old:
                    raise Conflict('observation sequence has different content')
                return goal, public(goal)
            accepts_recovery = (recovered and observation['state'] == 'completed'
                                and self._awaits_recovered_delivery(goal, task))
            if task['state'] not in {'running', 'waiting', 'resume_requested', 'revoke_requested'} and not accepts_recovery:
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
                self._settle_delivery(goal, task, observation['delivery'])
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
            if state in {'completed','failed','unknown','cancelled','paused'} and '_mission' in goal:
                from .mission_reviews import queue_boundary
                queue_boundary(goal)
            goal['revision'] += 1
            return goal, public(goal)
        return self.store.transact(workspace, goal_id, change,
            event=self._event('execution.observed', delegation_id=delegation_id,
                              observation_sequence=observation['sequence'], observed_state=observation['state']))

    @staticmethod
    def _settle_delivery(goal, task, delivery):
        validate_delivery(delivery, task['delegation']['binding'])
        content = {**deepcopy(delivery), 'revision': 1}
        if task['delivery'] is not None and task['delivery'] != content:
            raise Conflict('delivery changed after persistence')
        failure = None
        if set(task.get('required_reference_sources', ())) - content.keys():
            failure = 'required_reference_receipt_missing'
        elif '_mission' in goal and content.get('outcome') == 'partial':
            failure = 'child_goal_partial_delivery'
        elif '_mission' in goal:
            names = {product.get('file_name') for product in content['products'] if isinstance(product, dict)}
            if set(task.get('required_products', ())) - names:
                failure = 'required_product_missing'
        task.update(state='failed' if failure else 'delivered', delivery=content)
        if failure:
            task['failure_reason'] = failure
            goal.update(state='waiting', reason='delegation_failed')

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
        return self.store.transact(workspace, command['goal_id'], change,
            event=self._event('command.' + command['kind'], operation_id=command['operation_id']))

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
            if '_mission' in goal:
                if not goal['_mission'].get('activated'):
                    raise InvalidTransition('Mission requires explicit readiness before execution')
                from .mission import dispatch_ready
                dispatch_ready(self, goal)
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
            self._verify(goal, payload, actor=actor)
        elif kind == 'defer_verification':
            object_fields(payload,{'task_id','reason'})
            if payload['reason']!='delivery_verification_unavailable' or not any(t['task_id']==payload['task_id'] and t['state']=='delivered' for t in goal['tasks']):
                raise InvalidTransition('no saved Task delivery awaits verification')
            goal.update(state='waiting_review' if '_mission' in goal else 'waiting',reason=payload['reason'])
        elif kind == 'accept':
            object_fields(payload, {'products'})
            if '_mission' in goal:
                from .mission import conclusion_satisfied
                if not conclusion_satisfied(goal):
                    raise InvalidTransition('Mission acceptance requires current satisfied criteria verdicts with saved evidence')
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
        if '_mission' in goal:
            if not goal['_mission'].get('activated'):
                raise InvalidTransition('Mission requires explicit readiness before execution')
            from .mission import dispatch_ready
            dispatch_ready(self, goal)
            if (any(task.get('equipment') or task.get('restrictions') for task in goal['tasks'])
                    and not self.mission_execution_adapter):
                raise InvalidTransition('Mission equipment needs a registered Agent execution adapter before dispatch')
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
        task.pop('observation', None)
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
        if '_mission' in goal:
            raise InvalidTransition('Mission plans use incremental Mission commands')
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

    def _verify(self, goal, payload, *, actor='application:trusted'):
        object_fields(payload, {'task_id', 'delivery_revision', 'checks'})
        identity(payload['task_id'])
        positive_integer(payload['delivery_revision'])
        task = next((t for t in goal['tasks'] if t['task_id'] == payload['task_id']), None)
        if task is None or task['state'] != 'delivered':
            raise InvalidTransition('Task has no current delivery')
        if payload['delivery_revision'] != task['delivery']['revision']:
            raise Conflict('stale delivery revision')
        if any(source not in task['delivery'] for source in task.get('required_reference_sources', ())):
            raise InvalidTransition('Task delivery lacks a required reference receipt')
        checks = payload['checks']
        if not isinstance(checks, list) or not checks:
            raise ContractError('verification checks required')
        from .contracts import text
        for check in checks:
            object_fields(check, {'name', 'passed'})
            text(check['name'])
            if check['passed'] is not True:
                raise InvalidTransition('all verification checks must pass')
        task.update(state='verified', verification={**deepcopy(payload),'actor':actor})
        if all(t['state'] == 'verified' for t in goal['tasks']):
            goal['state'] = 'waiting_review' if '_mission' in goal else 'delivered'
        if '_mission' in goal:
            from .mission_reviews import queue_boundary
            queue_boundary(goal)

    def deliver(self, workspace, goal_id, delegation_id, binding, delivery):
        """Trusted adapter call, never an unqualified model proposal."""
        object_fields(binding, {'thread_id', 'work_id'})
        for value in binding.values():
            identity(value)
        validate_delivery(delivery, binding)

        def change(goal):
            if goal is None:
                raise KeyError(goal_id)
            task = next((t for t in goal['tasks'] if t['delegation'] and
                         t['delegation']['delegation_id'] == delegation_id), None)
            if task is None or (task['state'] not in {'dispatching', 'running', 'delivered'}
                                and not (task['state'] == 'failed' and task['delivery'] is not None)):
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
            self._settle_delivery(goal, task, delivery)
            if '_mission' in goal:
                from .mission_reviews import queue_boundary
                queue_boundary(goal)
            goal['revision'] += 1
            return goal, public(goal)
        return self.store.transact(workspace, goal_id, change,
            event=self._event('delivery.recorded', delegation_id=delegation_id))
