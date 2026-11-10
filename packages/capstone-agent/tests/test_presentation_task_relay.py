from threading import Thread
from types import SimpleNamespace
import time

import httpx

from capstone_agent.general_pi_relay import ProviderRelay
from capstone_agent.general_pi_server import GeneralPiHost, make_server


def test_template_tool_publication_requires_the_exact_application_contract():
    from capstone_agent.native_task_context import native_context_for
    from capstone_agent.presentation_template_contract import PRESENTATION_LIBRARY_CAPABILITY
    from test_research_policy_compatibility import registered_binding
    binding = registered_binding('1.9.0')
    binding['capability']['native_builtin_tools'] = ['bash', 'write', 'read']
    claim = SimpleNamespace(submission=None, selected_task_reader=None)
    assert 'agent_presentations' not in native_context_for(claim, binding)['policy']['allowed_tools']
    binding['capability']['presentation_library'] = dict(PRESENTATION_LIBRARY_CAPABILITY)
    assert 'agent_presentations' in native_context_for(claim, binding)['policy']['allowed_tools']
    binding['capability']['presentation_library']['schema'] = 'unknown/2'
    assert 'agent_presentations' not in native_context_for(claim, binding)['policy']['allowed_tools']


def test_private_template_adapter_uses_only_live_host_bound_task_scope(tmp_path):
    calls = []
    port = SimpleNamespace(task_id='task-one', client=SimpleNamespace(workspace='enterprise', thread_id='thr_one'),
                           invoke=lambda operation, document, call_id: calls.append((operation, document, call_id)) or {'catalog': True})
    relay = ProviderRelay()
    runner = SimpleNamespace(relay=relay, task_presentations={'task-one': port})
    host = GeneralPiHost(root=tmp_path, identity={'engine': 'pi'}, run_task=lambda *_: ('ok', {}))
    request = SimpleNamespace(managed_workspace='enterprise', business_context=SimpleNamespace(
        to_document=lambda: {'workspace_id': 'thr_one'}))
    host._tasks['task-one'] = {'request': request, 'status': 'running'}
    server = make_server(host, control_token='control', address=('127.0.0.1', 0), runner=runner)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    relay.register('task-one', 'grant', time.monotonic()+30)
    base = f'http://127.0.0.1:{server.server_port}/presentation-template-tasks/task-one'
    body = {'call_id': 'call-one', 'operation': 'catalog', 'document': {}}
    try:
        with httpx.Client(timeout=5, trust_env=False) as client:
            assert client.post(base, json=body).status_code == 401
            headers = {'Authorization': 'Bearer grant'}
            response = client.post(base, headers=headers, json=body)
            assert response.status_code == 200
            assert response.json() == {'ok': True, 'result': {'catalog': True}}
            assert calls == [('catalog', {}, 'call-one')]
            assert client.post(base, headers=headers, json={**body, 'workspace': 'other'}).status_code == 400
            request.managed_workspace = 'other'
            assert client.post(base, headers=headers, json=body).status_code == 403
            request.managed_workspace = 'enterprise'
            host._tasks['task-one']['status'] = 'completed'
            assert client.post(base, headers=headers, json=body).status_code == 409
            assert len(calls) == 1
    finally:
        relay.revoke('task-one')
        server.shutdown(); server.server_close(); thread.join(timeout=1)
