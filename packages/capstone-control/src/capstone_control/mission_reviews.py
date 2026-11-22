"""Durable organizer outbox, driven by admitted Task boundaries, never polling models."""
from copy import deepcopy

from .contracts import identity, object_fields, text, utc_deadline
from .service import Conflict, InvalidTransition, fingerprint

TERMINAL_TASKS = {'delivered', 'verified', 'failed', 'blocked', 'paused', 'cancelled'}


def organizer(goal):
    return goal['_mission'].setdefault('organizer', dict(max_reviews=8,reviews_admitted=0,
        records=[],current_review_id=None,next_boundary=None,suspended=False))


def boundary(goal):
    tasks=[]
    for task in goal['tasks']:
        item={key:deepcopy(task[key]) for key in ('task_id','revision','objective','state','generation','delivery','verification')}
        if task['state'] in {'failed','blocked'} and task.get('observation'):
            item['observation']={key:deepcopy(task['observation'][key]) for key in ('state','summary')}
        if 'failure_reason' in task:
            item['failure_reason'] = task['failure_reason']
        tasks.append(item)
    source=dict(plan_revision=goal['_mission']['plan_revision'],tasks=tasks)
    return {'digest':fingerprint(source),**source}


def progress(goal):
    return fingerprint(dict(boundary=boundary(goal),conclusion=goal['_mission'].get('plan_conclusion'),
                            disposition=organizer(goal).get('disposition')))


def eligible(goal):
    return (goal['state'] not in {'paused','pausing','cancelled','cancelling','accepted','delivered'}
            and not organizer(goal)['suspended'])


def _continue_admitted_tasks(service, goal, reason):
    from .mission import has_dispatchable_task

    if (goal['state'] == 'waiting_review' and goal['_mission'].get('activated')
            and has_dispatchable_task(service, goal)):
        organizer(goal)['suspended'] = False
        goal.update(state='ready', reason=reason)


def recovery_allowed(service, goal, review_id):
    return (organizer(goal)['current_review_id'] == review_id
            and goal['state'] not in {'paused','pausing','cancelled','cancelling','accepted','delivered'}
            and service.now() < utc_deadline(goal['deadline_at']))


def record_for(goal, review_id):
    found=next((item for item in organizer(goal)['records'] if item['intent']['review_id']==review_id),None)
    if found is None:
        raise KeyError(review_id)
    return found


def queue_boundary(goal, *, force=False, explicit_operation=None):
    """Called in the same transaction as a real delivered/verified/failed Task fact."""
    if '_mission' not in goal or (explicit_operation is None
            and not any(t['state'] in TERMINAL_TASKS for t in goal['tasks'])):
        return
    state=organizer(goal)
    facts={task['task_id']:fingerprint(dict(revision=task['revision'],state=task['state'],delivery=task['delivery'],
        verification=None if not task.get('verification') else {key:task['verification'][key] for key in ('delivery_revision','checks')}))
        for task in goal['tasks'] if task['state'] in TERMINAL_TASKS}
    if explicit_operation is None and not force and facts==state.get('last_task_facts',{}):
        return
    state['last_task_facts']=facts
    if goal['reason'] in {'delegation_failed','delegation_unknown','delegation_cancelled'}:
        # Review the failure. This does not retry, reconcile or certify it.
        goal.update(state='waiting_review',reason='task_boundary')
    if not eligible(goal):
        return
    source=boundary(goal)
    current=next((r for r in state['records'] if r['intent']['review_id']==state['current_review_id']),None)
    if current and current['state'] in {'reserved','running'}:
        if explicit_operation is not None:
            raise InvalidTransition('an admitted organizer review is already in progress')
        if current['intent']['boundary']['digest']!=source['digest']:
            state['next_boundary']=source
        return
    if explicit_operation is None and any(r['intent']['boundary']['digest']==source['digest'] for r in state['records']):
        return
    if current and current['state']=='pending':
        state['records'].remove(current)  # Coalesce before any execution admission.
    review_id='review_'+fingerprint([goal['goal_id'],source['digest'],explicit_operation])[:40]
    intent=dict(schema='capstone-mission-review-intent/1',workspace=goal['workspace'],mission_id=goal['goal_id'],
        review_id=review_id,origin=deepcopy(goal['_mission']['origin']),objective=goal['objective'],
        deadline_at=goal['deadline_at'],boundary=source,revision=goal['revision']+1)
    state['records'].append(dict(intent=intent,state='pending',binding=None))
    state['current_review_id']=review_id
    goal.update(state='waiting_review',reason='task_boundary')


