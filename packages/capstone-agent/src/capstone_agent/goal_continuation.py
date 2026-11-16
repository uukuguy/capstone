"""Build deterministic commands from durable next-step intent."""
from hashlib import sha256


def continuation_command(thread_id: str, work: dict) -> dict | None:
    goal, pending = work.get('goal_mode'), work.get('goal_continuation')
    if (not goal or not pending or goal['state'] != 'ready'
            or goal['generation'] != pending['generation']):
        return None
    identity = sha256(f"{thread_id}:{work['work_id']}:{pending['generation']}:"
                      f"{pending['predecessor_attempt_id']}:{work['revision']}".encode()).hexdigest()[:32]
    return {'schema': 'capstone-command/2', 'command_id': 'cmd_goal_' + identity,
        'idempotency_key': 'goal_' + identity, 'thread_id': thread_id,
        'kind': 'continue_goal', 'target': {'kind': 'work', 'id': work['work_id'],
        'expected_revision': work['revision']}, 'payload': {
            'predecessor_attempt_id': pending['predecessor_attempt_id'],
            'generation': pending['generation']}}
