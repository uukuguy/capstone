"""Work admission at the application boundary, using the Thread ledger."""
from copy import deepcopy
from dataclasses import replace
import json
import secrets

from .enterprise_context import TaskContext, WorkBinding
from .thread_protocol import ModelContextSnapshot, ThreadProtocolError, ThreadSnapshot
from .session_title import SessionTitle
from .application_capacity import limits, require_capacity


WORK_STATUSES = {'ready', 'queued', 'running', 'completed', 'failed', 'cancelled', 'interrupted', 'blocked'}
TASK_DECISIONS = ('accept', 'request_changes')


def checked_work_product_refs(value):
    """Map all public Work selection failures to the command protocol boundary."""
    from .thread_products import checked_selections
    try:
        return checked_selections(value)
    except (ValueError, TypeError, KeyError) as error:
        raise ThreadProtocolError('invalid Work product references') from error


def execution_model(snapshot):
    """Preview the same pending resource choice that legacy message admission activates."""
    return snapshot.pending_model_switch or snapshot.active_model_context


def start_unavailable_reason(snapshot):
    if snapshot.run.state != 'open':
        return 'run_not_open'
    if snapshot.current_attempt is not None:
        return 'attempt_in_progress'
    model = execution_model(snapshot)
    if model is None and snapshot.native_execution is not None:
        return None
    if snapshot.runtime_mode != 'capstone' or model is None:
        return 'execution_unavailable'
    profiles = (model.enabled_profiles if snapshot.pending_model_switch is not None or snapshot.pending_selection is None
                else snapshot.pending_selection.enabled_profiles)
    if not profiles:
        return 'capability_required'
    from .thread_service import _application_case_active, _application_context_lock
    return _application_context_lock(snapshot) or ('case_execution_active' if _application_case_active(snapshot) else None)


def goal_task_workflow(work):
    goal = work.get('goal_mode')
    if goal is None:
        return None
    plan = work.get('goal_plan', {})
    return {'kind': 'goal', 'work_revision': work['revision'],
            'objective_revision': goal['objective_revision'], 'generation': goal['generation'],
            'state': goal['state'], 'reason': goal['reason'],
            'plan_revision': plan.get('plan_revision'), 'step_index': plan.get('step_index'),
            'criteria': deepcopy(plan.get('criteria', [])),
            'review_refs': deepcopy(plan.get('review_refs', []))}


def project_work(snapshot, work):
    from .instruction_queue import supported
    reason = start_unavailable_reason(snapshot)
    if reason is None and len(work_instruction(work)) > limits.input_text_chars:
        reason = 'work_input_too_large'
    if work['status'] in {'queued', 'running'}:
        reason = 'attempt_in_progress'
    projected = deepcopy(work)
    projected.pop('goal_step_review', None)
    projected.pop('goal_followup', None)
    current = snapshot.current_attempt
    if (work.get('conversation_mode') and current is not None
            and work.get('latest_attempt_id') == current.attempt_id):
        projected['execution_checkpoint'] = {
            'attempt_id': current.attempt_id,
            'turn_id': current.turn_id,
            'phase': current.phase,
            'work_revision': work['revision'],
            'task_state_ref': work['task_context'].get('task_state_ref'),
        }
    workflow = goal_task_workflow(work)
    if workflow is not None and 'task_state' in projected:
        projected['task_state']['workflow'] = workflow
    return {**projected, 'latest_attempt_id': work.get('latest_attempt_id'),
            'consumed_message_count': work.get('consumed_message_count', 0),
            'cancel_requested': work.get('cancel_requested', False),
            'instruction_queue_available': snapshot.active_model_context is None and supported(snapshot.native_execution),
            'start_available': reason is None, 'start_unavailable_reason': reason}


def checked_business_report(value):
    fields = ('completed', 'open', 'defects', 'blockers')
    if not isinstance(value, dict) or set(value) != set(fields):
        return None
    report = {}
    for field in fields:
        items = value[field]
        if not isinstance(items, list) or len(items) > 8 or any(
                not isinstance(item, str) or not 0 < len(item.strip()) <= 160 for item in items):
            return None
        report[field] = [item.strip() for item in items]
    return report


def settle_task_state(snapshot, work_payload, task_context, attempt, phase, submission, business_report=None):
    if task_context is None:
        return snapshot, work_payload
    work_id = task_context.binding.work_id
    work = next((item for item in snapshot.works if item['work_id'] == work_id), None)
    if work is None or not (work.get('conversation_mode') or 'goal_mode' in work):
        return snapshot, work_payload
    previous = work.get('task_state')
    predecessor = None if previous is None else previous['revision_ref']
    if predecessor == attempt.attempt_id:
        predecessor = previous['previous_revision_ref']
    state = {
        'schema': 'capstone-task-state/1',
        'task': {'thread_id': snapshot.thread_id, 'work_id': work_id},
        'revision_ref': attempt.attempt_id,
        'previous_revision_ref': predecessor,
        'execution': {'attempt_id': attempt.attempt_id, 'turn_id': attempt.turn_id, 'phase': phase},
        'acceptance': 'undecided',
        'open_items': [] if phase == 'completed' else [{'kind': 'execution_incomplete', 'reason': phase}],
    }
    instruction_command = (submission or {}).get('_instruction_command_id')
    if instruction_command is not None:
        state['instruction_command_id'] = instruction_command
    unconfirmed = [item['id'] for item in work.get('instruction_queue', ())
                   if item['state'] == 'delivery_unknown']
    if unconfirmed:
        state['unconfirmed_instruction_refs'] = unconfirmed
    handoff = (submission or {}).get('_task_handoff')
    if handoff is not None:
        from .task_handoff import MISSION_FIELDS, SELECTION_FIELDS, parse_task_handoff
        state['handoff'] = parse_task_handoff({
            field: handoff[field] for field in handoff.keys() & (SELECTION_FIELDS | MISSION_FIELDS)})
    elif previous is not None and 'handoff' in previous:
        state['handoff'] = previous['handoff']
    report = checked_business_report(business_report)
    if report is not None:
        state['business_report'] = report
        state['business_report_source'] = attempt.attempt_id
    else:
        report_source = handoff['state'] if handoff is not None else previous
        if report_source is not None and 'business_report' in report_source:
            state['business_report'] = report_source['business_report']
            state['business_report_source'] = report_source['business_report_source']
    settled = {**work, 'task_state': state}
    settled.pop('task_decision', None)
    snapshot = replace(snapshot, works=tuple(
        settled if item['work_id'] == work_id else item for item in snapshot.works))
    return snapshot, {**work_payload, 'work': project_work(snapshot, settled)}


