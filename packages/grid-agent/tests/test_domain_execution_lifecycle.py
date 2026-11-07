from grid_agent.domain_tools import PandapowerDomainToolService
import json
import pytest


def test_service_returns_owner_receipt_on_success_and_failure(tmp_path):
    service = PandapowerDomainToolService(workspace_root=tmp_path)
    service._capabilities = {'published': 'capability'}
    service._read_only = {'published': True}
    class Executor:
        def invoke(self, capability, arguments, *, execution_observer):
            execution_observer('execution_started')
            execution_observer('execution_ended')
            if arguments.get('fail'):
                raise RuntimeError('failed')
            return {'value': 1}
    service._executors['task'] = Executor()
    for failed in (False, True):
        result = service.invoke({'task_id': 'task', 'call_id': 'call', 'name': 'published', 'arguments': {'fail': failed}})
        assert result['ok'] is not failed
        receipt = result['execution_receipt']
        assert receipt['capacity'] == 8
        assert receipt['call_id'] == 'call'
        assert [e['phase'] for e in receipt['events']] == [
            'submitted','queued','acquired','execution_started','execution_ended','released']
    saved = list((tmp_path / 'task' / 'execution-receipts').glob('*.json'))
    assert len(saved) == 2  # Repeated task/call identity never overwrites an invocation.
    assert all(json.loads(path.read_text())['events'][-1]['phase'] == 'released' for path in saved)


def test_receipt_write_failure_is_fatal_and_releases_owner_capacity(tmp_path, monkeypatch):
    service = PandapowerDomainToolService(workspace_root=tmp_path)
    service._capabilities = {'published': 'capability'}
    def fail(*args, **kwargs): raise OSError('storage failed')
    monkeypatch.setattr('grid_agent.domain_tools.os.replace', fail)
    with pytest.raises(RuntimeError, match='execution receipt persistence failed'):
        service.invoke({'task_id': 'task', 'call_id': 'call', 'name': 'published', 'arguments': {}})
    assert not service._queue._active


def test_owner_records_survive_without_a_response_consumer(tmp_path):
    service = PandapowerDomainToolService(workspace_root=tmp_path)
    service._capabilities = {'published': 'capability'}
    class Executor:
        def invoke(self, capability, arguments, *, execution_observer):
            execution_observer('execution_started')
            execution_observer('execution_ended')
            raise RuntimeError('source failed')
    service._executors['task'] = Executor()
    service.invoke({'task_id': 'task', 'call_id': 'call', 'name': 'published', 'arguments': {}})
    saved, = (tmp_path / 'task' / 'execution-receipts').glob('*.json')
    document = json.loads(saved.read_text())
    assert document['call_id'] == 'call'
    assert document['events'][-1]['phase'] == 'released'
    assert 'arguments' not in document


def test_receipt_storage_can_use_separate_persistent_root(tmp_path, monkeypatch):
    receipt_root = tmp_path / 'persistent'
    monkeypatch.setenv('CAPSTONE_DOMAIN_EXECUTION_RECEIPTS_ROOT', str(receipt_root))
    workspace = tmp_path / 'scratch'
    service = PandapowerDomainToolService(workspace_root=workspace)
    persist = service._receipt_writer('task')
    persist({'task_id': 'task', 'call_id': 'call', 'events': []})
    saved, = (receipt_root / 'task' / 'execution-receipts').glob('*.json')
    assert json.loads(saved.read_text())['call_id'] == 'call'
    assert not (workspace / 'task' / 'execution-receipts').exists()


def test_mixed_entry_calls_use_one_owner_budget(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event, Lock
    service = PandapowerDomainToolService(workspace_root=tmp_path)
    service._capabilities = {'a': 'one', 'b': 'two'}
    service._read_only = {'a': True, 'b': True}
    entered, release, lock = Event(), Event(), Lock()
    active, peak = 0, 0
    class Executor:
        def invoke(self, capability, arguments, *, execution_observer):
            nonlocal active, peak
            execution_observer('execution_started')
            with lock:
                active += 1
                peak = max(peak, active)
                if active == 8: entered.set()
            assert release.wait(5)
            with lock: active -= 1
            execution_observer('execution_ended')
            return {}
    service._executors['task'] = Executor()
    with ThreadPoolExecutor(max_workers=16) as pool:
        futures = [pool.submit(service.invoke, {'task_id': 'task', 'call_id': str(i),
            'name': 'a' if i % 2 else 'b', 'arguments': {}}) for i in range(16)]
        try:
            assert entered.wait(3)
            assert peak == 8
        finally:
            release.set()
        results = [f.result() for f in futures]
    assert all(r['ok'] for r in results)
    assert peak == 8
    assert len({r['execution_receipt']['owner_id'] for r in results}) == 1
