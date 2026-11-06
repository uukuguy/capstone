import pytest
from types import SimpleNamespace
from capstone_agent.thinking_preview import PreviewBus, ThinkingWriter


def test_bus_bounds_deduplicates_and_expires():
    bus = PreviewBus(max_batches=2, ttl=10)
    for key in ['a', 'a', 'b', 'c']:
        bus.publish({'thread_id': 't', 'attempt_id': 'a', 'batch_id': key, 'text': key}, now=1)
    assert [p['batch_id'] for p in bus.read('t', now=2)] == ['b', 'c']
    assert bus.read('t', now=12) == []


def test_writer_barrier_and_required_failure():
    saved = []
    service = SimpleNamespace(append_runtime_event=lambda *a, **kw: saved.append(kw))
    writer = ThinkingWriter(service, object(), lambda p: None, interval=30)
    writer.append_thinking({}, {'text': 'one'}, 'public')
    writer.append_thinking({}, {'text': 'two'}, 'public')
    writer.flush()
    writer.close()
    assert ''.join(row['payload']['text'] for row in saved) == 'onetwo'
    assert len(saved[0]['payload']['preview_batch_ids']) == 2
    def fail(*a, **kw):
        raise OSError('write failed')
    writer = ThinkingWriter(SimpleNamespace(append_runtime_event=fail), object(), lambda p: None, interval=30)
    writer.append_thinking({}, {'text': 'one'}, 'public')
    with pytest.raises(OSError):
        writer.flush()
    with pytest.raises(OSError):
        writer.close()


def test_private_publish_requires_operator_even_when_threads_are_open(monkeypatch):
    from fastapi.testclient import TestClient
    from capstone_agent.host_api import create_host_app
    from capstone_agent.session import WorkerRegistry
    from test_thread_http_api import _Ledger, _service
    monkeypatch.setenv('CAPSTONE_THINKING_PREVIEW', '1')
    service = _service()
    app = create_host_app(_Ledger(), WorkerRegistry(()), operator_token='hosted-secret',
        allowed_hosts={'localhost'}, allowed_origins={'http://localhost:5173'},
        thread_service=service, thread_open_access=True)
    command = {'schema': 'capstone-command/1', 'thread_id': 'thr_demo_39',
        'run_id': 'run_001', 'command_id': 'cmd_preview', 'idempotency_key': 'idem_preview',
        'kind': 'send_ordinary', 'expected_event_seq': 0, 'payload': {'text': 'hello'}}
    with TestClient(app, base_url='http://localhost') as client:
        assert client.post('/internal/thinking-preview', json={}).status_code == 401
        assert client.post('/api/v1/threads/thr_demo_39/commands', json=command).status_code == 202
        claim = service.claim_attempt('worker', 30)
        body = {'thread_id': claim.thread_id, 'attempt_id': claim.attempt.attempt_id,
            'lease_token': claim.lease_token, 'workspace_name': claim.workspace_name,
            'batch_id': 'a' * 32, 'text': 'Supplied thought'}
        auth = {'Authorization': 'Bearer hosted-secret'}
        assert client.post('/internal/thinking-preview', json=body, headers=auth).status_code == 204
        assert client.post('/internal/thinking-preview', json={**body, 'lease_token': 'wrong'}, headers=auth).status_code == 409
        assert client.post('/internal/thinking-preview', json={**body, 'workspace_name': 'other'}, headers=auth).status_code == 409
        service.finish_attempt(claim, phase='failed', payload={'error_code': 'test_failed'})
        assert client.post('/internal/thinking-preview', json=body, headers=auth).status_code == 409


