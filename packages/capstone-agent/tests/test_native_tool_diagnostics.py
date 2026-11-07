from capstone_agent.native_tool_diagnostics import structured_tool_diagnostic
import pytest


@pytest.mark.parametrize('diagnostic,expected,absent', [
    ({'transport_phase': 'connect', 'connection_established': False, 'request_sent': False,
      'result_state': 'not_produced', 'retry_policy': 'after_connection_restored'},
     ['连接阶段失败', '连接未建立', '请求未发送', '未生成结果', '先恢复连接'], ['已取消', '无数据']),
    ({'transport_phase': 'send', 'request_sent': None, 'remote_execution_possible': True,
      'result_state': 'unknown', 'remote_cancellation_confirmed': False},
     ['发送阶段失败', '发送状态未知', '源端结果未知', '不可自动重放'], ['未执行', '已取消', '无数据']),
    ({'transport_phase': 'receive', 'request_sent': True, 'result_state': 'unknown'},
     ['等待响应阶段失败', '请求已发送', '源端结果未知', '不可自动重放'], ['未执行', '已取消']),
])
def test_transport_failure_summary_keeps_uncertainty_and_next_step(diagnostic, expected, absent):
    value = {'status': 'error', 'gaps': [{'reason': 'source_unavailable', 'message': 'Provider unavailable'}],
             'provenance': {'request_id': 'request-1', 'execution_diagnostics': diagnostic}}
    output = structured_tool_diagnostic({'content': [{'type': 'text', 'text': __import__('json').dumps(value)}]})
    for text in expected:
        assert text in output
    for text in absent:
        assert text not in output
    assert 'request-1' in output


def test_failure_summary_uses_only_declared_diagnostics_not_business_rows():
    value = {'status': 'error', 'gaps': [{'message': 'Outer failure'}],
             'data': [{'transport_phase': 'connect', 'request_sent': False}]}
    assert structured_tool_diagnostic(value) == 'Outer failure'


def test_batch_failure_uses_selected_child_and_keeps_parent_request():
    result = {'status': 'error', 'provenance': {'request_id': 'parent'},
              'gaps': [{'message': 'See subquery', 'scope': {'query_index': 1}}],
              'data': [{'result': {'status': 'error', 'error': {'message': 'wrong child'}}},
                       {'result': {'status': 'error', 'gaps': [
                           {'reason': 'ambiguous_data_source', 'message': 'Select source_id explicitly'}]}}]}
    summary = structured_tool_diagnostic(result)
    assert 'Select source_id explicitly' in summary
    assert 'ambiguous_data_source' in summary
    assert 'parent' in summary
    assert 'wrong child' not in summary
    assert result['gaps'][0]['message'] == 'See subquery'


def test_successful_business_rows_are_not_treated_as_nested_errors():
    result = {'status': 'error', 'gaps': [{'message': 'Outer failure', 'scope': {'query_index': 0}}],
              'data': [{'result': {'status': 'success', 'error': {'message': 'business text'}}}]}
    assert structured_tool_diagnostic(result) == 'Outer failure'


def test_invalid_subquery_index_keeps_outer_diagnostic():
    for index in (-1, 3, True, '0'):
        result = {'status': 'error', 'gaps': [{'message': 'Outer failure', 'scope': {'query_index': index}}],
                  'data': []}
        assert structured_tool_diagnostic(result) == 'Outer failure'
