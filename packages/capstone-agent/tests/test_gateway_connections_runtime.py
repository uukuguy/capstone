import json


def test_runtime_seeds_are_private_and_existing_selection_wins(tmp_path, monkeypatch):
    from capstone_agent import gateway_connections_runtime as runtime
    private = tmp_path / 'private'
    private.mkdir(mode=0o700)
    directory = private / 'data-gateway'
    directory.mkdir(mode=0o700)
    connection = {'name': 'Local', 'transport': 'streamable-http', 'url': 'http://localhost:18001/mcp',
                  'headers': {'Authorization': 'Bearer private-example-token'}}
    config = directory / 'connection.json'
    config.write_text(json.dumps(connection))
    config.chmod(0o600)
    policy = tmp_path / 'policy.json'
    policy.write_text('{}')
    calls = []

    class Registry:
        current_access = None
        def __init__(self, root, policy, *, seeds, transport_host):
            assert seeds[0]['connection'] == connection
            assert transport_host == 'host.docker.internal'
        def snapshot(self):
            return {'selected_id': 'previous-user-selection'}
        def prepare_selected(self):
            calls.append('restore')
        def select(self, _):
            raise AssertionError('must preserve persisted selection')
        def start(self):
            calls.append('background')

    monkeypatch.setattr(runtime, 'GatewayConnectionRegistry', Registry)
    registry, access, publication = runtime.load_gateway_connections(config, policy, tmp_path / 'state',
        private_root=private, owner_uid=private.stat().st_uid, transport_host='host.docker.internal')
    assert registry is not None and access is None and publication['available'] is False
    assert calls == ['restore', 'background']
    config.chmod(0o644)
    assert runtime.load_gateway_connections(config, policy, tmp_path / 'bad', private_root=private,
        owner_uid=private.stat().st_uid)[0] is None
