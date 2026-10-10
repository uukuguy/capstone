import pytest

from capstone_agent.task_outcome import normalize_task_outcome, unavailable_outcome


def test_unknown_cause_is_explicit_and_does_not_claim_missing_data():
    outcome = unavailable_outcome('answer_admission_failed', ({'tool_call_id': 'call-1', 'ok': False, 'error_code': 'tool_outcome_unknown'},))
    assert normalize_task_outcome(outcome) == outcome
    assert [item['category'] for item in outcome['diagnostics']] == ['unknown', 'admission']
    assert outcome['diagnostics'][0]['confirmation'] == 'unknown'
    assert outcome['status'] == 'unavailable'


def test_typed_transport_deadline_is_distinct_from_unknown_and_missing_input():
    outcome = unavailable_outcome('answer_admission_failed', ({'ok': False, 'error_code': 'capability_transport_timeout'},))
    assert outcome['diagnostics'][0]['category'] == 'service'
    assert outcome['diagnostics'][0]['confirmation'] == 'confirmed'
    assert '是否完成尚未确认' in outcome['diagnostics'][0]['summary']


def test_outcome_rejects_extra_fields_and_excess_work():
    outcome = unavailable_outcome('answer_admission_failed', ())
    with pytest.raises(ValueError):
        normalize_task_outcome({**outcome, 'raw_error': 'SECRET'})
    with pytest.raises(ValueError):
        normalize_task_outcome({**outcome, 'work': [{'id': 'a'}] * 33})


def test_unconfirmed_scope_cannot_claim_full_ranking_or_complete_task():
    outcome = unavailable_outcome('answer_admission_failed', ())
    coverage = {'requested_scope': 'unconfirmed', 'completed_scenario_count': 1,
        'scenario_context_refs': ['context:sha256:' + 'a' * 64], 'full_ranking_allowed': True}
    with pytest.raises(ValueError, match='coverage'):
        normalize_task_outcome({**outcome, 'coverage': coverage})
