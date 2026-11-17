"""Progressive Mission planning over the existing Control aggregate identity.

Equipment references describe requested registered resources. They do not grant
execution access. The application must admit them at readiness and dispatch.
"""
from copy import deepcopy
from datetime import timedelta

from .contracts import (ContractError, identity, object_fields, positive_integer,
                        text, text_list, utc_deadline, validate_goal_request)
from .service import Conflict, InvalidTransition, fingerprint, public


TASK_FIELDS = {'task_id', 'objective', 'delivery_requirements', 'depends_on',
               'agent_id', 'mode', 'max_attempts', 'required_products'}


def references(values):
    if not isinstance(values, list) or len(values) > 64:
        raise ContractError('bounded registered equipment references required')
    keys = []
    for ref in values:
        object_fields(ref, {'schema', 'kind', 'id', 'revision'})
        if (ref['schema'] != 'capstone-mission-equipment-reference/1'
                or ref['kind'] not in {'capability', 'resource_profile', 'skill', 'resource'}):
            raise ContractError('unsupported registered equipment reference')
        identity(ref['id'])
        text(ref['revision'], limit=256)
        keys.append(fingerprint(ref))
    if len(set(keys)) != len(keys):
        raise ContractError('duplicate equipment reference')
    return deepcopy(values)


def checked_tasks(tasks, goal):
    if not isinstance(tasks, list) or len(tasks) > 64:
        raise ContractError('at most64 Tasks required')
    plain = []
    for task in tasks:
        if not isinstance(task, dict) or set(task) - TASK_FIELDS - {'equipment', 'restrictions'}:
            raise ContractError('unsupported Mission Task fields')
        selected, denied = references(task.get('equipment', [])), references(task.get('restrictions', []))
        if {fingerprint(ref) for ref in selected} & {fingerprint(ref) for ref in denied}:
            raise ContractError('restricted equipment cannot be selected')
        plain.append({key: value for key, value in task.items() if key in TASK_FIELDS})
    if plain:
        validate_goal_request(dict(schema='capstone-control-goal-create/1', operation_id='plan',
            objective=goal['objective'], acceptance_criteria=['Planning validation'],
            max_delegations=goal['max_delegations'], deadline_at=goal['deadline_at'], tasks=plain))
    return deepcopy(tasks)


def dispatch_ready(service, goal):
    if not goal['tasks'] or not goal['acceptance_criteria']:
        raise InvalidTransition('Mission needs Tasks and acceptance criteria before readiness')
    for task in goal['tasks']:
        for ref in task.get('equipment', []) + task.get('restrictions', []):
            admit = service.admit_mission_reference
            if admit is None or admit(goal['workspace'], deepcopy(goal['_mission']['origin']), deepcopy(ref)) is not True:
                raise InvalidTransition('Mission equipment reference is not admitted by the application')


def projection(service, goal):
    result = public(goal)
    result.update(schema='capstone-control-mission/1', mission_id=goal['goal_id'])
    metadata = goal.get('_mission', {})
    result.update(origin=deepcopy(metadata.get('origin')), plan_revision=metadata.get('plan_revision', 1))
    # Readiness here is structural. It cannot assert live registry availability.
    result['plan_complete'] = bool(goal['tasks'] and goal['acceptance_criteria'])
    return result


def create(service, workspace, request):
    required = {'schema', 'operation_id', 'objective', 'origin'}
    optional = {'acceptance_criteria', 'max_delegations', 'deadline_at'}
    if not isinstance(request, dict) or not required <= request.keys() or set(request) - required - optional:
        raise ContractError('invalid Mission creation fields')
    if request['schema'] != 'capstone-control-mission-create/1':
        raise ContractError('unsupported Mission creation schema')
    text(workspace, limit=128)
    identity(request['operation_id'])
    text(request['objective'])
    origin = request['origin']
    if not isinstance(origin, dict) or 'thread_id' not in origin or set(origin) - {'thread_id', 'work_id'}:
        raise ContractError('Mission origin must name its Thread and optional Work')
    for value in origin.values():
        identity(value)
    criteria = request.get('acceptance_criteria', [])
    if criteria:
        text_list(criteria)
    elif not isinstance(criteria, list):
        raise ContractError('acceptance criteria must be a list')
    budget = positive_integer(request.get('max_delegations', 8))
    explicit_deadline = request.get('deadline_at')
    if explicit_deadline is not None:
        utc_deadline(explicit_deadline)
    goal_id = 'goal_' + fingerprint([workspace, request['operation_id']])[:32]
    digest = fingerprint(request)

    def change(current):
        if current is not None:
            old = current['_operations'].get(request['operation_id'])
            if old is None or old['digest'] != digest:
                raise Conflict('operation identity has different content')
            return current, old['receipt']
        deadline = explicit_deadline or (service.now() + timedelta(days=1)).isoformat()
        if utc_deadline(deadline) <= service.now():
            raise InvalidTransition('Mission deadline already expired')
        goal = dict(schema='capstone-control-goal/1', workspace=workspace, goal_id=goal_id,
            objective=request['objective'], acceptance_criteria=deepcopy(criteria), max_delegations=budget,
            deadline_at=deadline, revision=1, objective_revision=1, state='planning', reason=None,
            delegations_admitted=0, acceptance=None, history=[], tasks=[],
            _mission={'origin': deepcopy(origin), 'plan_revision': 1, 'activated': False})
        receipt = projection(service, goal)
        goal['_operations'] = {request['operation_id']: {'digest': digest, 'receipt': receipt}}
        return goal, receipt
    return service.store.transact(workspace, goal_id, change,
        event=service._event('mission.created', operation_id=request['operation_id']))


