import json

import pytest

from capstone_agent.result_delivery import ResultDeliveryChannel


def channel(tmp_path, *, verify=None):
    calls = []
    projection = {'result_ref': 'result:one', 'status': 'completed', 'summary': [{'value': 12}],
        'tables': [{'table_id': 'values', 'title': 'Values', 'columns': [{'column_id': 'value'}],
                    'rows': [{'value': 123}, {'value': 456}]}]}
    def build(results, evidence, events):
        calls.append((results, evidence, events))
        return (projection,)
    value = ResultDeliveryChannel(tmp_path, thread_id='thr_one', attempt_id='attempt_one',
        binding_ids={'business'}, verify=verify or (lambda *_: None), project=build, is_active=lambda: True)
    return value, calls, projection


def observe(value, *, ok=True, binding='business'):
    value.observe({'type': 'tool_result', 'tool_name': 'business_calculate', 'binding_id': binding,
        'capability_key': {'binding_id': binding, 'capability_id': 'calculate'}, 'capability': 'calculate',
        'ok': ok, 'result_refs': ['result:one'], 'evidence_refs': ['evidence:one']})


def test_delivery_requires_observed_success_and_selected_binding(tmp_path):
    value, calls, _ = channel(tmp_path)
    assert value.prepare('result:one')['status'] == 'unavailable'
    observe(value, ok=False)
    observe(value, binding='foreign')
    assert value.prepare('result:one')['status'] == 'unavailable'
    assert not calls


def test_receipt_has_full_coverage_but_no_retyped_rows_and_reuses_projection(tmp_path):
    value, calls, projection = channel(tmp_path)
    observe(value)
    receipt = value.prepare('result:one')
    assert receipt['status'] == 'prepared'
    assert receipt['tables'][0]['total_rows'] == 2
    assert receipt['tables'][0]['complete'] is True
    assert 'rows' not in receipt['tables'][0]
    assert '123' not in json.dumps(receipt)
    assert value.projections(('result:one',), ('evidence:one',), ()) == (projection,)
    assert len(calls) == 1


def test_failed_verification_is_not_a_success_or_fatal_task_error(tmp_path):
    def rejected(*_):
        raise ValueError('private authority detail')
    value, calls, _ = channel(tmp_path, verify=rejected)
    observe(value)
    receipt = value.prepare('result:one')
    assert receipt['status'] == 'unavailable'
    assert receipt['code'] == 'result_delivery_not_verified'
    assert 'private authority detail' not in json.dumps(receipt)
    assert not calls


def test_partial_table_does_not_claim_complete_delivery(tmp_path):
    value, _, projection = channel(tmp_path)
    projection['status'] = 'partial'
    projection['tables'][0]['pagination'] = {'total_rows': 10, 'page_size': 2, 'manifest_ref': 'not-published'}
    observe(value)
    receipt = value.prepare('result:one')
    assert receipt['tables'][0]['complete'] is False
    assert receipt['tables'][0]['total_rows'] == 10


def test_channel_receipts_are_bound_and_changed_requests_are_rejected(tmp_path):
    value, calls, _ = channel(tmp_path)
    observe(value)
    request = value.root / 'requests' / 'request_one.json'
    request.write_text(json.dumps({'request_id': 'request_one', 'thread_id': 'thr_one',
        'attempt_id': 'attempt_one', 'result_ref': 'result:one'}))
    value.drain()
    receipt = json.loads((value.root / 'receipts' / request.name).read_text())
    assert receipt['status'] == 'prepared'
    value.drain()
    assert len(calls) == 1
    request.write_text(request.read_text() + ' ')
    with pytest.raises(ValueError, match='changed'):
        value.drain()


def test_cancelled_attempt_does_not_project(tmp_path):
    value, calls, _ = channel(tmp_path)
    observe(value)
    value.bind_active_check(lambda: False)
    assert value.prepare('result:one')['code'] == 'attempt_closed'
    assert not calls