def explicit_resume(service,goal,operation_id):
    state=organizer(goal)
    if (service.now()>=utc_deadline(goal['deadline_at']) or state['reviews_admitted']>=state['max_reviews']):
        raise InvalidTransition('organizer review budget or deadline is exhausted')
    state['suspended']=False
    state['disposition']=None
    goal.update(state='waiting_review',reason='organizer_explicit_resume')
    queue_boundary(goal,force=True,explicit_operation=operation_id)


def pending(service, workspace=None, limit=32):
    if type(limit) is not int or not 1<=limit<=128:
        raise ValueError('bounded Mission review page required')
    cursors=getattr(service,'_mission_review_cursors',{})
    after=cursors.get(workspace)
    goals=service.store.list(workspace,limit,after=after)
    if not goals and after is not None:
        goals=service.store.list(workspace,limit)
    cursors[workspace]=goals[-1]['goal_id'] if goals else None
    service._mission_review_cursors=cursors
    result=[]
    for goal in goals:
        if '_mission' not in goal:
            continue
        state = organizer(goal)
        for record in state['records']:
            recovering = (record['state'] == 'interrupted'
                          and goal.get('reason') == 'organizer_interrupted'
                          and recovery_allowed(service, goal, record['intent']['review_id']))
            if recovering or record['state'] in {'reserved','running'} or record['state']=='pending' and eligible(goal):
                result.append(deepcopy(record['intent']))
    return result[:limit]


def transact(service, workspace, mission_id, review_id, kind, apply):
    identity(mission_id);identity(review_id)
    def change(goal):
        if goal is None or '_mission' not in goal:
            raise KeyError(mission_id)
        record=record_for(goal,review_id)
        before=fingerprint(goal)
        result=apply(goal,record)
        if fingerprint(goal)!=before:
            goal['revision']+=1
        return goal,result
    return service.store.transact(workspace,mission_id,change,
        event=service._event('mission.review_'+kind,review_id=review_id))


def reserve(service, workspace, mission_id, review_id):
    def apply(goal,record):
        state=organizer(goal)
        if record['state']=='running':
            return deepcopy(record['intent'])  # Reconcile an already admitted Attempt, including after stop.
        if not eligible(goal) or record['state'] not in {'pending','reserved'}:
            return None
        if service.now()>=utc_deadline(goal['deadline_at']):
            record.update(state='blocked',reason='organizer_deadline_exhausted')
            state['suspended']=True
            return None
        if record['state']=='pending':
            reason=('organizer_deadline_exhausted' if service.now()>=utc_deadline(goal['deadline_at']) else
                    'organizer_budget_exhausted' if state['reviews_admitted']>=state['max_reviews'] else None)
            if reason:
                record.update(state='blocked',reason=reason)
                state['suspended']=True
                goal['reason']=reason
                return None
            record.update(state='reserved',progress_before=progress(goal))
            state['reviews_admitted']+=1
        return deepcopy(record['intent'])
    return transact(service,workspace,mission_id,review_id,'reserved',apply)


def read(service, workspace, mission_id, review_id):
    goal=service.store.read(workspace,mission_id)
    record=record_for(goal,review_id)
    if not eligible(goal) or service.now()>=utc_deadline(goal['deadline_at']) or record['state'] not in {'reserved','running'}:
        raise InvalidTransition('Mission review is not admitted for execution')
    return deepcopy(record['intent'])


