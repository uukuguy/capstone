import socket
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock
from types import SimpleNamespace

import httpx
import pytest

from capstone_agent.application_capacity import current_capacity, initialize_capacity
from capstone_agent.general_pi_relay import ProviderRelay


@pytest.mark.parametrize('mode', ['normal', 'debug'])
def test_28_parallel_gateway_requests_queue_without_cancelling_task_or_using_model_slots(tmp_path, mode):
    import asyncio
    from threading import Thread
    from capstone_agent.general_pi_server import GeneralPiHost, make_server

    original = current_capacity()
    initialize_capacity(mode=mode)
    lock = Lock()
    active = maximum = 0
    completed = []

    class Gateway:
        catalog = {}

        async def call(self, task_id, document):
            nonlocal active, maximum
            with lock:
                active += 1
                maximum = max(maximum, active)
            try:
                await asyncio.sleep(.01)
                completed.append(document['id'])
                return {'id': document['id']}
            finally:
                with lock:
                    active -= 1

    relay = ProviderRelay(max_requests=1, per_task=1, gateway_requests=4, gateway_per_task=4)
    relay.register('task', 'grant', time.monotonic()+15)
    left, right = socket.socketpair()
    model_lease = relay.acquire('task', 'grant', left)
    runner = SimpleNamespace(relay=relay, gateway=Gateway())
    host = GeneralPiHost(root=tmp_path, identity={'engine': 'pi'}, run_task=lambda *_: ('unused', {}))
    server = make_server(host, control_token='control', address=('127.0.0.1', 0), runner=runner)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with httpx.Client(timeout=10, trust_env=False) as client, ThreadPoolExecutor(max_workers=28) as pool:
            def call(index):
                return client.post(f'http://127.0.0.1:{server.server_port}/data-gateway/task',
                                   headers={'Authorization': 'Bearer grant'}, json={'id': index})
            responses = list(pool.map(call, range(28)))
        assert all(response.status_code == 200 for response in responses)
        assert {response.json()['id'] for response in responses} == set(range(28))
        assert sorted(completed) == list(range(28))
        assert maximum <= 4
        assert relay.grants['task'] == 'grant'
        assert not model_lease.cancelled.is_set()
    finally:
        relay.release(model_lease)
        relay.revoke('task')
        server.shutdown(); server.server_close(); thread.join(timeout=1)
        left.close(); right.close()
        initialize_capacity(original)


@pytest.mark.parametrize('mode', ['normal', 'debug'])
def test_gateway_capacity_preflight_can_be_corrected_without_revoking_task(tmp_path, mode):
    from threading import Thread
    from capstone_agent.application_capacity import require_capacity
    from capstone_agent.general_pi_server import GeneralPiHost, make_server

    original = current_capacity()
    initialize_capacity({'rpc_batch_requests': 2}, mode=mode)

    class Gateway:
        catalog = {}

        def validate_batch(self, task_id, calls):
            require_capacity('rpc_batch_requests', len(calls), 'gateway_batch_preflight')
            return {'valid': True, 'executed': False}

    relay = ProviderRelay()
    relay.register('task', 'grant', time.monotonic()+10)
    host = GeneralPiHost(root=tmp_path, identity={'engine': 'pi'}, run_task=lambda *_: ('unused', {}))
    runner = SimpleNamespace(relay=relay, gateway=Gateway())
    server = make_server(host, control_token='control', address=('127.0.0.1', 0), runner=runner)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with httpx.Client(timeout=5, trust_env=False) as client:
            def submit(count):
                return client.post(f'http://127.0.0.1:{server.server_port}/data-gateway/task',
                    headers={'Authorization': 'Bearer grant'},
                    json={'operation': 'validate_batch', 'calls': [{}]*count})
            rejected = submit(3)
            assert rejected.status_code == 400
            assert rejected.json()['executed'] is False
            assert rejected.json()['capacity']['fatal'] is False
            assert rejected.json()['capacity']['limit'] == 2
            assert submit(2).status_code == 200
            assert relay.grants['task'] == 'grant'
    finally:
        relay.revoke('task')
        server.shutdown(); server.server_close(); thread.join(timeout=1)
        initialize_capacity(original)


def test_queued_request_is_not_admitted_after_revocation():
    relay = ProviderRelay(max_requests=1, per_task=1)
    relay.register('task', 'grant', time.monotonic()+5)
    left, right = socket.socketpair()
    held = relay.acquire('task', 'grant', left)
    entered = Event()
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            def waiting():
                entered.set()
                return relay.acquire('task', 'grant', left)
            future = pool.submit(waiting)
            assert entered.wait(1)
            assert not future.done()
            relay.revoke('task')
            with pytest.raises(PermissionError):
                future.result(timeout=1)
        assert held.cancelled.is_set()
    finally:
        relay.release(held)
        left.close(); right.close()
