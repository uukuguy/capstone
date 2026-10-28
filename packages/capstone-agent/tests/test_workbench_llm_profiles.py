import pytest
from capstone_agent.workbench_llm_profiles import ProfileRegistry


def test_defaults_and_public_catalog_hide_credentials():
    registry = ProfileRegistry(environment={'DEEPSEEK_API_KEY': 'private'})
    public = registry.catalog()
    assert public['default_profile_id'] == 'commercial-deepseek-flash'
    assert 'private' not in str(public)
    assert 'base_url' not in str(public)
    assert ProfileRegistry(environment={'CAPSTONE_WORKBENCH_PRESET': 'intranet'}).catalog()['default_profile_id'] == 'intranet-dsv4-18804'


def test_frozen_selection_rejects_changed_identity_and_unknown_profiles():
    registry = ProfileRegistry(environment={})
    selected = registry.freeze('intranet-dsv4-18804')
    assert registry.resolve(selected)['model'] == 'dsv4'
    assert registry.resolve(selected)['network'] == 'direct'
    with pytest.raises(ValueError):
        registry.resolve({**selected, 'model': 'other'})
    with pytest.raises(ValueError):
        registry.freeze('https://caller.example')
    with pytest.raises(ValueError):
        registry.freeze('configured-openai-compatible')


def test_public_submission_freezes_only_registered_identity():
    from capstone_agent.thread_input import validate_submission
    payload = {'text': 'hello', 'input': {'kind': 'text', 'text': 'hello'}, 'llm_profile_id': 'intranet-dsv4-18804'}
    result = validate_submission(payload, mode='capstone', objects=[])
    assert result['llm_selection']['model'] == 'dsv4'
    assert set(result['llm_selection']) == {'profile_id', 'provider', 'model', 'profile_revision'}
    payload['llm_profile_id'] = 'intranet-qwen-8011'
    assert result['llm_selection']['model'] == 'dsv4'


def test_task_relay_routes_frozen_profile_instead_of_runner_default(tmp_path):
    import json
    import threading
    import time
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from types import SimpleNamespace
    import httpx
    from capstone_agent.general_pi_relay import ProviderRelay
    from capstone_agent.general_pi_server import GeneralPiHost, make_server
    seen = []
    class Upstream(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_POST(self):
            seen.append((self.headers.get('Authorization'), json.loads(self.rfile.read(int(self.headers['Content-Length'])))))
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"choices":[]}')
    upstream = ThreadingHTTPServer(('127.0.0.1', 0), Upstream)
    relay = ProviderRelay()
    relay.register('task', 'grant', time.monotonic() + 10)
    host = GeneralPiHost(root=tmp_path, identity={'engine': 'pi'}, run_task=lambda *_: ('unused', {}))
    server = make_server(host, control_token='control', address=('127.0.0.1', 0),
        runner=SimpleNamespace(relay=relay, model='old-model', task_llm_profiles={'task': {
            'model': 'selected-model', 'base_url': f'http://127.0.0.1:{upstream.server_port}', 'key': 'selected-key'}}),
        upstream='http://127.0.0.1:1', provider_key='wrong-key')
    for item in (server, upstream):
        threading.Thread(target=item.serve_forever, daemon=True).start()
    try:
        response = httpx.post(f'http://127.0.0.1:{server.server_port}/provider/task/chat/completions',
            json={'model': 'selected-model'}, headers={'Authorization': 'Bearer grant'}, timeout=5, trust_env=False)
        assert response.status_code == 200
        assert seen == [('Bearer selected-key', {'model': 'selected-model'})]
    finally:
        relay.revoke('task')
        for item in (server, upstream):
            item.shutdown()
            item.server_close()
