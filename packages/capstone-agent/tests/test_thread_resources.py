"""Resource uploads persist bounded parts and publish verified immutable versions."""
from hashlib import sha256

import pytest

from capstone_agent.artifacts import MemoryObjectStore
from capstone_agent.thread_resources import ResourceUploads
from test_enterprise_normal_chat import chat_store
from test_thread_postgres import postgres_thread_service


def test_draft_attachment_is_only_admitted_by_accepted_send(chat_store):
    from test_enterprise_normal_chat import native_executor
    from test_thread_work_execution import command
    service, thread = chat_store
    objects = MemoryObjectStore()
    service._material_objects = objects
    uploads = ResourceUploads(service, objects, chunk_bytes=4)
    uid = uploads.begin(thread, 'draft.csv', 4, 'draft', True)['upload_id']
    uploads.part(thread, uid, 0, b'abcd')
    resource = uploads.complete(thread, uid)
    assert uploads.resources(thread) == []
    assert uploads.resources(thread, True) == [resource]
    request = command(service, thread, 'send_message', 'unavailable', payload={
        'text': 'Inspect the attachment', 'attachment_refs': [resource['resource_id']]})
    assert service.submit_command(request).status == 'rejected'
    assert uploads.resources(thread) == []
    assert uploads.resources(thread, True) == [resource]
    service.set_native_executor(native_executor())
    request = command(service, thread, 'send_message', 'send', payload={
        'text': 'Inspect the attachment', 'attachment_refs': [resource['resource_id']]})
    receipt = service.submit_command(request)
    assert receipt.status == 'accepted'
    assert service.submit_command(request) == receipt
    assert uploads.resources(thread) == [resource]
    assert uploads.resources(thread, True) == []
    lease = service.claim_attempt('worker', 30, 'native')
    assert lease.submission['_resource_manifests'][0]['sha256'] == resource['sha256']
    assert lease.submission['_resource_manifests'][0]['resource_id'] == resource['resource_id']
    with pytest.raises(ValueError, match='cannot be cancelled'):
        uploads.cancel(thread, uid)


def test_draft_removal_excludes_context_and_preserves_other_uploads(chat_store):
    from capstone_agent.thread_materials import freeze_material_submission
    service, thread = chat_store
    objects = MemoryObjectStore()
    service._material_objects = objects
    uploads = ResourceUploads(service, objects, chunk_bytes=4)
    uid = uploads.begin(thread, 'draft.csv', 4, 'draft', True)['upload_id']
    uploads.part(thread, uid, 0, b'abcd')
    resource = uploads.complete(thread, uid)
    submission, rejection = freeze_material_submission(service, service.snapshot(thread), {}, {})
    assert rejection is None
    assert not submission.get('_resource_manifests')
    uploads.cancel(thread, uid)
    assert uploads.resources(thread, True) == []
    assert not objects.contents
    _, rejection = freeze_material_submission(service, service.snapshot(thread), {'attachment_refs': [resource['resource_id']]}, {})
    assert rejection == 'attachment_unavailable'


def test_resume_retry_and_verified_publication(chat_store):
    service, thread = chat_store
    objects = MemoryObjectStore()
    uploads = ResourceUploads(service, objects, chunk_bytes=4, max_file_bytes=100)
    upload = uploads.begin(thread, 'data.csv', 10, 'request-one')
    uid = upload['upload_id']
    assert uploads.begin(thread, 'data.csv', 10, 'request-one') == upload
    uploads.part(thread, uid, 0, b'abcd')
    uploads.part(thread, uid, 0, b'abcd')
    with pytest.raises(ValueError, match='conflict'):
        uploads.part(thread, uid, 0, b'xxxx')
    resumed = ResourceUploads(service, objects, chunk_bytes=4, max_file_bytes=100)
    assert resumed.status(thread, uid)['received_bytes'] == 4
    with pytest.raises(ValueError, match='incomplete'):
        resumed.complete(thread, uid)
    resumed.part(thread, uid, 1, b'efgh')
    resumed.part(thread, uid, 2, b'ij')
    resource = resumed.complete(thread, uid)
    assert resource['sha256'] == sha256(b'abcdefghij').hexdigest()
    assert resource['size_bytes'] == 10
    assert resumed.complete(thread, uid) == resource
    assert list(resumed.read(thread, resource['resource_id'], start=3, length=5)) == [b'd', b'efgh']
    assert 'object_key' not in str(resource)


