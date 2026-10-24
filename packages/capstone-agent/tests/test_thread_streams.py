import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from capstone_agent.thread_streams import ThreadStreamBudget


@pytest.mark.parametrize('legacy,capacity,expected', [
    (None, None, None), ('', None, None),
    (None, {'thread_stream_count': 41, 'thread_streams_per_thread': 6}, (41, 6)),
    ('', {'thread_stream_count': 41, 'thread_streams_per_thread': 6}, (41, 6)),
    (('17', '3'), {'thread_stream_count': 41, 'thread_streams_per_thread': 6}, (17, 3)),
])
def test_host_stream_budget_uses_canonical_or_explicit_configuration(monkeypatch, legacy, capacity, expected):
    from capstone_agent.application_capacity import initialize_capacity, limits
    from capstone_agent.host_api import create_host_app
    from capstone_agent.session import WorkerRegistry
    for index, name in enumerate(('CAPSTONE_THREAD_MAX_STREAMS', 'CAPSTONE_THREAD_STREAMS_PER_THREAD')):
        if legacy is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, legacy[index] if isinstance(legacy, tuple) else legacy)
    try:
        environment = {} if capacity is None else {'CAPSTONE_CAPACITY_JSON': json.dumps({
            'schema': 'capstone-capacity-profile/1', 'limits': capacity})}
        initialize_capacity(environment=environment)
        selected = expected or (limits.thread_stream_count, limits.thread_streams_per_thread)
        app = create_host_app(SimpleNamespace(), WorkerRegistry(()), operator_token='test-secret',
            allowed_hosts={'localhost'}, allowed_origins={'http://localhost'})
        configured = next(middleware.kwargs for middleware in app.user_middleware
                          if middleware.cls is ThreadStreamBudget)
        assert (configured['max_streams'], configured['per_thread']) == selected
        budget = ThreadStreamBudget(lambda *_: None, **configured)
        assert (budget.max_streams, budget.per_thread) == selected
    finally:
        initialize_capacity()


def test_compose_does_not_override_application_stream_defaults():
    compose = (Path(__file__).parents[3] / 'compose.yaml').read_text()
    assert 'CAPSTONE_THREAD_MAX_STREAMS: ${CAPSTONE_THREAD_MAX_STREAMS:-}' in compose
    assert 'CAPSTONE_THREAD_STREAMS_PER_THREAD: ${CAPSTONE_THREAD_STREAMS_PER_THREAD:-}' in compose
    assert 'CAPSTONE_CAPACITY_JSON: ${CAPSTONE_CAPACITY_JSON:-}' in compose


def test_stream_capacity_is_bounded_and_disconnect_releases_it():
    async def scenario():
        entered = asyncio.Event()
        release = asyncio.Event()
        async def app(_scope, _receive, _send):
            entered.set()
            await release.wait()
        budget = ThreadStreamBudget(app, max_streams=2, per_thread=1)
        async def receive():
            return {'type': 'http.disconnect'}
        frames = []
        async def send(frame):
            frames.append(frame)
        def scope(thread):
            return {'type': 'http', 'path': f'/api/v1/threads/{thread}/events/stream'}
        first = asyncio.create_task(budget(scope('thr_one'), receive, send))
        await entered.wait()
        entered.clear()
        await budget(scope('thr_one'), receive, send)
        assert frames[0]['status'] == 503
        second = asyncio.create_task(budget(scope('thr_two'), receive, send))
        await entered.wait()
        frames.clear()
        await budget(scope('thr_three'), receive, send)
        assert frames[0]['status'] == 503 and budget.active_count == 2
        first.cancel()
        await asyncio.gather(first, return_exceptions=True)
        assert budget.active_count == 1
        release.set()
        await second
        assert budget.active_count == 0 and budget._counts == {}
        await budget(scope('thr_three'), receive, send)
        assert budget.active_count == 0
    asyncio.run(scenario())
