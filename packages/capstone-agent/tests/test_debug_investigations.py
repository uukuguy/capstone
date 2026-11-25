from concurrent.futures import ThreadPoolExecutor
import os

import pytest

from capstone_agent.debug_investigations import InvestigationRegister
from capstone_agent.thread_service import PostgresThreadService
from test_harness import _thread_service
from uuid import uuid4
from dataclasses import replace


def test_postgres_register_survives_reopen_and_concurrent_reservations():
    dsn = os.environ.get('CAPSTONE_TEST_DATABASE_URL')
    if not dsn:
        pytest.skip('requires isolated PostgreSQL test database')
    service = PostgresThreadService(dsn)
    service.initialize()
    thread = 'thr_' + uuid4().hex
    snap = _thread_service().snapshot('thr_harness')
    service.create_thread(replace(snap, thread_id=thread, run=replace(snap.run, run_id='run_'+thread)))
    try:
        store = InvestigationRegister(service)
        args = ('enterprise',thread,'command-1','诊断目标')
        first = store.start(*args)
        reopened = InvestigationRegister(PostgresThreadService(dsn))
        assert reopened.latest('enterprise', thread) == reopened.start(*args) == first
        with pytest.raises(ValueError):
            reopened.start(*args[:-1], 'changed')
        call = ('enterprise',thread,first['investigation_id'],'step-1','read',{'limit':1},'fixture-binding')
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: reopened.reserve_call(*call), range(8)))
        assert len({identity for identity,_ in results}) == 1
        assert sum(dispatch for _,dispatch in results) == 1
        assert InvestigationRegister(PostgresThreadService(dsn)).reserve_call(*call)[1] is False
        with pytest.raises(ValueError):
            reopened.reserve_call(*call[:-1], 'changed-binding')
        scope = ('enterprise', thread, first['investigation_id'])
        pending = {'task_id': 'debug_original', 'status': 'queued'}
        assert reopened._reserve_diagnosis(scope, pending) == pending
        assert reopened._reserve_diagnosis(scope, {'task_id': 'debug_duplicate', 'status': 'running'}) == pending
        worker = InvestigationRegister(PostgresThreadService(dsn))
        assert worker.next_queued() == scope
        with ThreadPoolExecutor(max_workers=4) as pool:
            claims = list(pool.map(lambda _: worker._claim_diagnosis(scope, {**pending, 'status': 'running'}), range(8)))
        assert sum(claims) == 1
        assert worker.next_queued() is None
        completed = {**pending, 'status': 'completed', 'answer': '已定位。'}
        reopened._save_diagnosis(scope, completed)
        reopened._save_diagnosis(scope, {**pending, 'status': 'unknown'})
        assert reopened.get(*scope)['diagnosis'] == completed
    finally:
        service.delete_thread(thread)
