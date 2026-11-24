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


def test_result_readers_use_only_the_names_published_by_the_pack(tmp_path):
    service = PandapowerToolService(workspace_root=tmp_path)
    service._capabilities = {
        'actual_list': 'result.dataset.list',
        'actual_query': 'result.dataset.query',
    }
    tools = service.result_read_guidance()
    assert 'actual_list' in tools
    assert 'actual_query' in tools
    assert 'result_ref' in tools
    assert 'evidence_refs' in tools
    service._capabilities = {'actual_list': 'result.dataset.list'}
    assert service.result_read_guidance() is None


def test_model_result_views_keep_evidence_and_index_datasets_without_field_lists(tmp_path):
    service = PandapowerToolService(workspace_root=tmp_path)
    datasets = [
        {'dataset': 'result.res_bus', 'row_count': 14, 'available_fields': ['vm_pu']},
        {'dataset': 'result.res_empty', 'row_count': 0, 'available_fields': ['unused']},
    ]
    result = {'result_ref': 'result', 'evidence_refs': ['evidence'], 'converged': True, 'datasets': datasets}
    solving = service.model_result('analysis.powerflow.ac.run', result)
    assert solving['evidence_refs'] == ['evidence']
    assert solving['converged'] is True
    assert 'datasets' not in solving
    listing = service.model_result('result.dataset.list', result)
    assert listing['datasets'] == [{'dataset': 'result.res_bus', 'row_count': 14}]
    assert listing['empty_datasets'] == ['result.res_empty']
    assert service.model_result('result.dataset.query', result) is None
    assert result['datasets'][0]['available_fields'] == ['vm_pu']


def test_open_model_view_keeps_revision_and_offers_read_back_for_overview(tmp_path):
    service = PandapowerToolService(workspace_root=tmp_path)
    service._capabilities = {'published_read': 'context.get'}
    result = {'context_ref': 'context', 'revision_ref': 'revision', 'counts': {'buses': 14},
              'overview': [{'dataset': 'network.bus', 'row_count': 14, 'aggregates': [{'value': 110}]}]}
    view = service.model_result('context.open', result)
    assert view['context_ref'] == 'context'
    assert view['revision_ref'] == 'revision'
    assert view['counts'] == {'buses': 14}
    assert 'overview' not in view
    assert view['overview_read']['tool'] == 'published_read'
    assert view['overview_read']['arguments'] == {'context_ref': 'context', 'include_overview': True}
    assert service.model_result('context.get', result) is None


def test_model_guidance_passes_exact_refs_and_only_offers_available_voltage_fields(tmp_path):
    service = PandapowerToolService(workspace_root=tmp_path)
    service._capabilities = {
        'published_ac': 'analysis.powerflow.ac.run',
        'published_query': 'result.dataset.query',
    }
    opened = service.model_guidance('context.open', {'context_ref': 'actual-context'})
    assert 'published_ac' in opened and 'actual-context' in opened
    assert 'omit solver overrides' in opened
    solved = {'result_ref': 'actual-result', 'datasets': [
        {'dataset': 'result.res_bus', 'row_count': 14, 'available_fields': ['index', 'vm_pu']},
    ]}
    guidance = service.model_guidance('analysis.powerflow.ac.run', solved)
    assert 'published_query' in guidance and 'actual-result' in guidance
    assert 'vm_pu' in guidance and 'ascending' in guidance
    assert service.model_guidance('result.dataset.list', solved) is None
    solved['datasets'][0]['available_fields'] = ['index']
    assert service.model_guidance('analysis.powerflow.ac.run', solved) is None


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