def update_tasks(goal, proposed):
    for spec in proposed:
        if set(spec) - TASK_FIELDS - {'equipment', 'restrictions'}:
            raise ContractError('unsupported Mission Task fields')
    changes = {task['task_id']: task for task in proposed}
    if len(changes) != len(proposed):
        raise ContractError('duplicate Task identity')
    combined = []
    for previous in goal['tasks']:
        spec = changes.pop(previous['task_id'], None)
        if spec is None:
            combined.append(deepcopy(previous))
            continue
        if previous['state'] != 'pending' or previous['delegation'] is not None:
            raise InvalidTransition('active or completed Task cannot be replaced by a planning command')
        denied = {fingerprint(ref) for ref in previous.get('restrictions', [])}
        if not denied <= {fingerprint(ref) for ref in spec.get('restrictions', [])}:
            raise InvalidTransition('planning cannot relax saved Task restrictions')
        combined.append({**deepcopy(spec), 'revision': previous['revision'] + 1, 'state': 'pending',
                         'generation': previous['generation'], 'delegation': None, 'delivery': None, 'verification': None})
    for spec in changes.values():
        combined.append({**deepcopy(spec), 'revision': 1, 'state': 'pending',
                         'generation': 0, 'delegation': None, 'delivery': None, 'verification': None})
    # Revalidate the complete dependency order, including retained Tasks.
    plain = [{key: value for key, value in item.items() if key in TASK_FIELDS | {'equipment', 'restrictions'}} for item in combined]
    checked_tasks(plain, goal)
    goal['tasks'] = combined


def command(service, workspace, document, actor):
    object_fields(document, {'schema', 'operation_id', 'mission_id', 'expected_revision', 'kind', 'payload'})
    if document['schema'] != 'capstone-control-mission-command/1':
        raise ContractError('unsupported Mission command schema')
    identity(document['operation_id'])
    identity(document['mission_id'])
    positive_integer(document['expected_revision'])
    kind, payload = document['kind'], document['payload']
    if not isinstance(kind, str) or not isinstance(payload, dict):
        raise ContractError('invalid Mission command')
    digest = fingerprint([document, actor])

    def change(goal):
        if goal is None:
            raise KeyError(document['mission_id'])
        old = goal['_operations'].get(document['operation_id'])
        if old is not None:
            if old['digest'] != digest:
                raise Conflict('operation identity has different content')
            return goal, old['receipt']
        if goal['revision'] != document['expected_revision']:
            raise Conflict('stale Mission revision')
        if kind in {'prepare_task', 'update_plan', 'ready'}:
            if goal['state'] not in {'planning', 'ready', 'running', 'paused', 'waiting'}:
                raise InvalidTransition('Mission cannot plan from this state')
            if '_mission' not in goal:
                raise InvalidTransition('legacy Goal needs explicit Mission origin association before planning')
            if kind == 'ready':
                object_fields(payload, set())
                if goal['state'] != 'planning' and not (goal['state'] == 'paused' and not goal['_mission'].get('activated')):
                    raise InvalidTransition('only a planning Mission can become ready')
                dispatch_ready(service, goal)
                goal['_mission']['activated'] = True
                goal.update(state='ready', reason=None)
            else:
                if kind == 'prepare_task':
                    object_fields(payload, {'task'})
                    proposed = [payload['task']]
                else:
                    object_fields(payload, {'acceptance_criteria', 'tasks'})
                    text_list(payload['acceptance_criteria'])
                    goal['acceptance_criteria'] = deepcopy(payload['acceptance_criteria'])
                    proposed = payload['tasks']
                # Validate each proposal against the complete merged order below.
                if not isinstance(proposed, list) or len(proposed) > 64:
                    raise ContractError('bounded Mission Task plan required')
                for spec in proposed:
                    if not isinstance(spec, dict) or not isinstance(spec.get('task_id'), str):
                        raise ContractError('Mission Task identity required')
                update_tasks(goal, proposed)
                goal['_mission']['plan_revision'] += 1
        elif kind in {'pause', 'cancel', 'resume', 'delegate_next'}:
            if kind == 'resume' and '_mission' in goal:
                dispatch_ready(service, goal)
            service._apply(goal, kind, payload, actor=actor)
        else:
            raise ContractError('unsupported Mission command kind')
        goal['revision'] += 1
        receipt = dict(schema='capstone-control-mission-receipt/1',operation_id=document['operation_id'],mission=projection(service, goal))
        goal['_operations'][document['operation_id']] = {'digest': digest, 'receipt': receipt}
        return goal, receipt
    return service.store.transact(workspace, document['mission_id'], change,
        event=service._event('mission.' + kind, operation_id=document['operation_id']))
