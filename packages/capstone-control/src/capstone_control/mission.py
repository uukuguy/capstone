"""Progressive Mission planning over the existing Control aggregate identity.

Equipment references describe requested registered resources. They do not grant
execution access. The application must admit them at readiness and dispatch.
"""
from copy import deepcopy
from datetime import timedelta
import re

from .contracts import (ContractError, identity, object_fields, positive_integer,
                        text, text_list, utc_deadline, validate_goal_request)
from .service import Conflict, InvalidTransition, fingerprint, public


TASK_FIELDS = {'task_id', 'objective', 'delivery_requirements', 'depends_on',
               'agent_id', 'mode', 'max_attempts', 'required_products', 'required_reference_sources'}


def criteria_verdicts(goal, values):
    """Bind each semantic verdict to the current acceptance contract and saved results."""
    criteria = goal['acceptance_criteria']
    if not isinstance(values, list) or not criteria or len(values) != len(criteria):
        raise ContractError('acceptance verdicts must cover every current criterion')
    indices = set()
    for verdict in values:
        object_fields(verdict, {'criterion_index', 'status', 'explanation', 'evidence'})
        index = verdict['criterion_index']
        if type(index) is not int or not 0 <= index < len(criteria) or index in indices:
            raise ContractError('acceptance criterion indices must be exact and unique')
        indices.add(index)
        if not isinstance(verdict['status'], str) or verdict['status'] not in {'met', 'not_met', 'unknown'}:
            raise ContractError('unsupported acceptance verdict status')
        text(verdict['explanation'])
        refs = verdict['evidence']
        if not isinstance(refs, list) or len(refs) > 64 or (verdict['status'] == 'met' and not refs):
            raise ContractError('met acceptance criteria require bounded saved evidence')
        for ref in refs:
            if not isinstance(ref, dict) or not isinstance(ref.get('kind'), str) or ref['kind'] not in {'product', 'answer'}:
                raise ContractError('unsupported acceptance evidence kind')
            fields = {'kind', 'task_id', 'artifact_id', 'sha256'} if ref['kind'] == 'product' else {'kind', 'task_id', 'answer_ref'}
            object_fields(ref, fields)
            identity(ref['task_id'])
            task = next((task for task in goal['tasks'] if task['task_id'] == ref['task_id']), None)
            delivery = task.get('delivery') if task else None
            verification = task.get('verification') if task else None
            if (not task or task['state'] != 'verified' or not delivery or not verification
                    or verification['delivery_revision'] != delivery['revision']):
                raise Conflict('acceptance evidence requires the current verified Task delivery')
            if ref['kind'] == 'product':
                text(ref['artifact_id'], limit=256)
                if not isinstance(ref['sha256'], str) or re.fullmatch(r'[a-f0-9]{64}', ref['sha256']) is None:
                    raise ContractError('acceptance evidence requires a SHA-256 digest')
                if not any(product.get('artifact_id') == ref['artifact_id'] and product.get('sha256') == ref['sha256']
                           for product in delivery['products']):
                    raise Conflict('acceptance evidence does not match a current saved product')
            else:
                identity(ref['answer_ref'])
                if delivery['answer_ref'] != ref['answer_ref']:
                    raise Conflict('acceptance evidence does not match the current saved answer')
    return deepcopy(sorted(values, key=lambda verdict: verdict['criterion_index']))


def conclusion_satisfied(goal):
    """Old opaque conclusions remain readable; they do not certify acceptance."""
    metadata = goal.get('_mission', {})
    conclusion = metadata.get('plan_conclusion')
    if (not isinstance(conclusion, dict) or conclusion.get('plan_revision') != metadata.get('plan_revision', 1)
            or not goal['tasks'] or not all(task['state'] == 'verified' for task in goal['tasks'])):
        return False
    try:
        checked = criteria_verdicts(goal, conclusion.get('criteria_verdicts'))
    except (ContractError, Conflict):
        return False
    return all(verdict['status'] == 'met' for verdict in checked)


