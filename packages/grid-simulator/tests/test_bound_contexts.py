from grid_simulator.operations import dispatch
from grid_simulator.protocol import GridCapabilityRequest
import io
import json

from grid_simulator.cli import main


def request(capability, **arguments):
    return GridCapabilityRequest(protocol='grid-capability', protocol_version='1.0',
                                 request_id='scope-test', capability=capability, arguments=arguments)


def test_bound_scope_allows_child_calculation_and_rejects_foreign_context(tmp_path):
    base = dispatch(request('context.open', model_id='ieee39'), tmp_path).result
    foreign = dispatch(request('context.open', model_id='case9'), tmp_path).result
    child = dispatch(request('model.revision.derive', context_ref=base['context_ref'],
        patches=[{'operation': 'in_service', 'kind': 'gen',
                  'selector': {'indices': [0]}, 'value': False}]), tmp_path).result
    assert child is not None
    response = dispatch(request('context.get', context_ref=child['context_ref']), tmp_path,
                        bound_context_ref=base['context_ref'])
    assert response.ok
    rejected = dispatch(request('context.get', context_ref=foreign['context_ref']), tmp_path,
                        bound_context_ref=base['context_ref'])
    assert not rejected.ok
    assert rejected.error.code == 'model_scope_mismatch'


def test_bound_scope_rejects_opening_another_registered_model(tmp_path):
    base = dispatch(request('context.open', model_id='ieee39'), tmp_path).result
    response = dispatch(request('context.open', model_id='case9'), tmp_path,
                        bound_context_ref=base['context_ref'])
    assert not response.ok
    assert response.error.code == 'model_scope_mismatch'


def test_cli_enforces_private_scope_and_rejects_linked_scope(tmp_path, monkeypatch, capsys):
    base = dispatch(request('context.open', model_id='ieee39'), tmp_path).result
    scope = tmp_path / 'thread-model-scope.json'
    scope.write_text(json.dumps({'schema': 'grid-thread-model-scope/1', 'base_context_ref': base['context_ref']}))
    payload = request('context.open', model_id='case9').model_dump_json()
    monkeypatch.setattr('sys.stdin', io.StringIO(payload))
    assert main(['request', '--workspace', str(tmp_path)]) == 0
    response = json.loads(capsys.readouterr().out)
    assert response['error']['code'] == 'model_scope_mismatch'
    scope.unlink()
    secret = tmp_path / 'secret'
    secret.write_text('SECRET')
    scope.symlink_to(secret)
    monkeypatch.setattr('sys.stdin', io.StringIO(payload))
    assert main(['request', '--workspace', str(tmp_path)]) == 0
    output = capsys.readouterr().out
    assert json.loads(output)['error']['code'] == 'model_scope_invalid'
    assert 'SECRET' not in output
