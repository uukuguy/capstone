import json
import time

import pytest

from capstone_agent.general_pi_server import GeneralPiHost
from capstone_agent.pi_delegation import PiTaskRequest
from capstone_agent.failure_delivery import NATIVE_FAILURE_REASONS


@pytest.mark.parametrize('reason', [
    'session_skill_content_changed', 'session_skill_content_unavailable', 'session_skill_unavailable',
])
def test_native_skill_failure_is_specific_and_keeps_saved_products(tmp_path, reason):
    saved = tmp_path / 'existing.csv'
    saved.write_text('name,value\nalpha,7\n')
    def fail(request, *_):
        if request.instruction == 'Recover':
            return 'Recovered', {}
        raise ValueError(reason)
    host = GeneralPiHost(root=tmp_path, identity={'engine': 'pi'}, run_task=fail)
    request = PiTaskRequest('task-skill-recovery', 'attempt', 'direct', 'Explain', (), (), host.identity, 2)
    host.submit(request)
    deadline = time.monotonic() + 3
    while host.read(request.task_id)['status'] == 'running' and time.monotonic() < deadline:
        time.sleep(.01)
    result = host.read(request.task_id)['result']
    assert result['failure']['code'] == 'native_' + reason
    assert NATIVE_FAILURE_REASONS[result['failure']['code']]
    assert saved.read_text() == 'name,value\nalpha,7\n'
    record = json.loads((tmp_path / 'receipts/failures/task-skill-recovery.json').read_text())
    assert record['reason_code'] == reason
    recovered = PiTaskRequest('task-skill-recovered', 'attempt-recovered', 'direct', 'Recover', (), (), host.identity, 2)
    host.submit(recovered)
    deadline = time.monotonic() + 3
    while host.read(recovered.task_id)['status'] == 'running' and time.monotonic() < deadline:
        time.sleep(.01)
    assert host.read(recovered.task_id)['result']['status'] == 'completed'
    assert saved.read_text() == 'name,value\nalpha,7\n'


def test_unregistered_skill_exception_stays_private(tmp_path):
    def fail(*_):
        raise ValueError('session_skill_content_changed PRIVATE_SENSITIVE_MESSAGE')
    host = GeneralPiHost(root=tmp_path, identity={'engine': 'pi'}, run_task=fail)
    request = PiTaskRequest('task-private-skill', 'attempt', 'direct', 'Explain', (), (), host.identity, 2)
    host.submit(request)
    deadline = time.monotonic() + 3
    while host.read(request.task_id)['status'] == 'running' and time.monotonic() < deadline:
        time.sleep(.01)
    public = host.read(request.task_id)['result']
    assert public['failure']['code'] == 'native_execution_error'
    assert 'PRIVATE_SENSITIVE_MESSAGE' not in json.dumps(public)
