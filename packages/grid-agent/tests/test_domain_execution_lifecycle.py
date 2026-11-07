from grid_agent.domain_tools import PandapowerDomainToolService


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
