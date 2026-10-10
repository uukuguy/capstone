import pytest

from capstone_agent.task_outcome import normalize_task_outcome, unavailable_outcome


def test_unknown_cause_is_explicit_and_does_not_claim_missing_data():
    outcome = unavailable_outcome('answer_admission_failed', ({'tool_call_id': 'call-1', 'ok': False, 'error_code': 'tool_outcome_unknown'},))
    assert normalize_task_outcome(outcome) == outcome
    assert [item['category'] for item in outcome['diagnostics']] == ['unknown', 'admission']
    assert outcome['diagnostics'][0]['confirmation'] == 'unknown'
    assert outcome['status'] == 'unavailable'


def test_outcome_rejects_extra_fields_and_excess_work():
    outcome = unavailable_outcome('answer_admission_failed', ())
    with pytest.raises(ValueError):
        normalize_task_outcome({**outcome, 'raw_error': 'SECRET'})
    with pytest.raises(ValueError):
        normalize_task_outcome({**outcome, 'work': [{'id': 'a'}] * 33})
