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


def test_query_delivery_keeps_returned_order_stored_units_and_evidence(tmp_path):
    service = PandapowerToolService(workspace_root=tmp_path)
    evidence = 'evidence:sha256:' + 'ab' * 32
    result_ref = 'result:sha256:' + 'cd' * 32

    class Stored:
        document = {'datasets': {'result.res_bus': {'fields': [
            {'name': 'index', 'unit': None},
            {'name': 'vm_pu', 'unit': 'p.u.'},
        ]}}}

    class Authority:
        def verify_result(self, ref):
            assert ref == result_ref
            return Stored()

    result = {'result_ref': result_ref, 'dataset': 'result.res_bus', 'row_count': 3,
              'returned_row_count': 3, 'offset': 0, 'next_offset': None,
              'rows': [{'index': 2, 'vm_pu': 1.01}, {'index': 4, 'vm_pu': 1.0195}, {'index': 3, 'vm_pu': 1.0177}]}
    arguments = {'select': ['index', 'vm_pu']}
    delivery = service.query_delivery(result, arguments, Authority(), [evidence])
    assert [row['index'] for row in delivery['rows']] == [2, 4, 3]
    assert [row['vm_pu'] for row in delivery['rows']] == [1.01, 1.0195, 1.0177]
    assert delivery['columns'] == [{'name': 'index'}, {'name': 'vm_pu', 'unit': 'p.u.'}]
    assert delivery['evidence_refs'] == [evidence]
    assert 'p.u.' not in json.dumps(result['rows'])
    result['rows'] = [{'index': 2, 'vm_pu': 1.01, 'extra': 1}]
    assert service.query_delivery(result, arguments, Authority(), [evidence]) is None