def transition_work(snapshot, task_context, attempt_id, status):
    """Apply an Attempt boundary only to its exact, host-frozen Work."""
    if task_context is None:
        return snapshot, None
    works = deepcopy(list(snapshot.works))
    work = next((item for item in works if item['work_id'] == task_context.binding.work_id), None)
    if (work is None or work['task_context'] != task_context.to_document()
            or (work.get('latest_attempt_id') is not None and work['latest_attempt_id'] != attempt_id)):
        raise ThreadProtocolError('attempt Work snapshot is inconsistent')
    work['revision'] += 1
    work['status'] = status
    work['blocked_reason'] = None
    work['latest_attempt_id'] = attempt_id
    if status == 'completed':
        work.pop('context_product_refs', None)
        if work.get('conversation_mode'):
            # Full transcript is in the same event/Attempt ledger. Keep only
            # unconsumed input here so a normal conversation has no turn cap.
            work['messages'] = []
            work['consumed_message_count'] = 0
        else:
            work['consumed_message_count'] = len(work['messages'])
    if status in {'completed', 'failed', 'cancelled', 'interrupted'}:
        goal_followup = work.pop('goal_followup', False)
        for item in work.get('instruction_queue', []):
            if item['attempt_id'] != attempt_id:
                continue
            if item['state'] == 'delivering':
                item['state'] = 'delivery_unknown'
            elif item['state'] == 'pending' and item.get('mode') == 'interrupt' and work.get('cancel_requested'):
                item['state'] = 'withdrawn'
        work['cancel_requested'] = False
        pending = work.pop('pending_goal_control', None)
        if pending is not None:
            goal = pending['goal_mode']
            previous = work['goal_mode']
            if (goal['reason'] != 'user_pause' or goal['generation'] != previous['generation']
                    or goal['objective_revision'] != previous['objective_revision']):
                work.pop('goal_continuation', None)
            if goal['generation'] != previous['generation'] and ('goal_plan' in work or work.get('goal_plan_pending')):
                work.pop('goal_plan', None)
                work['goal_plan_pending'] = True
            work.update(goal_mode=goal, goal=goal['objective'], goal_revision=goal['objective_revision'])
            work['task_context'] = replace(task_context, goal_revision=goal['objective_revision']).to_document()
        elif 'goal_mode' in work and not goal_followup:
            goal = dict(work['goal_mode'])
            goal.update(state='paused', reason=('goal_receipt_missing' if status == 'completed'
                        else 'attempt_' + status), last_settled_attempt_id=attempt_id)
            work['goal_mode'] = goal
        if status != 'completed' and work.get('conversation_mode'):
            # This instruction's input is closed. The text stays for an explicit
            # retry; a later new instruction does not append to it.
            work['consumed_message_count'] = len(work['messages'])
    return replace(snapshot, works=tuple(works)), work


def work_event_payload(snapshot, task_context, attempt_id, status):
    updated, work = transition_work(snapshot, task_context, attempt_id, status)
    return updated, ({} if work is None else {'work_id': work['work_id'], 'work': project_work(updated, work)})


def settle_early_task_state(snapshot, task_context, attempt, submission):
    updated, payload = work_event_payload(snapshot, task_context, attempt.attempt_id, attempt.phase)
    return settle_task_state(updated, payload, task_context, attempt, attempt.phase, submission)


def create_attempt(snapshot, work, *, turn_id=None, bind_task_state=False):
    """Adapt one explicit Work start to the existing accepted Attempt contract."""
    from .thread_protocol import AttemptSnapshot
    if snapshot.current_attempt is not None:
        raise ThreadProtocolError('attempt already active')
    if 'goal_mode' in work and not work.get('goal_followup'):
        from datetime import datetime, timezone
        from .goal_mode import parse_goal_mode
        goal = parse_goal_mode(work['goal_mode'])
        if (goal['state'] != 'ready' or goal['attempts_admitted'] >= goal['max_attempts']
                or datetime.fromisoformat(goal['deadline_at']) <= datetime.now(timezone.utc)):
            raise ThreadProtocolError('goal execution unavailable')
        goal.update(state='running', reason=None, attempts_admitted=goal['attempts_admitted'] + 1)
        work['goal_mode'] = goal
    token = secrets.token_hex(8)
    model = snapshot.active_model_context
    context = replace(TaskContext.from_document(work['task_context']),
                      model_contexts=() if model is None else (model,))
    if (bind_task_state or 'goal_mode' in work) and 'task_state' in work:
        context = replace(context, task_state_ref=work['task_state']['revision_ref'])
    work['task_context'] = context.to_document()
    attempt = AttemptSnapshot(turn_id or 'turn_' + token, 'attempt_' + token, 'accepted',
                              None if model is None else model.id, snapshot.runtime_mode)
    instruction = work_instruction(work)
    # Only an explicit new execution rebinds untouched inputs. In-flight
    # delivery remains bound to its old attempt for recovery inspection.
    for item in work.get('instruction_queue', []):
        if item['state'] == 'pending':
            item['attempt_id'] = attempt.attempt_id
    work['latest_attempt_id'] = attempt.attempt_id
    return replace(snapshot, current_attempt=attempt), attempt, context, instruction


