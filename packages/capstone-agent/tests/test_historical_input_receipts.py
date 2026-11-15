from hashlib import sha256
from types import SimpleNamespace
import pytest
from test_enterprise_normal_chat import chat_store, native_executor
from test_thread_postgres import postgres_thread_service
from test_thread_work_execution import command


def inputs():
    from capstone_agent.continuation_resources import artifact_resource
    source = dict(thread_id='thr_test', attempt_id='attempt_old', artifact_id='file-old',
                  work_id='work_test', source_status='completed', file_name='data.csv',
                  size_bytes=3, sha256=sha256(b'abc').hexdigest())
    resource = artifact_resource(source)
    claim = SimpleNamespace(thread_id='thr_test', attempt=SimpleNamespace(attempt_id='attempt_new'),
        task_context=SimpleNamespace(binding=SimpleNamespace(work_id='work_test')),
        submission={'_resource_manifests': [resource], '_continuation_artifacts': [source]})
    return claim, resource, source


def test_receipt_is_bound_to_frozen_source_and_consumer():
    from capstone_agent.historical_input_receipts import delivery_receipt
    claim, resource, source = inputs()
    receipt = delivery_receipt(claim, 'task_one', resource)
    assert receipt['source'] == source
    assert receipt['attempt_id'] == 'attempt_new'
    assert receipt == delivery_receipt(claim, 'task_one', resource)
    assert receipt['receipt_id'] != delivery_receipt(claim, 'task_two', resource)['receipt_id']
    with pytest.raises(ValueError):
        delivery_receipt(claim, 'task_one', {**resource, 'sha256': '0'*64})
    claim.task_context.binding.work_id = 'work_other'
    with pytest.raises(ValueError):
        delivery_receipt(claim, 'task_one', resource)


def test_available_upload_is_not_historical_delivery():
    from capstone_agent.historical_input_receipts import delivery_receipt
    claim, resource, _ = inputs()
    claim.submission['_continuation_artifacts'] = []
    assert delivery_receipt(claim, 'task_one', resource) is None


def test_delivery_is_durable_idempotent_and_rejects_changed_origin(chat_store):
    from dataclasses import replace
    from capstone_agent.continuation_resources import artifact_resource, resource_reader_for
    from capstone_agent.historical_input_receipts import delivery_receipt, EVENT
    service, thread = chat_store
    service.set_native_executor(native_executor())
    service.submit_command(command(service, thread, 'send_message', 'delivery', payload={'text': 'Check a file'}))
    claim = service.claim_attempt('delivery-test', 60)
    source = inputs()[2]
    source = {**source, 'thread_id': thread, 'work_id': claim.task_context.binding.work_id}
    resource = artifact_resource(source)
    claim = replace(claim, submission={**claim.submission, '_resource_manifests': [resource],
                                      '_continuation_artifacts': [source]})
    reader = resource_reader_for(service, claim)
    reader.record_delivery('task_one', resource)
    reader.record_delivery('task_one', resource)
    records = [e for e in service.read_events(thread, 0).events if e.event_type == EVENT]
    assert len(records) == 1
    assert records[0].attempt_id == claim.attempt.attempt_id
    assert records[0].payload == delivery_receipt(claim, 'task_one', resource)
    with pytest.raises(ValueError):
        service.append_runtime_event(claim, event_type=EVENT, payload={**records[0].payload, 'source': {}})
