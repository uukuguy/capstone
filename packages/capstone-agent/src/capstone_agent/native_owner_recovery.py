"""Observe a native child after parent contact is delayed, without dispatching work."""
from hashlib import sha256
import logging

from .native_failure_origin import native_failure_origin


def observe_lost_contact(service, executor) -> int:
    read_terminal = getattr(executor, 'observe_terminal_task', None)
    if not callable(read_terminal):
        return 0
    recorded = 0
    for candidate in service.native_recovery_candidates():
        binding = candidate['binding']
        attempt_id = candidate['attempt_id']
        expected_task = 'pi-' + sha256((attempt_id + '\0conversation').encode()).hexdigest()
        if binding.get('task_id') != expected_task or binding.get('parent_attempt_id') != attempt_id:
            continue
        try:
            terminal = read_terminal(expected_task, attempt_id, binding['executor_identity'])
            status = 'unknown' if terminal is None else terminal.status
        except Exception as error:
            logging.getLogger(__name__).warning(
                'Native recovery lookup unavailable; attempt_id=%s exception_type=%s origin=%s',
                attempt_id, type(error).__name__, native_failure_origin(error))
            status = 'unknown'
        if status not in {'completed', 'failed', 'cancelled'}:
            status = 'unknown'
        recorded += service.record_native_recovery_observation(candidate, status)
    return recorded
