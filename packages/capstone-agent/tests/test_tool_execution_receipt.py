from copy import deepcopy

from capstone_agent.tool_execution_receipt import checked_execution_receipt


def receipt():
    phases = ['submitted', 'queued', 'acquired', 'execution_started', 'execution_ended', 'released']
    return {'schema': 'capstone-tool-execution/1', 'owner_id': 'owner', 'scope_id': 'scope',
            'task_id': 'task', 'call_id': 'call', 'policy_version': 'rolling/1', 'capacity': 8,
            'events': [{'phase': phase, 'at': '2026-11-08T01:00:00+00:00', 'elapsed_ms': index,
                        'provenance': 'authority_process' if phase.startswith('execution_') else 'owner_scheduler'}
                       for index, phase in enumerate(phases)]}


def test_owner_receipt_is_bounded_and_bound_to_actual_call():
    value = receipt()
    assert checked_execution_receipt(value, task_id='task', call_id='call') == value
    assert checked_execution_receipt(value, task_id='other', call_id='call') is None
    assert checked_execution_receipt(value, task_id='task', call_id='other') is None


def test_untrusted_unknown_nonfinite_and_reordered_records_are_not_projected():
    value = receipt()
    for update in [lambda v: v.update(secret='do-not-project'),
                   lambda v: v.update(capacity=True),
                   lambda v: v['events'][2].update(elapsed_ms=float('nan')),
                   lambda v: v['events'][2].update(elapsed_ms=-1),
                   lambda v: v['events'].reverse(),
                   lambda v: v['events'][3].update(provenance='owner_scheduler')]:
        invalid = deepcopy(value)
        update(invalid)
        assert checked_execution_receipt(invalid, task_id='task', call_id='call') is None


def test_queued_cancellation_records_request_without_claiming_execution():
    value = receipt()
    value['events'] = value['events'][:2] + [{
        'phase': 'cancellation_requested', 'at': '2026-11-08T01:00:00+00:00',
        'elapsed_ms': 2, 'provenance': 'owner_scheduler'}]
    assert checked_execution_receipt(value, task_id='task', call_id='call') == value