def references(values):
    if not isinstance(values, list) or len(values) > 64:
        raise ContractError('bounded registered equipment references required')
    keys = []
    for ref in values:
        object_fields(ref, {'schema', 'kind', 'id', 'revision'})
        if (ref['schema'] != 'capstone-mission-equipment-reference/1'
                or not isinstance(ref['kind'],str) or ref['kind'] not in {'capability', 'resource_profile', 'skill', 'resource'}):
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
        resource_ids = [ref['id'] for ref in selected if ref['kind'] == 'resource']
        if sum(ref['kind'] == 'skill' for ref in selected) > 1 or any(ref['kind'] == 'skill' for ref in denied):
            raise ContractError('Mission Tasks may select one skill and cannot use skills as restrictions')
        if len(set(resource_ids)) != len(resource_ids) or any(ref['kind'] == 'resource' for ref in denied):
            raise ContractError('Mission Tasks may select one version per resource and cannot use resources as restrictions')
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
        if (service.admit_mission_task is not None
                and service.admit_mission_task(goal['workspace'], deepcopy(goal['_mission']['origin']), deepcopy(task)) is not True):
            raise InvalidTransition('Mission Task is not admitted by the registered application')
        for ref in task.get('equipment', []) + task.get('restrictions', []):
            admit = service.admit_mission_reference
            if admit is None or admit(goal['workspace'], deepcopy(goal['_mission']['origin']), deepcopy(ref)) is not True:
                raise InvalidTransition('Mission equipment reference is not admitted by the application')


def task_state(mission):
    revision = mission['revision']
    organizer = mission['organizer']
    open_items = [] if mission['plan_complete'] else [{'kind': 'mission_plan_incomplete'}]
    for task in mission['tasks']:
        if task['state'] != 'verified':
            open_items.append({'kind': 'mission_task', 'task_id': task['task_id'],
                               'revision': task['revision'], 'state': task['state'], 'objective': task['objective'],
                               'reason': task.get('failure_reason')})
    if organizer.get('reason'):
        open_items.append({'kind': 'organizer', 'reason': organizer['reason']})
    return {
        'schema': 'capstone-task-state/1',
        'task': {'mission_id': mission['mission_id']},
        'revision_ref': str(revision),
        'previous_revision_ref': str(revision - 1) if revision > 1 else None,
        'execution': {'phase': mission['state']},
        'acceptance': 'accepted' if mission.get('acceptance') else 'undecided',
        'open_items': open_items,
        'workflow': {'kind': 'mission', 'plan_revision': mission['plan_revision'],
                     'objective_revision': mission['objective_revision'],
                     'origin': deepcopy(mission['origin']),
                     'objective': mission['objective'],
                     'criteria': deepcopy(mission['acceptance_criteria']),
                     'plan_conclusion_status': mission['plan_conclusion_status'],
                     'organizer': deepcopy(organizer),
                     'deliveries': [{'task_id': task['task_id'], 'task_revision': task['revision'],
                                     'delivery': deepcopy(task['delivery']),
                                     'verification': deepcopy(task.get('verification'))}
                                    for task in mission['tasks'] if task.get('delivery')]},
    }


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
    optional = {'acceptance_criteria', 'max_delegations', 'deadline_at', 'max_organizer_reviews'}
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
    review_budget = positive_integer(request.get('max_organizer_reviews',8))
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
            _mission={'origin': deepcopy(origin), 'plan_revision': 1, 'activated': False,
                      'organizer':dict(max_reviews=review_budget,reviews_admitted=0,records=[],current_review_id=None,
                                       next_boundary=None,suspended=False)})
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
        confirmed_pause = (goal['state'] == 'paused' and previous['state'] == 'paused'
            and previous['delegation'] is not None and previous['delegation'].get('requested_control') == 'pause')
        if not confirmed_pause and (previous['state'] != 'pending' or previous['delegation'] is not None):
            raise InvalidTransition('active or completed Task cannot be replaced by a planning command')
        denied = {fingerprint(ref) for ref in previous.get('restrictions', [])}
        if not denied <= {fingerprint(ref) for ref in spec.get('restrictions', [])}:
            raise InvalidTransition('planning cannot relax saved Task restrictions')
        history = deepcopy(previous.get('delegation_history', []))
        if confirmed_pause:
            history.append(deepcopy(previous['delegation']))
        combined.append({**deepcopy(spec), 'revision': previous['revision'] + 1, 'state': 'pending',
                         'generation': previous['generation'], 'delegation': None, 'delivery': None, 'verification': None,
                         **({'delegation_history': history} if history else {})})
    for spec in changes.values():
        if any(old.get('kind')=='tasks_removed' and any(task['task_id']==spec['task_id'] for task in old['tasks']) for old in goal['history']):
            raise InvalidTransition('removed Task identities remain historical; prepare a new Task identity')
        combined.append({**deepcopy(spec), 'revision': 1, 'state': 'pending',
                         'generation': 0, 'delegation': None, 'delivery': None, 'verification': None})
    # Revalidate the complete dependency order, including retained Tasks.
    plain = [{key: value for key, value in item.items() if key in TASK_FIELDS | {'equipment', 'restrictions'}} for item in combined]
    checked_tasks(plain, goal)
    goal['tasks'] = combined