def test_cancel_and_corruption_never_publish(chat_store):
    service, thread = chat_store
    objects = MemoryObjectStore()
    uploads = ResourceUploads(service, objects, chunk_bytes=4, max_file_bytes=100)
    uid = uploads.begin(thread, 'data.csv', 4, 'cancel')['upload_id']
    uploads.part(thread, uid, 0, b'abcd')
    uploads.cancel(thread, uid)
    assert uploads.status(thread, uid)['state'] == 'cancelled'
    with pytest.raises(ValueError):
        uploads.complete(thread, uid)
    uid = uploads.begin(thread, 'data.csv', 4, 'corrupt')['upload_id']
    uploads.part(thread, uid, 0, b'abcd')
    for key in objects.contents:
        if uid in key:
            objects.contents[key] = b'xxxx'
    with pytest.raises(ValueError, match='integrity'):
        uploads.complete(thread, uid)


def test_rejects_invalid_metadata_and_part_sizes(chat_store):
    service, thread = chat_store
    uploads = ResourceUploads(service, MemoryObjectStore(), chunk_bytes=4, max_file_bytes=100)
    for name, size in [('../escape', 4), ('data.csv', 101), ('data.csv', True)]:
        with pytest.raises(ValueError):
            uploads.begin(thread, name, size, 'bad')
    uid = uploads.begin(thread, 'data.csv', 6, 'valid')['upload_id']
    for index, data in [(0,b'abc'),(1,b'abcd'),(2,b'ab'),(-1,b'abcd')]:
        with pytest.raises(ValueError):
            uploads.part(thread, uid, index, data)


def test_http_chunk_bound_and_authorization(chat_store):
    from fastapi import FastAPI, HTTPException
    from fastapi.testclient import TestClient
    from capstone_agent.thread_resource_http import register_resource_routes
    service, thread = chat_store
    objects = MemoryObjectStore()
    app = FastAPI()
    def authorize(request):
        if request.headers.get('X-Test-Access') != 'allowed':
            raise HTTPException(403)
    register_resource_routes(app, service=service, objects=objects, authorize=authorize,
        uploads=ResourceUploads(service, objects, chunk_bytes=4, max_file_bytes=10**10))
    client = TestClient(app)
    base = f'/api/v1/threads/{thread}/resource-uploads'
    assert client.get(base).status_code == 403
    client.headers['X-Test-Access'] = 'allowed'
    assert client.get(base).json()['max_file_bytes'] > 1024**3
    uid = client.post(base, json={'file_name':'data.csv','size_bytes':4,'request_id':'http'}).json()['upload_id']
    assert client.put(f'{base}/{uid}/parts/0', content=b'abcde').status_code == 413
    assert client.put(f'{base}/{uid}/parts/0', content=b'abcd').status_code == 200
    assert client.post(f'{base}/{uid}/complete').json()['sha256'] == sha256(b'abcd').hexdigest()


def test_quota_expiry_and_storage_cleanup(chat_store, monkeypatch):
    service, thread = chat_store
    objects = MemoryObjectStore()
    uploads = ResourceUploads(service, objects, chunk_bytes=4, max_file_bytes=100,
        max_session_bytes=4, ttl_seconds=2)
    uid = uploads.begin(thread, 'a.csv', 4, 'first')['upload_id']
    uploads.part(thread, uid, 0, b'abcd')
    with pytest.raises(ValueError, match='quota'):
        uploads.begin(thread, 'b.csv', 1, 'second')
    expiry = uploads.status(thread, uid)['expires_at']
    monkeypatch.setattr('capstone_agent.thread_resources.time.time', lambda: expiry + 1)
    assert uploads.status(thread, uid)['state'] == 'expired'
    assert not objects.contents
    assert uploads.begin(thread, 'b.csv', 1, 'second')['state'] == 'uploading'


def test_write_before_ack_failure_remains_reclaimable(chat_store):
    service, thread = chat_store
    class FailingStore(MemoryObjectStore):
        def put(self, key, content, mime):
            super().put(key, content, mime)
            raise OSError('interrupted after writing bytes')
    objects = FailingStore()
    uploads = ResourceUploads(service, objects, chunk_bytes=4)
    uid = uploads.begin(thread, 'a.csv', 4, 'interruption')['upload_id']
    with pytest.raises(OSError):
        uploads.part(thread, uid, 0, b'abcd')
    assert uploads.status(thread, uid)['received_bytes'] == 0
    assert objects.contents
    ResourceUploads(service, objects).cancel(thread, uid)
    assert not objects.contents