def prepare_mission_review(snapshot, work_id, *, attempt_id, turn_id):
    """Resume an idle organizer without changing any admitted user input."""
    from .thread_protocol import AttemptSnapshot
    if snapshot.current_attempt is not None or snapshot.active_model_context is not None:
        return None
    works = deepcopy(list(snapshot.works))
    work = next((item for item in works if item['work_id'] == work_id), None)
    if (work is None or work.get('status') != 'completed' or work.get('cancel_requested')
            or not work.get('conversation_mode') or 'goal_mode' in work
            or snapshot.pending_model_switch is not None or snapshot.pending_selection is not None):
        return None
    context = replace(TaskContext.from_document(work['task_context']),
                      snapshot_id='task_' + secrets.token_hex(10),
                      task_state_ref=work.get('task_state', {}).get('revision_ref'))
    work.update(status='queued', blocked_reason=None, latest_attempt_id=attempt_id,
                revision=work['revision'] + 1, task_context=context.to_document())
    attempt = AttemptSnapshot(turn_id, attempt_id, 'accepted', None, snapshot.runtime_mode)
    return replace(snapshot, works=tuple(works), current_attempt=attempt), work, attempt, context


def work_instruction(work):
    """Keep every unconsumed supplement; a closed conversation retries its saved text."""
    if work.get('goal_followup'):
        return work['messages'][-1]
    if 'goal_continuation' in work:
        instruction = work['goal_continuation']['next_instruction']
        return instruction if 'goal_plan' in work else work['goal'] + '\n\nNext step:\n' + instruction
    if 'goal_plan' in work:
        plan = work['goal_plan']
        return plan['plan']['steps'][plan.get('step_index', 0)]['instruction']
    pending = work['messages'][work.get('consumed_message_count', 0):]
    if work.get('conversation_mode'):
        return '\n\n'.join(pending or work['messages'])
    if pending and pending[0] == work['goal']:
        pending = pending[1:]
    return work['goal'] if not pending else work['goal'] + '\n\nAdditional messages:\n' + json.dumps(pending, ensure_ascii=False)


def parse_command(command):
    fields = {'schema', 'command_id', 'idempotency_key', 'thread_id', 'run_id', 'kind', 'payload', 'target'}
    if set(command) - fields or not fields - {'run_id'} <= set(command):
        raise ThreadProtocolError('invalid Work command fields')
    from .thread_service import _identifier, _canonical, _validate_json
    for key in ('command_id', 'idempotency_key', 'thread_id'):
        _identifier(command[key], name=key)
    if command.get('run_id') is not None:
        _identifier(command['run_id'], name='run_id')
    target = command['target']
    target_kind = {'rename_session': 'session_title', 'set_session_skills': 'session_skills'}.get(command['kind'], 'work')
    if (not isinstance(target, dict) or set(target) != {'kind', 'id', 'expected_revision'}
            or target['kind'] != target_kind or type(target['expected_revision']) is not int
            or target['expected_revision'] < 0):
        raise ThreadProtocolError('invalid Work target')
    _identifier(target['id'], name='target.id')
    if not isinstance(command['kind'], str) or not isinstance(command['payload'], dict):
        raise ThreadProtocolError('invalid Work command')
    if command['kind'] in {'admit_goal_plan', 'fail_goal_plan', 'settle_goal_review'}:
        from .session_goal_plan import initial_plan_admission
        if not initial_plan_admission.get():
            raise ThreadProtocolError('Goal plan commands are internal')
    if command['kind'] == 'send_message' and (set(command['payload']) - {
            'text', 'input', 'context_selection', 'resource_profile', 'enabled_profiles', 'source_attempt_id', 'material_refs', 'context_product_refs', 'attachment_refs', 'deep_research', 'llm_profile_id', 'excluded_session_skills', 'task_handoff'}):
        raise ThreadProtocolError('invalid message input fields')
    if command['kind'] == 'send_message' and 'task_handoff' in command['payload']:
        from .task_handoff import parse_task_handoff
        parse_task_handoff(command['payload']['task_handoff'])
        if 'source_attempt_id' in command['payload']:
            raise ThreadProtocolError('task handoff cannot be combined with another history source')
    _validate_json(command['payload'], name='command.payload')
    require_capacity('command_bytes', len(_canonical(command).encode()), phase='command')
    if len(_canonical(command).encode()) > limits.command_bytes:
        raise ThreadProtocolError('command is too large')
    return {**deepcopy(command), 'run_id': command.get('run_id')}


