"""Build deterministic commands from durable next-step intent."""
from hashlib import sha256


def drain_goal_continuations(service, limit: int = 32) -> int:
    admitted = 0
    for thread_id in service.goal_continuation_candidates(limit):
        snapshot = service.snapshot(thread_id)
        if snapshot.current_attempt is not None:
            continue
        for work in snapshot.works:
            command = continuation_command(thread_id, work)
            if command is not None:
                submit = getattr(service, 'submit_goal_continuation', service.submit_command)
                receipt = submit(command)
                if receipt is None:
                    continue
                admitted += receipt.status == 'accepted'
                if receipt.status == 'rejected' and receipt.rejection != 'revision_conflict':
                    reason = receipt.rejection or 'unavailable'
                    record = getattr(service, 'submit_initial_goal_plan', None)
                    if callable(record):
                        record({'schema': 'capstone-command/2', 'thread_id': thread_id,
                            'command_id': 'cmd_failure_' + command['command_id'],
                            'idempotency_key': 'failure_' + command['idempotency_key'],
                            'kind': 'fail_goal_continuation',
                            'target': command['target'], 'payload': {'reason': reason}})
                break
    return admitted


def continuation_command(thread_id: str, work: dict) -> dict | None:
    goal, pending = work.get('goal_mode'), work.get('goal_continuation')
    if (not goal or not pending or goal['state'] != 'ready'
            or goal['generation'] != pending['generation']):
        return None
    identity = sha256(f"independent-product-bindings:{thread_id}:{work['work_id']}:{pending['generation']}:"
                      f"{pending['predecessor_attempt_id']}:{work['revision']}".encode()).hexdigest()[:32]
    return {'schema': 'capstone-command/2', 'command_id': 'cmd_goal_' + identity,
        'idempotency_key': 'goal_' + identity, 'thread_id': thread_id,
        'kind': 'continue_goal', 'target': {'kind': 'work', 'id': work['work_id'],
        'expected_revision': work['revision']}, 'payload': {
            'predecessor_attempt_id': pending['predecessor_attempt_id'],
            'generation': pending['generation']}}
