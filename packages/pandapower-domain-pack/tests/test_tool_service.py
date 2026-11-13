"""Published tools execute in the Pack with an application-selected workspace."""
import json

import pytest

from pandapower_domain.tool_service import PandapowerToolService


def test_pack_service_uses_explicit_workspace_and_keeps_owner_receipt(tmp_path):
    service = PandapowerToolService(workspace_root=tmp_path)
    service._capabilities = {'published': 'analysis.example'}
    service._read_only = {'published': True}
    class Executor:
        def invoke(self, capability, arguments, *, execution_observer, execution_lease):
            assert capability == 'analysis.example'
            assert arguments == {'value': 3}
            execution_observer('execution_started')
            execution_observer('execution_ended')
            return {'value': 3}
    service._executors['selected-model'] = Executor()
    result = service.invoke({'task_id': 'task-one', 'call_id': 'call-one',
        'name': 'published', 'arguments': {'value': 3}}, workspace_id='selected-model')
    assert result['ok'] and result['result'] == {'value': 3}
    assert result['execution_receipt']['events'][-1]['phase'] == 'released'
    saved, = (tmp_path/'task-one'/'execution-receipts').glob('*.json')
    assert json.loads(saved.read_text())['call_id'] == 'call-one'


@pytest.mark.parametrize('workspace', ['../escape', '/absolute', '', None, 'x'*81])
def test_pack_service_rejects_unsafe_workspace_before_storage(tmp_path, workspace):
    service = PandapowerToolService(workspace_root=tmp_path)
    with pytest.raises(ValueError, match='workspace'):
        service.invoke({'task_id':'task', 'call_id':'call', 'name':'unpublished',
                        'arguments':{}}, workspace_id=workspace)
    assert list(tmp_path.iterdir()) == []