def apply_work(snapshot, command, *, archived=False, goal_followup=False):
    """Return a new snapshot and rejection; never queue an unsupported executor."""
    if archived:
        return snapshot, 'thread_archived', None
    if snapshot.run.state != 'open':
        return snapshot, 'run_not_open', None
    if command['run_id'] is not None and command['run_id'] != snapshot.run.run_id:
        return snapshot, 'run_mismatch', None
    if snapshot.current_attempt is not None and command['kind'] not in {
            'cancel_work', 'pause_goal', 'cancel_goal', 'revise_goal_objective',
            'queue_instruction', 'withdraw_instruction'}:
        return snapshot, 'attempt_in_progress', None
    from .thread_service import _application_case_active, _application_context_lock
    if (context_lock := _application_context_lock(snapshot)) is not None:
        return snapshot, context_lock, None
    if _application_case_active(snapshot):
        return snapshot, 'case_execution_active', None
    target_work = next((item for item in snapshot.works
                        if item['work_id'] == command['target']['id']), None)
    if command['kind'] == 'record_task_decision':
        from .thread_protocol import _identifier
        payload = command['payload']
        if set(payload) != {'revision_ref', 'decision'} or payload['decision'] not in TASK_DECISIONS:
            raise ThreadProtocolError('invalid task decision')
        source = _identifier(payload['revision_ref'], name='task_decision.revision_ref')
        if target_work is None:
            return snapshot, 'work_not_found', None
        if target_work['revision'] != command['target']['expected_revision']:
            return snapshot, 'revision_conflict', None
        state = target_work.get('task_state')
        if state is None or state['revision_ref'] != source:
            return snapshot, 'task_state_revision_conflict', None
        work = {**target_work, 'revision': target_work['revision'] + 1,
                'task_decision': {**payload, 'command_id': command['command_id']}}
        works = tuple(work if item['work_id'] == work['work_id'] else item for item in snapshot.works)
        if len(json.dumps(works, ensure_ascii=False).encode()) > limits.work_state_bytes:
            return snapshot, 'work_limit_reached', None
        return replace(snapshot, works=works), None, work
    if command['kind'] in {'queue_instruction', 'withdraw_instruction'}:
        from .instruction_queue import submit, withdraw
        if target_work is None:
            return snapshot, 'work_not_found', None
        if target_work['revision'] != command['target']['expected_revision']:
            return snapshot, 'revision_conflict', None
        work = deepcopy(target_work)
        payload = command['payload']
        if command['kind'] == 'queue_instruction':
            if set(payload) - {'mode'} != {'text'} or ('mode' in payload and payload['mode'] != 'interrupt') or not isinstance(payload['text'], str) or not payload['text'].strip():
                raise ThreadProtocolError('Instruction text is required')
            current = snapshot.current_attempt
            if current is None or current.attempt_id != work.get('latest_attempt_id'):
                return snapshot, 'attempt_target_mismatch', None
            if work.get('cancel_requested'):
                return snapshot, 'attempt_stopping', None
            queue = work.get('instruction_queue', [])
            if len(queue) >= limits.work_message_count or len(payload['text']) > limits.input_text_chars:
                return snapshot, 'work_limit_reached', None
            mode = payload.get('mode')
            if mode == 'interrupt':
                if snapshot.active_model_context is not None or not work.get('conversation_mode') or 'goal_mode' in work:
                    return snapshot, 'instruction_queue_unavailable', None
                if any(item['attempt_id'] == current.attempt_id and item['state'] == 'pending'
                       and item.get('mode') == 'interrupt' for item in queue):
                    return snapshot, 'attempt_stopping', None
            work['instruction_queue'] = submit(queue, command['command_id'], payload['text'], current.attempt_id, mode=mode)
        else:
            if set(payload) != {'instruction_id'} or not isinstance(payload['instruction_id'], str):
                raise ThreadProtocolError('Instruction identity is required')
            try:
                work['instruction_queue'] = withdraw(work.get('instruction_queue', []), payload['instruction_id'])
            except ValueError:
                return snapshot, 'instruction_unavailable', None
        work['revision'] += 1
        works = tuple(work if item['work_id'] == work['work_id'] else deepcopy(item) for item in snapshot.works)
        if len(json.dumps(works, ensure_ascii=False).encode()) > limits.work_state_bytes:
            return snapshot, 'work_limit_reached', None
        return replace(snapshot, works=works), None, work
    if command['kind'] == 'settle_goal_review':
        from .goal_receipts import apply_terminal_goal_proposal
        from .session_goal_plan import GoalReviewValidationError, initial_plan_admission
        if not initial_plan_admission.get():
            return snapshot, 'goal_plan_admission_required', None
        if (target_work is None or target_work['revision'] != command['target']['expected_revision']
                or target_work.get('goal_mode', {}).get('reason') != 'goal_review_pending'):
            return snapshot, 'goal_review_unavailable', None
        work = deepcopy(target_work)
        delivery = work.pop('goal_step_review')
        if command['payload'].get('attempt_id') != delivery['attempt_id']:
            return snapshot, 'goal_review_unavailable', None
        work['goal_mode'].update(state='running', reason=None, last_settled_attempt_id=None)
        work['revision'] += 1
        works = tuple(work if item['work_id'] == work['work_id'] else item for item in snapshot.works)
        staged = replace(snapshot, works=works)
        try:
            updated = apply_terminal_goal_proposal(staged, TaskContext.from_document(work['task_context']),
                delivery['attempt_id'], command['payload'].get('proposal'), delivery_saved=True,
                saved_product_refs=tuple(delivery['product_refs']), saved_authority_refs=tuple(delivery['authority_refs']))
        except ValueError as error:
            from .native_failure_origin import native_failure_origin
            import logging
            reason = error.code if isinstance(error, GoalReviewValidationError) else 'goal_review_invalid'
            logging.getLogger(__name__).warning(
                'Goal review admission failed; attempt_id=%s reason=%s origin=%s',
                delivery['attempt_id'], reason, native_failure_origin(error))
            work['goal_step_review'] = delivery
            work['goal_mode'].update(state='paused', reason=reason,
                                     last_settled_attempt_id=delivery['attempt_id'])
            return staged, None, work
        reviewed = next(item for item in updated.works if item['work_id'] == work['work_id'])
        return updated, None, reviewed
    if command['kind'] in {'admit_goal_plan', 'fail_goal_plan'}:
        from .session_goal_plan import bind_initial_goal_plan, initial_plan_admission
        if not initial_plan_admission.get():
            return snapshot, 'goal_plan_admission_required', None
        if target_work is None or not target_work.get('goal_plan_pending'):
            return snapshot, 'goal_plan_unavailable', None
        if target_work['revision'] != command['target']['expected_revision']:
            return snapshot, 'revision_conflict', None
        if command['kind'] == 'fail_goal_plan':
            reason = command['payload'].get('reason')
            if (reason not in ('goal_planning_failed', 'deadline_elapsed')
                    or target_work['goal_mode']['state'] != 'ready'):
                return snapshot, 'goal_plan_unavailable', None
            work = deepcopy(target_work)
            work['goal_mode'].update(state='paused', reason=reason)
            work['revision'] += 1
            works = tuple(work if item['work_id'] == work['work_id'] else item for item in snapshot.works)
            return replace(snapshot, works=works), None, work
        if start_unavailable_reason(snapshot) is not None:
            return snapshot, 'execution_unavailable', None
        from datetime import datetime, timezone
        if datetime.fromisoformat(target_work['goal_mode']['deadline_at']) <= datetime.now(timezone.utc):
            return snapshot, 'goal_deadline_elapsed', None
        payload = command['payload']
        work = deepcopy(target_work)
        try:
            receipt = bind_initial_goal_plan(payload['plan'], thread_id=snapshot.thread_id, work=work,
                objective_revision=payload['objective_revision'], generation=payload['generation'])
        except (KeyError, ValueError):
            return snapshot, 'goal_plan_invalid', None
        work.pop('goal_plan_pending')
        work.update(goal_plan=receipt, status='queued', blocked_reason=None, cancel_requested=False,
                    revision=work['revision'] + 1)
        works = tuple(work if item['work_id'] == work['work_id'] else item for item in snapshot.works)
        if len(json.dumps(works, ensure_ascii=False).encode()) > limits.work_state_bytes:
            return snapshot, 'work_limit_reached', None
        return replace(snapshot, works=works), None, work
    if command['kind'] in {'start_goal', 'pause_goal', 'resume_goal', 'cancel_goal', 'revise_goal_objective', 'continue_goal'}:
        from datetime import datetime, timezone
        from .goal_mode import GOAL_SCHEMA, control_goal, parse_goal_mode
        if target_work is None:
            return snapshot, 'work_not_found', None
        if target_work['revision'] != command['target']['expected_revision']:
            return snapshot, 'revision_conflict', None
        work = deepcopy(target_work)
        now = datetime.now(timezone.utc)
        try:
            if command['kind'] == 'start_goal':
                if 'goal_mode' in work:
                    return snapshot, 'goal_already_exists', None
                payload = command['payload']
                if set(payload) != {'objective', 'max_attempts', 'deadline_at'}:
                    raise ValueError('invalid goal start payload')
                goal = parse_goal_mode({'schema': GOAL_SCHEMA, **payload,
                    'objective_revision': work['goal_revision'] + 1, 'generation': 1,
                    'state': 'ready', 'reason': None, 'attempts_admitted': 0,
                    'last_settled_attempt_id': None})
                if datetime.fromisoformat(goal['deadline_at']) <= now:
                    raise ValueError('goal deadline elapsed')
            elif command['kind'] == 'continue_goal':
                from .goal_continuation import continuation_command
                expected = continuation_command(snapshot.thread_id, work)
                if expected is None or command['payload'] != expected['payload']:
                    return snapshot, 'goal_continuation_unavailable', None
                goal = parse_goal_mode(work['goal_mode'])
            else:
                if 'goal_mode' not in work:
                    return snapshot, 'goal_unavailable', None
                if (command['kind'] == 'resume_goal' and 'goal_step_review' in work
                        and work['goal_mode']['state'] == 'paused' and not command['payload']):
                    goal = {**work['goal_mode'], 'state': 'waiting', 'reason': 'goal_review_pending'}
                else:
                    goal = control_goal(work['goal_mode'], command['kind'], command['payload'], now=now)
        except ValueError as error:
            raise ThreadProtocolError(str(error)) from error
        if snapshot.current_attempt is not None:
            if work.get('latest_attempt_id') != snapshot.current_attempt.attempt_id:
                return snapshot, 'attempt_target_mismatch', None
            work.update(pending_goal_control={'goal_mode': goal}, cancel_requested=True,
                        revision=work['revision'] + 1)
            works = tuple(work if item['work_id'] == work['work_id'] else deepcopy(item) for item in snapshot.works)
            return replace(snapshot, works=works), None, work
        work.update(goal_mode=goal, goal=goal['objective'], goal_revision=goal['objective_revision'],
                    revision=work['revision'] + 1)
        if command['kind'] in {'revise_goal_objective', 'cancel_goal'}:
            work.pop('goal_continuation', None)
            work.pop('goal_step_review', None)
        if command['kind'] == 'revise_goal_objective' and ('goal_plan' in work or work.get('goal_plan_pending')):
            work.pop('goal_plan', None)
            work['goal_plan_pending'] = True
        context = TaskContext.from_document(work['task_context'])
        work['task_context'] = replace(context, goal_revision=work['goal_revision']).to_document()
        if command['kind'] == 'start_goal':
            work.update(goal_plan_pending=True, status='ready', blocked_reason=None, cancel_requested=False)
        if (command['kind'] in {'resume_goal', 'continue_goal'} and not work.get('goal_plan_pending')
                and 'goal_step_review' not in work and start_unavailable_reason(snapshot) is None):
            work.update(status='queued', blocked_reason=None, cancel_requested=False)
        works = tuple(work if item['work_id'] == work['work_id'] else deepcopy(item) for item in snapshot.works)
        if len(json.dumps(works, ensure_ascii=False).encode()) > limits.work_state_bytes:
            return snapshot, 'work_limit_reached', None
        return replace(snapshot, works=works), None, work
    goal = (target_work or {}).get('goal_mode')
    followup = (goal is not None and command['kind'] == 'send_message'
                and goal['state'] in {'waiting', 'paused', 'completed', 'failed', 'cancelled'}
                and goal['reason'] != 'goal_review_pending')
    if (goal is not None and not (followup or goal_followup)
            and command['kind'] in {'send_message', 'work_message', 'revise_goal', 'start_work'}):
        # Legacy commands cannot change the objective or bypass its execution
        # budget. Goal controls use their own versioned admission contract.
        return snapshot, 'goal_control_required', None
    if command['kind'] == 'send_message':
        if command['target']['id'] == 'new' and any(work.get('conversation_mode') for work in snapshot.works):
            return snapshot, 'conversation_work_exists', None
        staged = snapshot
        previous = next((item for item in snapshot.works if item['work_id'] == command['target']['id']), None)
        if (previous is not None and previous.get('conversation_mode')
                and previous['status'] in {'cancelled', 'failed', 'interrupted'}):
            # A new instruction supersedes the pending input of a finished
            # Attempt. Keep the old bytes in history and available for explicit
            # retry; never concatenate them into an unrelated new request.
            works = deepcopy(list(snapshot.works))
            prior = next(item for item in works if item['work_id'] == previous['work_id'])
            prior['consumed_message_count'] = len(prior['messages'])
            staged = replace(snapshot, works=tuple(works))
        saved, rejection, work = apply_work(staged, {**command, 'kind': 'work_message',
            'payload': {'text': command['payload'].get('text')}}, archived=archived, goal_followup=followup)
        if rejection is not None:
            return snapshot, rejection, None
        assert work is not None
        if followup:
            work['goal_followup'] = True
        work['conversation_mode'] = True
        reason = start_unavailable_reason(saved)
        if reason is not None:
            return snapshot, reason, None
        if len(work_instruction(work)) > limits.input_text_chars:
            return snapshot, 'work_input_too_large', None
        work['status'], work['blocked_reason'] = 'queued', None
        work['cancel_requested'] = False
        work['task_context'] = replace(TaskContext.from_document(work['task_context']),
            snapshot_id='task_' + secrets.token_hex(10)).to_document()
        return saved, None, work
    if command['kind'] not in {'work_message', 'revise_goal', 'start_work', 'cancel_work'}:
        return snapshot, 'execution_unavailable', None
    payload = command['payload']
    if command['kind'] in {'start_work', 'cancel_work'}:
        if payload:
            raise ThreadProtocolError('Work control payload must be empty')
    elif (not {'text'} <= set(payload) or set(payload)-{'text','context_product_refs'}
            or not isinstance(payload['text'], str) or not payload['text'].strip()):
        raise ThreadProtocolError('Work text is required')
    if 'context_product_refs' in payload:
        refs = checked_work_product_refs(payload['context_product_refs'])
        if any(item['ref']['thread_id'] != snapshot.thread_id for item in refs):
            return snapshot, 'product_context_unavailable', None
    target = command['target']
    works = deepcopy(list(snapshot.works))
    work = next((item for item in works if item['work_id'] == target['id']), None)
    if target['id'] == 'new':
        if len(works) >= limits.work_count:
            return snapshot, 'work_limit_reached', None
        if command['kind'] != 'work_message' or target['expected_revision'] != 0:
            return snapshot, 'revision_conflict', None
        work_id = 'work_' + secrets.token_hex(10)
        context = TaskContext(WorkBinding(snapshot.thread_id, work_id, 'research-' + secrets.token_hex(10)),
                              1, 'task_' + secrets.token_hex(10),
                              () if snapshot.active_model_context is None else (snapshot.active_model_context,))
        reason = start_unavailable_reason(snapshot)
        work = {'work_id': work_id, 'goal': payload['text'], 'goal_revision': 1, 'revision': 1,
                'status': 'ready' if reason is None else 'blocked', 'blocked_reason': reason,
                'latest_attempt_id': None,
                'consumed_message_count': 0,
                'cancel_requested': False,
                'task_context': context.to_document(), 'messages': [payload['text']]}
        works.append(work)
    else:
        if work is None:
            return snapshot, 'work_not_found', None
        if work['revision'] != target['expected_revision']:
            return snapshot, 'revision_conflict', None
        if command['kind'] == 'cancel_work':
            current = snapshot.current_attempt
            if current is None or work.get('latest_attempt_id') != current.attempt_id:
                return snapshot, 'attempt_target_mismatch', None
            if work.get('cancel_requested', False):
                return snapshot, 'cancel_already_requested', None
            work['revision'] += 1
            work['cancel_requested'] = True
            return replace(snapshot, works=tuple(works)), None, work
        if command['kind'] == 'start_work':
            reason = start_unavailable_reason(snapshot)
            if reason is not None:
                return snapshot, reason, None
            if len(work_instruction(work)) > limits.input_text_chars:
                return snapshot, 'work_input_too_large', None
            previous = TaskContext.from_document(work['task_context'])
            context = TaskContext(previous.binding, work['goal_revision'], 'task_' + secrets.token_hex(10),
                                  () if snapshot.active_model_context is None else (snapshot.active_model_context,), previous.resource_refs)
            work['task_context'] = context.to_document()
            work['revision'] += 1
            work['status'] = 'queued'
            work['blocked_reason'] = None
            work['latest_attempt_id'] = None
            work['cancel_requested'] = False
            return replace(snapshot, works=tuple(works)), None, work
        if len(work['messages']) >= limits.work_message_count:
            return snapshot, 'work_limit_reached', None
        work['revision'] += 1
        work['messages'].append(payload['text'])
        reason = start_unavailable_reason(snapshot)
        work['status'] = 'ready' if reason is None else 'blocked'
        work['blocked_reason'] = reason
        if command['kind'] == 'revise_goal' and work['goal'] != payload['text']:
            work['goal'] = payload['text']
            work['goal_revision'] += 1
            context = TaskContext.from_document(work['task_context'])
            work['task_context'] = replace(context, goal_revision=work['goal_revision'],
                                           snapshot_id='task_' + secrets.token_hex(10)).to_document()
    if 'context_product_refs' in payload:
        prior = work.get('context_product_refs', [])
        merged = {json.dumps(item,sort_keys=True):item for item in [*prior,*refs]}
        work['context_product_refs'] = checked_work_product_refs(list(merged.values()))
    if len(json.dumps(works, ensure_ascii=False).encode()) > limits.work_state_bytes:
        return snapshot, 'work_limit_reached', None
    return replace(snapshot, minimum_protocol_version=2, works=tuple(works)), None, work


