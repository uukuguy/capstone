from copy import deepcopy

import pytest

from capstone_agent.admitted_result_answer import render_admitted_result_answer
from test_result_projection import valid_projection


def test_formal_summary_uses_admitted_domain_labels_and_values_without_model_prose():
    first = valid_projection()
    second = deepcopy(first)
    second.update(result_id='second', result_ref='result:sha256:' + 'd' * 64)
    second['source'] = {'capability_id': 'analysis.optimization.run', 'domain_pack_id': 'other-pack', 'implementation_family': 'pypsa'}
    second['summary'] = [{'metric_id': 'cost', 'label': '系统成本', 'value': 200, 'unit': 'EUR'}]
    second['tables'] = []
    second['overlay'] = None
    answer = render_admitted_result_answer((first, second),
        result_refs=(first['result_ref'], second['result_ref']), evidence_refs=tuple(first['evidence_refs']))
    assert '有功损耗：43.64 MW' in answer
    assert '系统成本：200 EUR' in answer
    assert '线路负载率' in answer and '67.15' in answer
    assert 'sha256' not in answer


def test_summary_rejects_unadmitted_or_foreign_attempt_projection():
    first = valid_projection()
    with pytest.raises(ValueError, match='admitted'):
        render_admitted_result_answer((first,), result_refs=(), evidence_refs=())
    second = deepcopy(first)
    second.update(result_id='foreign', attempt_id='other')
    with pytest.raises(ValueError, match='identity'):
        render_admitted_result_answer((first, second), result_refs=(first['result_ref'],), evidence_refs=tuple(first['evidence_refs']))


def test_unavailable_visual_projection_does_not_claim_analysis_failed():
    first = valid_projection()
    first.update(status='unavailable', summary=[], tables=[], element_refs=[], overlay=None,
                 unavailable_reason='此类型尚无展示投影')
    assert render_admitted_result_answer((first,), result_refs=(first['result_ref'],),
        evidence_refs=tuple(first['evidence_refs'])) is None


def test_combined_terminal_budget_keeps_answer_and_evidence_when_cards_do_not_fit():
    import json
    from capstone_agent.harness import AdmittedAttemptAnswer, terminal_payload_for_admission

    projection = valid_projection()
    projection['summary'][0]['label'] = '展示' * 8000
    admission = AdmittedAttemptAnswer('已核对结果。' * 2000, 'authority_backed', 'lineage_verified',
        (projection['result_ref'],), tuple(projection['evidence_refs']),
        result_projections=(projection,))
    payload = terminal_payload_for_admission(admission, bounded_display=True)
    assert payload['answer'] == admission.answer
    assert payload['result_refs'] == list(admission.result_refs)
    assert payload['evidence_refs'] == list(admission.evidence_refs)
    assert 'result_projections' not in payload
    assert 'task_outcome' not in payload
    assert payload['admission']['diagnostic_codes'] == ['result_display_unavailable']
    assert len(json.dumps(payload, ensure_ascii=False).encode()) < 64 * 1024