def acknowledge(service, workspace, mission_id, review_id, binding):
    object_fields(binding,{'thread_id','work_id','attempt_id'})
    for value in binding.values():identity(value)
    def apply(goal,record):
        origin=record['intent']['origin']
        if binding['thread_id']!=origin['thread_id'] or origin.get('work_id',binding['work_id'])!=binding['work_id']:
            raise Conflict('Mission review binding does not match its origin')
        if record['binding'] is not None:
            if record['binding']!=binding:
                raise Conflict('Mission review Attempt binding changed')
            return deepcopy(record['intent'])
        if record['state']!='reserved':
            raise InvalidTransition('Mission review was not reserved')
        record.update(state='running',binding=deepcopy(binding))
        return deepcopy(record['intent'])
    return transact(service,workspace,mission_id,review_id,'bound',apply)


def finish(service,workspace,mission_id,review_id,attempt_id,phase,*,recovered=False):
    if phase not in {'completed','failed','cancelled','interrupted'}:
        raise ValueError('terminal organizer Attempt phase required')
    def apply(goal,record):
        if not record['binding'] or record['binding']['attempt_id']!=attempt_id:
            raise Conflict('Mission review terminal is not bound to this Attempt')
        state=organizer(goal)
        previous = record.get('finish')
        if previous and (previous['phase'] == phase
                         or phase == 'interrupted' and record.get('interruption')):
            return deepcopy(previous)
        if recovered:
            if phase != 'completed' or previous and previous['phase'] != 'interrupted':
                raise Conflict('Mission review recovery requires the original interrupted Attempt')
            if not recovery_allowed(service, goal, review_id):
                return deepcopy(previous)
            if previous:
                if goal.get('reason') != 'organizer_interrupted':
                    return deepcopy(previous)
                state['suspended'] = False
                goal['reason'] = None
            record['interruption'] = dict(review_id=review_id, attempt_id=attempt_id,
                                          phase='interrupted', state='interrupted')
        elif previous:
            raise Conflict('Mission review terminal identity changed')
        outcome=phase
        if phase=='completed' and progress(goal)==record['progress_before']:
            outcome='no_progress'
        record['state']=outcome
        record['finish']=dict(review_id=review_id,attempt_id=attempt_id,phase=phase,state=outcome)
        if phase in {'cancelled','interrupted','failed'}:
            state['suspended']=True
            goal['reason']='organizer_'+phase
        if phase == 'failed' or outcome == 'no_progress':
            _continue_admitted_tasks(service, goal, 'organizer_' + outcome)
        if phase == 'interrupted':
            return deepcopy(record['finish'])
        next_boundary=state.pop('next_boundary',None)
        state['next_boundary']=None
        if next_boundary is not None and eligible(goal):
            queue_boundary(goal,force=True)
        return deepcopy(record['finish'])
    return transact(service,workspace,mission_id,review_id,'finished',apply)


def block(service,workspace,mission_id,review_id,reason):
    text(reason,limit=256)
    def apply(goal,record):
        if record['state'] not in {'pending','reserved'}:
            return None
        record.update(state='blocked',reason=reason)
        organizer(goal)['suspended']=True
        _continue_admitted_tasks(service, goal, 'organizer_review_blocked')
        return deepcopy(record['intent'])
    return transact(service,workspace,mission_id,review_id,'blocked',apply)


def release(service,workspace,mission_id,review_id,reason):
    """Trusted host only, under the origin lock after proving no Attempt exists."""
    if reason!='origin_paused_before_admission':
        raise ValueError('unsupported unexecuted review release reason')
    def apply(goal,record):
        if record['state']=='abandoned':
            return deepcopy(record['intent'])
        if record['state']!='reserved' or record['binding'] is not None:
            raise InvalidTransition('only a proven unexecuted reservation can be released')
        state=organizer(goal)
        if state['reviews_admitted']<1:
            raise Conflict('organizer reservation accounting is inconsistent')
        state['reviews_admitted']-=1
        record.update(state='abandoned',reason=reason)
        return deepcopy(record['intent'])
    return transact(service,workspace,mission_id,review_id,'released',apply)
