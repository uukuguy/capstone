from hashlib import sha256
import pytest
from capstone_agent.artifacts import MemoryObjectStore
from capstone_agent.thread_resources import ResourceUploads
from capstone_agent.resource_range_reads import ResourceRangeReads
from test_enterprise_normal_chat import chat_store, native_executor
from test_thread_work_execution import command
from test_thread_postgres import postgres_thread_service
from capstone_agent.application_capacity import initialize_capacity

def prepared(service, thread):
    objects = MemoryObjectStore()
    service.set_native_executor(native_executor())
    uploads = ResourceUploads(service, objects, chunk_bytes=4)
    uid = uploads.begin(thread, 'sample.txt', 12, 'range-upload')['upload_id']
    for index, data in enumerate((b'abcd', b'efgh', b'ijkl')):
        uploads.part(thread, uid, index, data)
    resource = uploads.complete(thread, uid)
    service.submit_command(command(service, thread, 'send_message', 'range-task', payload={
        'text': 'Read a sample', 'attachment_refs': [resource['resource_id']]}))
    claim = service.claim_attempt('range-test', 60)
    return objects, resource, claim

def test_cross_part_and_durable_retry(chat_store):
    service, thread = chat_store
    objects, resource, claim = prepared(service, thread)
    reads = ResourceRangeReads(service, objects)
    request = dict(schema='capstone-resource-range-request/1', request_id='a'*64,
                   resource_id=resource['resource_id'], offset=3, length=4)
    reply = reads.read(thread, claim.attempt.attempt_id, 'task', resource, request)
    assert reply['content'] == b'defg'
    assert reply['receipt']['sha256'] == sha256(b'defg').hexdigest()
    for key in list(objects.contents):
        if key.startswith('thread-resources/'):
            objects.delete(key)
    assert ResourceRangeReads(service, objects).read(thread, claim.attempt.attempt_id, 'task', resource, request) == reply
    assert reads.page(thread, claim.attempt.attempt_id)['items'] == [reply['receipt']]
    assert reads.detail(thread, reply['receipt']['read_id']) == reply['receipt']
    with pytest.raises(ValueError):
        reads.read(thread, claim.attempt.attempt_id, 'task', resource, {**request, 'offset': 2})

@pytest.mark.parametrize('offset,length', [(True,1),(0,False),(-1,2),(0,0),(0,1.5),(11,2),(2**54,1)])
def test_bad_range(chat_store, offset, length):
    service, thread = chat_store
    objects, resource, claim = prepared(service, thread)
    with pytest.raises(ValueError):
        ResourceRangeReads(service, objects).read(thread, claim.attempt.attempt_id, 'task', resource,
            dict(schema='capstone-resource-range-request/1', request_id='b'*64,
                 resource_id=resource['resource_id'], offset=offset, length=length))

def request_for(resource, identity='c', offset=3, length=4):
    return dict(schema='capstone-resource-range-request/1', request_id=identity*64,
                resource_id=resource['resource_id'], offset=offset, length=length)

def test_concurrent_retry_and_quota(chat_store):
    from concurrent.futures import ThreadPoolExecutor
    service, thread = chat_store
    objects, resource, claim = prepared(service, thread)
    attempt = claim.attempt.attempt_id
    reads = ResourceRangeReads(service, objects)
    initialize_capacity({'resource_read_attempt_bytes':4})
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(reads.read, thread, attempt, 'task', resource, request_for(resource)) for _ in range(2)]
            results = [f.result() for f in futures]
        assert results[0] == results[1]
        assert len(reads.page(thread, attempt)['items']) == 1
        with pytest.raises(ValueError, match='capacity'):
            reads.read(thread, attempt, 'task', resource, request_for(resource, 'd'))
    finally:
        initialize_capacity()

def test_cancel_persist_failure_corruption_and_scope(chat_store):
    service, thread = chat_store
    objects, resource, claim = prepared(service, thread)
    attempt = claim.attempt.attempt_id
    reads = ResourceRangeReads(service, objects)
    def cancelled():
        raise RuntimeError('cancelled')
    with pytest.raises(RuntimeError, match='cancelled'):
        reads.read(thread, attempt, 'task', resource, request_for(resource), checkpoint=cancelled)
    assert reads.page(thread, attempt)['items'] == []
    with pytest.raises(ValueError):
        reads.read(thread, 'unknown_attempt', 'task', resource, request_for(resource))
    with pytest.raises(ValueError):
        reads.read(thread, attempt, 'task', {**resource, 'sha256':'f'*64}, request_for(resource))
    original = objects.put
    def fail(*args):
        raise OSError('storage unavailable')
    objects.put = fail
    with pytest.raises(OSError):
        reads.read(thread, attempt, 'task', resource, request_for(resource))
    assert reads.page(thread, attempt)['items'] == []
    objects.put = original
    reply = reads.read(thread, attempt, 'task', resource, request_for(resource))
    original(reads._key(reply['receipt']), b'xxxx', 'application/octet-stream')
    with pytest.raises(ValueError, match='integrity'):
        reads.read(thread, attempt, 'task', resource, request_for(resource))

