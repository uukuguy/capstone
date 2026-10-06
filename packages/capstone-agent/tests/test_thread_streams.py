import asyncio

from capstone_agent.thread_streams import ThreadStreamBudget


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