def snapshot_document(snapshot, document):
    current = document['current_attempt']
    if current is not None:
        current = {**current, 'work_id': next((work['work_id'] for work in snapshot.works
            if work.get('latest_attempt_id') == current['attempt_id']), None)}
    return {**document, 'current_attempt': current, 'schema': 'capstone-thread-snapshot/2', 'minimum_protocol_version': 2,
            'native_execution': {'available': snapshot.active_model_context is None and snapshot.native_execution is not None,
                                 'unavailable_reason': None if snapshot.active_model_context is None and snapshot.native_execution is not None else 'execution_unavailable'},
            'selected_model_context_id': None if snapshot.active_model_context is None else snapshot.active_model_context.id,
            'task_context': None if not snapshot.works else deepcopy(snapshot.works[-1]['task_context']),
            'works': [project_work(snapshot, work) for work in snapshot.works]}


def parse_snapshot(document):
    if isinstance(document.get('works'), list):
        require_capacity('work_count', len(document['works']), phase='snapshot')
        require_capacity('work_state_bytes', len(json.dumps(document['works'], ensure_ascii=False).encode()), phase='snapshot')
    extra = {'minimum_protocol_version', 'selected_model_context_id', 'task_context', 'works'}
    base = {key: value for key, value in document.items() if key not in extra | {'native_execution'}}
    context = base.get('active_model_context')
    current = base.get('current_attempt')
    if isinstance(current, dict):
        base['current_attempt'] = {key: value for key, value in current.items() if key != 'work_id'}
    if (not extra <= set(document) or document.get('minimum_protocol_version') != 2
            or not isinstance(document.get('works'), list) or len(document['works']) > limits.work_count):
        raise ThreadProtocolError('invalid Work snapshot')
    # Validate all common fields with the existing strict parser. No substitute
    # model is created for the model-free representation.
    if context is None:
        from .thread_protocol import RunSnapshot, _identifier, _sequence
        allowed = {'schema', 'runtime_mode', 'thread_id', 'run', 'active_model_context', 'active_grid_page_id',
                   'current_attempt', 'last_event_seq', 'base_event_seq', 'application_state', 'session_title', 'session_type', 'session_skills', 'mission_refs'}
        required = allowed - {'runtime_mode', 'application_state', 'session_title', 'session_type', 'session_skills', 'mission_refs'}
        if (set(base) - allowed or not required <= set(base)
                or base.get('active_grid_page_id') is not None):
            raise ThreadProtocolError('invalid model-free snapshot')
        from .thread_protocol import AttemptSnapshot
        snapshot = ThreadSnapshot(_identifier(base['thread_id'], name='thread_id'), RunSnapshot.from_document(base['run']),
                                  None, None, None if current is None else AttemptSnapshot.from_document(base['current_attempt']), _sequence(base['last_event_seq'], name='last_event_seq'),
                                  _sequence(base['base_event_seq'], name='base_event_seq'),
                                  application_state=base.get('application_state'), runtime_mode=base.get('runtime_mode', 'capstone'),
                                  mission_refs=tuple(base.get('mission_refs', ())),
                                  minimum_protocol_version=2,
                                  session_type=base.get('session_type'),
                                  session_skills=base.get('session_skills'),
                                  session_title=None if base.get('session_title') is None else SessionTitle.from_document(base['session_title']))
    else:
        base['schema'] = 'capstone-thread-snapshot/1'
        snapshot = ThreadSnapshot.from_document(base)
    identities = set()
    for work in document['works']:
        fields = {'work_id', 'goal', 'goal_revision', 'revision', 'status', 'blocked_reason', 'task_context', 'messages'}
        optional = {'latest_attempt_id', 'start_available', 'start_unavailable_reason', 'consumed_message_count', 'cancel_requested', 'conversation_mode', 'context_product_refs', 'goal_mode', 'pending_goal_control', 'goal_continuation', 'goal_plan_pending', 'goal_plan', 'goal_step_review', 'goal_followup', 'instruction_queue_available', 'instruction_queue', 'mission_equipment', 'mission_equipment_binding_revision', 'mission_skill'}
        optional.update(('task_state', 'task_decision', 'execution_checkpoint'))
        if (not isinstance(work, dict) or set(work) - fields - optional or not fields <= set(work) or not isinstance(work['goal'], str)
                or not work['goal'].strip() or type(work['revision']) is not int or work['revision'] < 1
                or type(work['goal_revision']) is not int or not 1 <= work['goal_revision'] <= work['revision']
                or work['status'] not in WORK_STATUSES
                or work['blocked_reason'] not in {None, 'execution_unavailable', 'capability_required', 'run_not_open'}
                or not isinstance(work['messages'], list) or not (0 if work.get('conversation_mode') else 1) <= len(work['messages']) <= limits.work_message_count
                or any(not isinstance(message, str) or not message.strip() for message in work['messages'])):
            raise ThreadProtocolError('invalid Work state')
        if 'task_state' in work:
            from .thread_protocol import _identifier
            state = work['task_state']
            if (not isinstance(state, dict)
                    or set(state) - {'business_report', 'business_report_source', 'handoff', 'workflow',
                                     'instruction_command_id', 'unconfirmed_instruction_refs'} != {
                        'schema', 'task', 'revision_ref', 'previous_revision_ref',
                        'execution', 'acceptance', 'open_items'}
                    or state['schema'] != 'capstone-task-state/1'
                    or state['task'] != {'thread_id': snapshot.thread_id, 'work_id': work['work_id']}
                    or state['acceptance'] != 'undecided'):
                raise ThreadProtocolError('invalid task state')
            if 'instruction_command_id' in state:
                _identifier(state['instruction_command_id'], name='task_state.instruction_command_id')
            if 'unconfirmed_instruction_refs' in state:
                refs = state['unconfirmed_instruction_refs']
                if (not isinstance(refs, list) or not 0 < len(refs) <= limits.work_message_count
                        or any(not isinstance(ref, str) for ref in refs)
                        or len(set(refs)) != len(refs)):
                    raise ThreadProtocolError('invalid unconfirmed instruction references')
                for ref in refs:
                    _identifier(ref, name='task_state.unconfirmed_instruction_refs')
            if 'handoff' in state:
                from .task_handoff import parse_task_handoff
                parse_task_handoff(state['handoff'])
            execution = state['execution']
            if (not isinstance(execution, dict) or set(execution) != {'attempt_id', 'turn_id', 'phase'}
                    or execution['attempt_id'] != state['revision_ref']
                    or execution['phase'] not in ('completed', 'failed', 'cancelled', 'interrupted')
                    or state['previous_revision_ref'] == state['revision_ref']):
                raise ThreadProtocolError('invalid task state execution')
            _identifier(state['revision_ref'], name='task_state.revision_ref')
            _identifier(execution['turn_id'], name='task_state.turn_id')
            if state['previous_revision_ref'] is not None:
                _identifier(state['previous_revision_ref'], name='task_state.previous_revision_ref')
            expected_open = [] if execution['phase'] == 'completed' else [
                {'kind': 'execution_incomplete', 'reason': execution['phase']}]
            if state['open_items'] != expected_open:
                raise ThreadProtocolError('invalid task state open items')
            if 'business_report' in state or 'business_report_source' in state:
                if checked_business_report(state.get('business_report')) is None:
                    raise ThreadProtocolError('invalid task state business report')
                _identifier(state.get('business_report_source'), name='task_state.business_report_source')
        if 'task_decision' in work:
            from .thread_protocol import _identifier
            decision = work['task_decision']
            if (not isinstance(decision, dict)
                    or set(decision) != {'command_id', 'decision', 'revision_ref'}
                    or decision['decision'] not in TASK_DECISIONS
                    or decision['revision_ref'] != work.get('task_state', {}).get('revision_ref')):
                raise ThreadProtocolError('invalid task decision receipt')
            _identifier(decision['command_id'], name='task_decision.command_id')
        count = work.get('consumed_message_count', 0)
        if 'goal_followup' in work and (work['goal_followup'] is not True or 'goal_mode' not in work):
            raise ThreadProtocolError('invalid Goal follow-up state')
        if 'mission_equipment' in work:
            import re
            if (not isinstance(work.get('mission_equipment_binding_revision'), str)
                    or re.fullmatch(r'[0-9a-f]{64}', work['mission_equipment_binding_revision']) is None):
                raise ThreadProtocolError('invalid Mission equipment registry revision')
            from .native_mission import checked_equipment
            try:
                checked_equipment(work['mission_equipment'])
            except ValueError as error:
                raise ThreadProtocolError('invalid Mission equipment selection') from error
        if 'instruction_queue_available' in work and type(work['instruction_queue_available']) is not bool:
            raise ThreadProtocolError('invalid instruction availability')
        if 'instruction_queue' in work:
            queue = work['instruction_queue']
            if not isinstance(queue, list) or len(queue) > limits.work_message_count:
                raise ThreadProtocolError('invalid instruction queue bounds')
            from .thread_protocol import _identifier
            seen_instructions, previous_sequence = set(), 0
            for item in queue:
                if (not isinstance(item, dict)
                        or set(item) - {'mode'} != {'id', 'text', 'attempt_id', 'sequence', 'state'}
                        or ('mode' in item and item['mode'] != 'interrupt')
                        or not isinstance(item['text'], str) or not item['text'].strip()
                        or len(item['text']) > limits.input_text_chars
                        or type(item['sequence']) is not int or item['sequence'] <= previous_sequence
                        or not isinstance(item['state'], str)
                        or item['state'] not in {'pending', 'withdrawn', 'delivering', 'admitted', 'delivery_unknown'}):
                    raise ThreadProtocolError('invalid instruction queue entry')
                _identifier(item['id'], name='instruction.id')
                _identifier(item['attempt_id'], name='instruction.attempt_id')
                if item['id'] in seen_instructions:
                    raise ThreadProtocolError('duplicate instruction identity')
                seen_instructions.add(item['id'])
                previous_sequence = item['sequence']
        if 'goal_continuation' in work:
            continuation = work['goal_continuation']
            if (not isinstance(continuation, dict) or set(continuation) - {'product_refs', 'authority_refs', 'authority_model'} != {
                    'predecessor_attempt_id', 'generation', 'next_instruction'}
                    or 'goal_mode' not in work
                    or type(continuation['generation']) is not int
                    or continuation['generation'] != work['goal_mode'].get('generation')
                    or any(not isinstance(continuation[key], str) or not continuation[key].strip()
                           or len(continuation[key]) > limits.input_text_chars
                           for key in ('predecessor_attempt_id', 'next_instruction'))):
                raise ThreadProtocolError('invalid goal continuation')
            if 'product_refs' in continuation:
                from .goal_receipts import validate_goal_product_refs
                try:
                    validate_goal_product_refs(continuation['product_refs'])
                except ValueError as error:
                    raise ThreadProtocolError('invalid goal continuation products') from error
            if ('authority_refs' in continuation) != ('authority_model' in continuation):
                raise ThreadProtocolError('incomplete goal authority selection')
            if 'authority_refs' in continuation:
                from .goal_receipts import validate_goal_authority_refs
                try:
                    validate_goal_authority_refs(continuation['authority_refs'])
                    if continuation['authority_model'] is not None:
                        ModelContextSnapshot.from_document(continuation['authority_model'])
                except ValueError as error:
                    raise ThreadProtocolError('invalid goal continuation authority references') from error
        if 'pending_goal_control' in work:
            from .goal_mode import parse_goal_mode
            pending = work['pending_goal_control']
            try:
                if not isinstance(pending, dict) or set(pending) != {'goal_mode'} or not work.get('cancel_requested'):
                    raise ValueError('invalid pending goal control')
                parse_goal_mode(pending['goal_mode'])
            except ValueError as error:
                raise ThreadProtocolError('invalid pending goal control') from error
        if 'goal_mode' in work:
            from .goal_mode import parse_goal_mode
            try:
                goal = parse_goal_mode(work['goal_mode'])
            except ValueError as error:
                raise ThreadProtocolError('invalid Work goal mode') from error
            if goal['objective'] != work['goal'] or goal['objective_revision'] != work['goal_revision']:
                raise ThreadProtocolError('inconsistent Work goal objective')
        state = work.get('task_state', {})
        if 'workflow' in state and ('goal_mode' not in work or state['workflow'] != goal_task_workflow(work)):
            raise ThreadProtocolError('invalid Goal task workflow')
        if 'context_product_refs' in work:
            refs = checked_work_product_refs(work['context_product_refs'])
            if any(item['ref']['thread_id'] != snapshot.thread_id for item in refs):
                raise ThreadProtocolError('invalid Work product scope')
        if type(count) is not int or not 0 <= count <= len(work['messages']):
            raise ThreadProtocolError('invalid Work message cursor')
        if type(work.get('cancel_requested', False)) is not bool:
            raise ThreadProtocolError('invalid Work cancellation state')
        try:
            context = TaskContext.from_document(work['task_context'])
        except (ValueError, TypeError) as error:
            raise ThreadProtocolError('invalid Work task context') from error
        if (context.binding.thread_id != snapshot.thread_id or context.binding.work_id != work['work_id']
                or context.goal_revision != work['goal_revision'] or work['work_id'] in identities):
            raise ThreadProtocolError('invalid Work context identity')
        identities.add(work['work_id'])
    if (document['selected_model_context_id'] != (None if snapshot.active_model_context is None else snapshot.active_model_context.id)
            or document['task_context'] != (None if not document['works'] else document['works'][-1]['task_context'])
            or snapshot.base_event_seq > snapshot.last_event_seq
            or len(json.dumps(document['works'], ensure_ascii=False).encode()) > limits.work_state_bytes):
        raise ThreadProtocolError('invalid Work snapshot identity or bounds')
    stored = tuple({key: deepcopy(value) for key, value in work.items()
                    if key not in {'start_available', 'start_unavailable_reason',
                                   'instruction_queue_available', 'execution_checkpoint'}} for work in document['works'])
    for work in stored:
        if 'task_state' in work:
            work['task_state'].pop('workflow', None)
    return replace(snapshot, minimum_protocol_version=2, works=stored)