def test_blocking_io_deadline_is_bounded(chat_store):
    import threading
    import time
    service, thread = chat_store
    objects, resource, claim = prepared(service, thread)
    original = objects.get
    release = threading.Event()
    def slow(*args):
        release.wait(5)
        return original(*args)
    objects.get = slow
    initialize_capacity({'resource_read_io_seconds':1})
    start = time.monotonic()
    try:
        with pytest.raises(ValueError, match='deadline'):
            ResourceRangeReads(service, objects).read(thread, claim.attempt.attempt_id, 'task', resource, request_for(resource))
        assert time.monotonic()-start < 2
        assert ResourceRangeReads(service, objects).page(thread, claim.attempt.attempt_id)['items'] == []
    finally:
        release.set()
        initialize_capacity()

def test_reads_only_intersecting_parts(chat_store):
    service, thread = chat_store
    objects, resource, claim = prepared(service, thread)
    observed = []
    original = objects.get
    def count(key, limit):
        observed.append(key)
        return original(key, limit)
    objects.get = count
    ResourceRangeReads(service, objects).read(thread, claim.attempt.attempt_id, 'task', resource, request_for(resource))
    assert len([k for k in observed if k.startswith('thread-resources/')]) == 2

def test_keyset_page_and_http_projection(chat_store):
    from fastapi import FastAPI, HTTPException
    from fastapi.testclient import TestClient
    from capstone_agent.thread_resource_http import register_resource_routes
    service, thread = chat_store
    objects, resource, claim = prepared(service, thread)
    attempt = claim.attempt.attempt_id
    reads = ResourceRangeReads(service, objects)
    for identity in ('a','b','c'):
        reads.read(thread, attempt, 'task', resource, request_for(resource, identity))
    first = reads.page(thread,attempt,1)
    second = reads.page(thread,attempt,1,first['next_cursor'])
    assert second['items'][0]['request_id']=='b'*64
    with pytest.raises(ValueError,match='cursor'):
        reads.page(thread,attempt,1,'x'*1025)
    def authorize(request):
        if request.headers.get('Authorization') != 'Bearer test':
            raise HTTPException(401)
    app=FastAPI()
    register_resource_routes(app,service=service,objects=objects,authorize=authorize)
    client=TestClient(app)
    url=f'/api/v1/threads/{thread}/resource-reads'
    assert client.get(url,params={'attempt_id':attempt}).status_code==401
    page=client.get(url,params={'attempt_id':attempt,'limit':1},headers={'Authorization':'Bearer test'})
    assert page.status_code==200
    assert page.json()==first
    assert 'resource-range-reads/' not in page.text
    receipt=first['items'][0]
    assert client.get(url+'/'+receipt['read_id'],headers={'Authorization':'Bearer test'}).json()==receipt

def test_postgres_recreated_service_retains_accepted_bytes(chat_store):
    import os
    from capstone_agent.thread_service import PostgresThreadService
    service, thread=chat_store
    if hasattr(service,'_lock'):
        pytest.skip('PostgreSQL service recreation')
    objects,resource,claim=prepared(service,thread)
    request=request_for(resource)
    expected=ResourceRangeReads(service,objects).read(thread,claim.attempt.attempt_id,'task',resource,request)
    for key in list(objects.contents):
        if key.startswith('thread-resources/'):
            objects.delete(key)
    recreated=PostgresThreadService(os.environ['CAPSTONE_TEST_DATABASE_URL'])
    recreated.initialize()
    assert ResourceRangeReads(recreated,objects).read(thread,claim.attempt.attempt_id,'task',resource,request)==expected

def test_metadata_queries_bound_unrelated_history(chat_store,monkeypatch):
    from capstone_agent.thread_materials import _mutate,_write_event
    service,thread=chat_store
    objects,resource,claim=prepared(service,thread)
    attempt=claim.attempt.attempt_id
    reads=ResourceRangeReads(service,objects)
    reply=reads.read(thread,attempt,'task',resource,request_for(resource))
    def add_history(snapshot,connection):
        _write_event(service,snapshot,'resource_range_read',{
            **reply['receipt'],'attempt_id':'unrelated_attempt','read_id':'read_unrelated',
            'preview':{'text':'x'*8192}},connection)
    for _ in range(20):
        _mutate(service,thread,add_history)
    observed=[]
    original=reads._records
    def bounded(*args,**kwargs):
        rows=original(*args,**kwargs)
        observed.extend(rows)
        return rows
    monkeypatch.setattr(reads,'_records',bounded)
    assert reads.page(thread,attempt,1)['items']==[reply['receipt']]
    assert reads.detail(thread,reply['receipt']['read_id'])==reply['receipt']
    assert reads.read(thread,attempt,'task',resource,request_for(resource))==reply
    assert observed and all(r['attempt_id']==attempt for _,r in observed)

def test_source_integrity_and_missing_retained_fragment(chat_store):
    service,thread=chat_store
    objects,resource,claim=prepared(service,thread)
    reads=ResourceRangeReads(service,objects)
    key=next(key for key in objects.contents if '/0/' in key)
    old=objects.get(key,4)
    objects.put(key,b'xxxx','application/octet-stream')
    with pytest.raises(ValueError,match='integrity'):
        reads.read(thread,claim.attempt.attempt_id,'task',resource,request_for(resource))
    assert reads.page(thread,claim.attempt.attempt_id)['items']==[]
    objects.put(key,old,'application/octet-stream')
    reply=reads.read(thread,claim.attempt.attempt_id,'task',resource,request_for(resource))
    objects.delete(reads._key(reply['receipt']))
    with pytest.raises((ValueError,KeyError,OSError)):
        reads.read(thread,claim.attempt.attempt_id,'task',resource,request_for(resource))
