from capstone_agent.native_tool_diagnostics import structured_tool_diagnostic


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
