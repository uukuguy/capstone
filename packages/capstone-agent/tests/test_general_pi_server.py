from pathlib import Path
import threading
import time

import httpx

from capstone_agent.pi_delegation import PiTaskRequest, HttpGeneralPiExecutor
from capstone_agent.request_intent import NodeControl


def test_executor_service_binds_identity_and_control_authorization(tmp_path):
    from capstone_agent.general_pi_server import GeneralPiHost, make_server
    host = GeneralPiHost(root=tmp_path, identity={'engine': 'pi', 'config_revision': 'test'},
                         run_task=lambda request, cancelled, emit: ('General answer', {}))
    server = make_server(host, control_token='host-secret', address=('127.0.0.1', 0))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f'http://127.0.0.1:{server.server_port}'
    try:
        assert httpx.get(origin + '/health/ready').status_code == 200
        assert httpx.post(origin + '/tasks', json={}).status_code == 401
        client = HttpGeneralPiExecutor(origin, identity=host.identity, capability=host.capability,
                                      control_token='host-secret')
        request = PiTaskRequest.from_document({'schema': 'capstone-pi-task/1', 'task_id': 't1',
            'parent_attempt_id': 'a1', 'entrypoint': 'direct', 'instruction': 'Explain', 'messages': [],
            'dependency_results': [], 'executor_identity': host.identity, 'timeout_seconds': 2})
        result = client.execute(request, NodeControl(lambda: None, time.monotonic()+2), lambda _: None)
        assert result.answer == 'General answer'
        assert result.status == 'completed'
        assert list(tmp_path.glob('receipts/*.json'))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_cancel_service_stops_child_and_duplicate_tasks_do_not_repeat_actions(tmp_path):
    from capstone_agent.general_pi_server import GeneralPiHost
    calls = []
    def run(request, cancelled, emit):
        calls.append(request.task_id)
        while not cancelled():
            time.sleep(0.01)
        raise InterruptedError()
    host = GeneralPiHost(root=tmp_path, identity={'engine': 'pi'}, run_task=run)
    request = PiTaskRequest.from_document({'schema': 'capstone-pi-task/1', 'task_id': 't1',
        'parent_attempt_id': 'a1', 'entrypoint': 'delegated', 'instruction': 'Explain', 'messages': [],
        'dependency_results': [], 'executor_identity': host.identity, 'timeout_seconds': 2})
    host.submit(request)
    host.submit(request)
    host.cancel('t1')
    deadline = time.monotonic()+2
    while host.read('t1')['status'] in {'queued', 'running'} and time.monotonic() < deadline:
        time.sleep(0.01)
    assert calls == ['t1']
    assert host.read('t1')['result']['status'] == 'cancelled'


def test_service_restart_replays_receipt_without_repeating_work(tmp_path):
    from capstone_agent.general_pi_server import GeneralPiHost
    request = PiTaskRequest.from_document({'schema': 'capstone-pi-task/1', 'task_id': 't1',
        'parent_attempt_id': 'a1', 'entrypoint': 'delegated', 'instruction': 'Explain', 'messages': [],
        'dependency_results': [], 'executor_identity': {'engine': 'pi'}, 'timeout_seconds': 2})
    host = GeneralPiHost(root=tmp_path, identity={'engine': 'pi'},
                         run_task=lambda *_: ('Saved answer', {}))
    host.submit(request)
    deadline = time.monotonic()+2
    while host.read('t1')['status'] == 'running' and time.monotonic() < deadline:
        time.sleep(0.01)
    restarted = GeneralPiHost(root=tmp_path, identity={'engine': 'pi'},
        run_task=lambda *_: (_ for _ in ()).throw(AssertionError('repeated work')))
    restarted.submit(request)
    assert restarted.read('t1')['result']['answer'] == 'Saved answer'


def test_sources_reference_actual_host_observed_tool_results(tmp_path):
    from capstone_agent.general_pi_server import GeneralPiHost
    def run(request, cancelled, emit):
        emit({'type': 'tool_execution_end', 'toolName': 'bash', 'toolCallId': 'call-1',
              'result': {'content': [{'type': 'text', 'text': 'Observed output'}]}})
        return 'Answer', {}
    host = GeneralPiHost(root=tmp_path, identity={'engine': 'pi'}, run_task=run)
    request = PiTaskRequest.from_document({'schema': 'capstone-pi-task/1', 'task_id': 't1',
        'parent_attempt_id': 'a1', 'entrypoint': 'direct', 'instruction': 'Explain', 'messages': [],
        'dependency_results': [], 'executor_identity': host.identity, 'timeout_seconds': 2})
    host.submit(request)
    deadline = time.monotonic()+2
    while host.read('t1')['status'] == 'running' and time.monotonic() < deadline:
        time.sleep(0.01)
    sources = host.read('t1')['result']['sources']
    assert len(sources) == 1
    assert sources[0]['kind'] == 'native_tool_observation'
    assert sources[0]['task_id'] == 't1'
    assert sources[0]['metadata']['tool_name'] == 'bash'
    assert list((tmp_path / 'receipts').glob('t1-observation-*.json'))