def test_semantic_and_terminal_barriers_keep_synchronous_return():
    rows = []
    service = SimpleNamespace(append_runtime_event=lambda *a, **kw: rows.append(kw) or 'event',
        finish_attempt=lambda *a, **kw: rows.append(kw) or 'terminal')
    writer = ThinkingWriter(service, object(), lambda p: None, interval=30)
    writer.append_thinking({}, {'text': 'before tool'})
    assert writer.append_runtime_event({}, event_type='tool_started', payload={}) == 'event'
    writer.append_thinking({}, {'text': 'before finish'})
    assert writer.finish_attempt({}, phase='succeeded', payload={}) == 'terminal'
    writer.close()
    assert [r.get('event_type', r.get('phase')) for r in rows] == [
        'assistant_thinking_delta', 'tool_started', 'assistant_thinking_delta', 'succeeded']


def test_async_writer_preserves_metadata_boundaries_and_preview_precedes_durability():
    import threading
    entered, release = threading.Event(), threading.Event()
    order = []
    def save(*args, **kw):
        entered.set()
        release.wait(2)
        order.append(('durable', kw['payload']))
    writer = ThinkingWriter(SimpleNamespace(append_runtime_event=save), object(),
        lambda row: order.append(('preview', row)), interval=0.01)
    writer.append_thinking({}, {'text': 'one', 'correlation_id': 'first'})
    assert entered.wait(1)
    writer.append_thinking({}, {'text': 'two', 'correlation_id': 'second'})
    assert [kind for kind, _ in order] == ['preview', 'preview']
    release.set()
    writer.close()
    durable = [row for kind, row in order if kind == 'durable']
    assert [(row['text'], row['correlation_id']) for row in durable] == [('one', 'first'), ('two', 'second')]
    assert all(len(row['preview_batch_ids']) == 1 for row in durable)


def test_required_write_failure_records_failed_terminal_through_original_service(monkeypatch):
    from capstone_agent import thread_worker
    from test_thread_http_api import _service
    service = _service()
    service.submit_command({'schema': 'capstone-command/1', 'thread_id': 'thr_demo_39',
        'run_id': 'run_001', 'command_id': 'cmd_write_failure', 'idempotency_key': 'idem_write_failure',
        'kind': 'send_ordinary', 'expected_event_seq': 0, 'payload': {'text': 'hello'}})
    def fail(*args, **kwargs):
        raise OSError('required write failed')
    def run(writer, *_args):
        writer.append_thinking({}, {'text': 'Actual supplied thought'})
        writer.finish_attempt({}, phase='completed', payload={})
    monkeypatch.setenv('CAPSTONE_THINKING_PREVIEW_ORIGIN', 'http://unused')
    monkeypatch.setattr('capstone_agent.thinking_preview.http_publisher', lambda *a: lambda p: None)
    monkeypatch.setattr(service, 'append_runtime_event', fail)
    monkeypatch.setattr(thread_worker, '_run_claimed_attempt', run)
    with pytest.raises(OSError):
        thread_worker.run_pending_attempt(service, lambda c: None, worker_id='worker')
    events = service.read_events('thr_demo_39', 0).events
    assert events[-1].event_type == 'attempt_failed'
    assert events[-1].payload['error_code'] == 'thinking_persistence_failed'
    assert not any(row.event_type == 'attempt_completed' for row in events)


def test_flush_waits_for_inflight_publish_and_rejects_oversize_utf8():
    import threading
    entered, release, flushed = threading.Event(), threading.Event(), threading.Event()
    saved = []
    def publish(row):
        entered.set()
        assert release.wait(2)
    writer = ThinkingWriter(SimpleNamespace(append_runtime_event=lambda *a, **kw: saved.append(kw)),
                            object(), publish, interval=30)
    producer = threading.Thread(target=lambda: writer.append_thinking({}, {'text': 'actual thought'}))
    producer.start()
    assert entered.wait(1)
    waiter = threading.Thread(target=lambda: (writer.flush(), flushed.set()))
    waiter.start()
    assert not flushed.wait(0.02)
    release.set()
    producer.join(2)
    waiter.join(2)
    assert flushed.is_set() and saved[0]['payload']['text'] == 'actual thought'
    with pytest.raises(ValueError):
        writer.append_thinking({}, {'text': '网' * 6000})
    writer.close()
