from types import SimpleNamespace
from threading import Event, RLock

import pytest

from capstone_agent.general_pi_server import GeneralPiHost
from capstone_agent.native_execution_authority import ExecutionAuthority, SCHEMA


def test_native_instruction_owner_retry_and_cancellation():
    host = object.__new__(GeneralPiHost)
    host._lock = RLock()
    authority = {'schema': SCHEMA, 'generation': 'a' * 64, 'capability': 'b' * 64}
    record = {'request': SimpleNamespace(parent_attempt_id='attempt-1'), 'status': 'running',
              'cancel': Event(), 'execution_authority': ExecutionAuthority('a' * 64, 'b' * 64, 30)}
    host._tasks = {'task-1': record}
    document = {'parent_attempt_id': 'attempt-1', 'instruction_id': 'instruction-1',
                'text': 'Use the saved result', 'execution_authority': authority}
    assert host.submit_instruction('task-1', document) == {'instruction_id': 'instruction-1', 'state': 'queued'}
    assert host.submit_instruction('task-1', document)['state'] == 'queued'
    assert len(host.take_instructions('task-1')) == 1
    assert host.take_instructions('task-1') == []
    with pytest.raises(ValueError):
        host.submit_instruction('task-1', {**document, 'text': 'changed'})
    with pytest.raises(PermissionError):
        host.submit_instruction('task-1', {**document, 'parent_attempt_id': 'wrong'})
    record['cancel'].set()
    with pytest.raises(PermissionError):
        host.submit_instruction('task-1', document)


def test_instruction_capability_requires_runner_transport_support(tmp_path):
    from capstone_agent.application_capacity import limits
    def unsupported(*args):
        raise AssertionError('not executed')
    host = GeneralPiHost(root=tmp_path / 'unsupported', identity={}, run_task=unsupported)
    assert 'instruction_schemas' not in host.capability
    unsupported.instruction_transport = True
    host = GeneralPiHost(root=tmp_path / 'supported', identity={}, run_task=unsupported)
    assert host.capability['instruction_schemas'] == ['capstone-native-instruction/1']
    assert host.capability['instruction_limit'] == limits.native_instruction_count
