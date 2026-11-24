import json
from pathlib import Path

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


def test_general_pi_image_copies_query_delivery():
    image = (Path(__file__).resolve().parents[3] / 'deploy/general-pi.Dockerfile').read_text()
    assert 'packages/capstone-agent/src/capstone_agent/query_delivery.py' in image


def test_formal_answer_bundle_keeps_admitted_table_inside_answer():
    delivery = _delivery()
    evidence = delivery['evidence_refs'].pop()
    bundle = {'answer': '结果如下。\n| 模型表 |\n| --- |\n| 草稿 |',
              'summary': '查询已完成。', 'task_state_report': {'status': 'complete'}}
    amended = json.loads(answer_with_query_deliveries(
        json.dumps(bundle), [delivery], answer_format='formal-and-core/1',
        authority_receipts=[{'result_refs': [delivery['result_ref']], 'evidence_refs': [evidence]}]))
    assert amended == {**bundle, 'answer': '结果如下。\n\n'
                       '| index | vm_pu (p.u.) |\n| --- | --- |\n'
                       '| 2 | 1.01 |\n| 3 | 1.0177 |\n| 4 | 1.0195 |\n\n证据：' + evidence}


def test_formal_answer_fallback_still_replaces_model_table():
    for answer in ('结果如下。\n| 模型表 |\n| --- |\n| 草稿 |',
                   '```json\n{"answer":"结果如下。\\n| 模型表 |\\n| --- |","summary":"查询完毕"}\n```'):
        amended = answer_with_query_deliveries(answer, [_delivery()], answer_format='formal-and-core/1')
        assert '模型表' not in amended
        assert '| index | vm_pu (p.u.) |' in amended
        if answer.startswith('```'):
            assert json.loads(amended)['summary'] == '查询完毕'
