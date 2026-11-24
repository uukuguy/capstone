from capstone_agent.query_delivery import answer_with_query_deliveries


def _delivery():
    evidence = 'evidence:sha256:' + 'ab' * 32
    return {'schema': 'capstone-query-delivery/1',
            'result_ref': 'result:sha256:' + 'cd' * 32,
            'dataset': 'result.res_bus',
            'columns': [{'name': 'index'}, {'name': 'vm_pu', 'unit': 'p.u.'}],
            'rows': [{'index': 2, 'vm_pu': 1.01}, {'index': 3, 'vm_pu': 1.0177}, {'index': 4, 'vm_pu': 1.0195}],
            'row_count': 3, 'returned_row_count': 3, 'offset': 0, 'next_offset': None,
            'evidence_refs': [evidence]}


def test_answer_uses_admitted_rows_in_order_and_drops_the_model_table():
    delivery = _delivery()
    answer = answer_with_query_deliveries(
        '三行均高于 0.95。\n\n| 母线 | 电压 |\n| --- | --- |\n| 2 | 1.0100 |n| 3 | 1.0177 |',
        [delivery])
    assert answer.startswith('三行均高于 0.95。')
    assert '|n|' not in answer
    assert '| index | vm_pu (p.u.) |' in answer
    assert answer.index('| 2 | 1.01 |') < answer.index('| 3 | 1.0177 |') < answer.index('| 4 | 1.0195 |')
    assert answer.endswith('证据：' + delivery['evidence_refs'][0])
    assert answer_with_query_deliveries('保留原文', [{'schema': 'other'}]) == '保留原文'