def command(service, workspace, document, actor, *, validate_task_equipment=False, excluded_skills=()):
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
            if goal['state'] not in {'planning', 'waiting_review', 'ready', 'running', 'paused', 'waiting'}:
                raise InvalidTransition('Mission cannot plan from this state')
            if '_mission' not in goal:
                raise InvalidTransition('legacy Goal needs explicit Mission origin association before planning')
            if validate_task_equipment and kind in {'prepare_task', 'update_plan'}:
                tasks = [payload.get('task')] if kind == 'prepare_task' else payload.get('tasks')
                if not isinstance(tasks, list) or any(not isinstance(task, dict) for task in tasks):
                    raise ContractError('Mission planning requires typed Task proposals')
                admit = service.admit_mission_reference
                for task in tasks:
                    for field in ('equipment', 'restrictions'):
                        for ref in references(task.get(field, [])):
                            if admit is None or admit(workspace, goal['_mission']['origin'], ref) is not True:
                                raise ContractError('Mission Task equipment must use exact currently registered references')
                    skills = [ref for ref in task.get('equipment', []) if ref['kind'] == 'skill']
                    if skills and (any(ref['id'] in excluded_skills for ref in skills)
                                   or service.admit_mission_task is None
                                   or not service.admit_mission_task(workspace, goal['_mission']['origin'], task)):
                        raise ContractError('Mission Task skill is outside the admitted equipment selection')
            if kind == 'ready':
                object_fields(payload, set())
                if goal['state'] not in {'planning','waiting_review'} and not (goal['state'] == 'paused' and not goal['_mission'].get('activated')):
                    raise InvalidTransition('only a planning Mission can become ready')
                dispatch_ready(service, goal)
                verified={t['task_id'] for t in goal['tasks'] if t['state']=='verified'}
                if not any(t['state']=='pending' and set(t['depends_on'])<=verified for t in goal['tasks']):
                    raise InvalidTransition('no dependency-ready Task; inspect results and conclude the plan or wait for required input')
                goal['_mission']['activated'] = True
                goal.update(state='ready', reason=None)
            else:
                if kind == 'prepare_task':
                    object_fields(payload, {'task'})
                    proposed = [payload['task']]
                else:
                    if not {'acceptance_criteria','tasks'}<=payload.keys() or set(payload)-{'acceptance_criteria','tasks','removed_task_ids'}:
                        raise ContractError('invalid Mission plan update fields')
                    if payload['acceptance_criteria']:
                        text_list(payload['acceptance_criteria'])
                    elif not isinstance(payload['acceptance_criteria'], list):
                        raise ContractError('acceptance criteria must be a list')
                    goal['acceptance_criteria'] = deepcopy(payload['acceptance_criteria'])
                    proposed = payload['tasks']
                    removed=payload.get('removed_task_ids',[])
                    if not isinstance(removed,list) or len(removed)>64 or any(not isinstance(item,str) for item in removed) or len(set(removed))!=len(removed):
                        raise ContractError('distinct removed Task identities required')
                    removed_tasks=[]
                    for task_id in removed:
                        identity(task_id)
                        previous=next((t for t in goal['tasks'] if t['task_id']==task_id),None)
                        confirmed_pause=previous and goal['state']=='paused' and previous['state']=='paused' and (previous.get('delegation') or {}).get('requested_control')=='pause'
                        if previous is None or previous['state'] not in {'pending','failed'} and not confirmed_pause:
                            raise InvalidTransition('only unstarted, failed or confirmed paused Tasks can be removed')
                        removed_tasks.append(deepcopy(previous))
                    if removed_tasks:
                        goal['history'].append(dict(kind='tasks_removed',plan_revision=goal['_mission']['plan_revision'],tasks=removed_tasks))
                        goal['tasks']=[t for t in goal['tasks'] if t['task_id'] not in removed]
                        if any(isinstance(t,dict) and t.get('task_id') in removed for t in proposed):
                            raise ContractError('one update cannot remove and recreate the same Task')
                # Validate each proposal against the complete merged order below.
                if not isinstance(proposed, list) or len(proposed) > 64:
                    raise ContractError('bounded Mission Task plan required')
                for spec in proposed:
                    if not isinstance(spec, dict) or not isinstance(spec.get('task_id'), str):
                        raise ContractError('Mission Task identity required')
                update_tasks(goal, proposed)
                goal['_mission']['plan_revision'] += 1
                goal['_mission']['plan_conclusion']=None
                if goal['state']=='ready' and (not goal['tasks'] or not goal['acceptance_criteria']):
                    goal.update(state='planning',reason='plan_incomplete')
            from .mission_reviews import organizer
            organizer(goal)['suspended']=False
            organizer(goal)['disposition']=None
        elif kind == 'conclude_plan':
            object_fields(payload,{'plan_revision','summary','criteria_verdicts'})
            positive_integer(payload['plan_revision'])
            text(payload['summary'],limit=4096)
            if (goal['state'] not in {'planning','waiting_review','ready','running','waiting'} or not goal['tasks'] or not goal['acceptance_criteria']
                    or any(task['state'] in {'dispatching','running','waiting','resume_requested','revoke_requested'} for task in goal['tasks'])):
                raise InvalidTransition('Mission plan conclusion requires a settled Task boundary and acceptance criteria')
            if payload['plan_revision']!=goal['_mission']['plan_revision']:
                raise Conflict('stale Mission plan conclusion')
            verdicts = criteria_verdicts(goal, payload['criteria_verdicts'])
            all_met = all(verdict['status'] == 'met' for verdict in verdicts)
            if all_met and not all(task['state'] == 'verified' for task in goal['tasks']):
                raise InvalidTransition('satisfied Mission conclusion requires all Tasks to be verified')
            goal['_mission']['plan_conclusion']=dict(plan_revision=payload['plan_revision'],summary=payload['summary'],actor=actor,criteria_verdicts=verdicts)
            if all_met:
                goal.update(state='delivered',reason=None)
            else:
                from .mission_reviews import organizer
                organizer(goal)['suspended'] = True
                organizer(goal)['disposition'] = dict(kind='wait',until='user',reason='acceptance_incomplete',revision=goal['revision']+1)
                goal.update(state='waiting',reason='acceptance_incomplete')
        elif kind == 'wait':
            object_fields(payload,{'until','reason'})
            text(payload['reason'],limit=4096)
            if not isinstance(payload['until'],str) or payload['until'] not in {'task_boundary','user'} or goal['state'] in {'paused','pausing','cancelled','cancelling','accepted','delivered'}:
                raise InvalidTransition('Mission cannot wait from this state')
            if payload['until']=='task_boundary' and (goal['state'] not in {'ready','running'} or not any(
                    t['state'] in {'pending','dispatching','running','waiting','resume_requested'} for t in goal['tasks'])):
                raise InvalidTransition('waiting for a Task boundary requires admitted pending or active work')
            from .mission_reviews import organizer
            state=organizer(goal)
            state['disposition']=dict(kind='wait',until=payload['until'],reason=payload['reason'],revision=goal['revision']+1)
            if payload['until']=='user':
                state['suspended']=True
                goal.update(state='waiting',reason='organizer_waiting_user')
        elif kind in {'pause', 'cancel', 'resume', 'delegate_next'}:
            if kind=='resume' and '_mission' in goal and goal['state']=='waiting_review':
                object_fields(payload,set())
                from .mission_reviews import explicit_resume
                explicit_resume(service,goal,document['operation_id'])
            else:
                if kind=='resume' and '_mission' in goal:
                    dispatch_ready(service,goal)
                service._apply(goal, kind, payload, actor=actor)
                if kind=='resume' and '_mission' in goal and not any(t['state'] in {'pending','dispatching','running','waiting','resume_requested'} for t in goal['tasks']):
                    from .mission_reviews import explicit_resume
                    explicit_resume(service,goal,document['operation_id'])
            if kind=='resume' and '_mission' in goal:
                from .mission_reviews import organizer
                organizer(goal)['suspended']=False
                organizer(goal)['disposition']=None
        else:
            raise ContractError('unsupported Mission command kind')
        goal['revision'] += 1
        receipt = dict(schema='capstone-control-mission-receipt/1',operation_id=document['operation_id'],mission=projection(service, goal))
        goal['_operations'][document['operation_id']] = {'digest': digest, 'receipt': receipt}
        return goal, receipt
    return service.store.transact(workspace, document['mission_id'], change,
        event=service._event('mission.' + kind, operation_id=document['operation_id']))
