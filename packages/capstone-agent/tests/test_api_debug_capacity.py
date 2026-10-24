"""Debug bounds interrupt before upload/projection fallback; no Provider."""
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from capstone_agent.application_capacity import CapacityExceeded, initialize_capacity
from capstone_agent.thread_products import checked_selections, _events
from capstone_agent.thread_resource_http import register_resource_routes
from capstone_agent.thread_materials import _process_files


@pytest.fixture(autouse=True)
def restore_capacity():
    yield
    initialize_capacity()


def test_debug_selection_count_preserves_typed_capacity():
    initialize_capacity({'product_reference_count': 1}, mode='debug')
    with pytest.raises(CapacityExceeded) as caught:
        checked_selections([{}, {}])
    assert caught.value.dimension == 'product_reference_count'
    assert caught.value.actual == 2
    assert caught.value.to_document()['fatal'] is True


def test_debug_upload_metadata_uses_effective_bound_before_parsing():
    initialize_capacity({'control_document_bytes': 8}, mode='debug')
    app = FastAPI()
    register_resource_routes(app, service=SimpleNamespace(), objects=object(),
                             authorize=lambda request: None, uploads=SimpleNamespace())
    with TestClient(app) as client, pytest.raises(CapacityExceeded) as caught:
        client.post('/api/v1/threads/thr_one/resource-uploads', content=b'{"long":"metadata"}')
    assert caught.value.dimension == 'control_document_bytes'
    assert caught.value.actual == 19
    assert caught.value.phase == 'resource.upload.metadata'


def test_debug_continuation_detects_overflow_before_dropping_process_files():
    initialize_capacity({'artifact_count': 2}, mode='debug')
    events = []
    for index in range(3):
        document = {'payload': {'artifact': {'file_name': f'{index}.csv', 'work_id': 'work_one'}}}
        events.append(SimpleNamespace(event_type='native_artifact_published', thread_id='thr_one',
                                      attempt_id='attempt_one', payload=document['payload'], to_document=lambda value=document: value))
    service = SimpleNamespace(_events=events, _attempts={'attempt_one': {'attempt': SimpleNamespace(phase='completed')}})
    with pytest.raises(CapacityExceeded) as caught:
        _process_files(service, SimpleNamespace(thread_id='thr_one'), 'work_one', None, None)
    assert caught.value.dimension == 'artifact_count'
    assert caught.value.actual == 3


def test_product_scan_uses_the_same_initialized_window_in_memory():
    initialize_capacity({'product_index_scan_events': 80})
    events = [SimpleNamespace(event_seq=i, event_type='native_artifact_published', visibility='public',
                              payload={'artifact': {'work_id': 'work_one'}}) for i in range(1, 91)]
    service = SimpleNamespace(_events=events, _check_thread=lambda thread: None, _lock=object())
    selected = _events(service, 'thr_one', work_id='work_one')
    assert len(selected) == 81  # One lookahead record preserves has_more.
    assert selected[-1].event_seq == 10
