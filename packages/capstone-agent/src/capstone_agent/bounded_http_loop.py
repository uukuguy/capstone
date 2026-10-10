"""Shared HTTP loop: cancellation never joins a per-request DNS executor."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import BoundedSemaphore, Event, Lock, Thread


class HttpLoop(asyncio.SelectorEventLoop):
    def __init__(self):
        super().__init__()
        self.dns_slots = asyncio.Semaphore(4)
        self.write_slots = asyncio.Semaphore(4)
        self.writers = ThreadPoolExecutor(max_workers=4, thread_name_prefix='capstone-http-write')
        self.set_default_executor(ThreadPoolExecutor(max_workers=4, thread_name_prefix='capstone-http-dns'))

    async def getaddrinfo(self, host, port, *, family=0, type=0, proto=0, flags=0):
        await self.dns_slots.acquire()
        pending = self.create_task(super().getaddrinfo(host, port, family=family,
                                  type=type, proto=proto, flags=flags))
        def settled(future):
            self.dns_slots.release()
            if not future.cancelled():
                future.exception()  # Consume errors even if the caller deadline has passed.
        pending.add_done_callback(settled)
        # A running OS resolver is not cancellable. Retain its slot until it stops.
        return await asyncio.shield(pending)

    async def write_once(self, function):
        await self.write_slots.acquire()
        pending = self.run_in_executor(self.writers, function)
        def settled(future):
            self.write_slots.release()
            if not future.cancelled():
                future.exception()
        pending.add_done_callback(settled)
        return await asyncio.shield(pending)


class HttpRunner:
    def __init__(self):
        self.ready = Event()
        self.slots = BoundedSemaphore(64)
        self.loop: HttpLoop | None = None
        Thread(target=self._serve, daemon=True, name='capstone-http-loop').start()
        if not self.ready.wait(2):
            raise RuntimeError('HTTP loop is unavailable')

    def _serve(self):
        self.loop = HttpLoop()
        asyncio.set_event_loop(self.loop)
        self.ready.set()
        self.loop.run_forever()

    def run(self, coroutine):
        if not self.slots.acquire(blocking=False):
            coroutine.close()
            raise RuntimeError('HTTP exchange capacity reached')
        try:
            assert self.loop is not None
            return asyncio.run_coroutine_threadsafe(coroutine, self.loop).result()
        finally:
            self.slots.release()


_lock = Lock()
_runner: HttpRunner | None = None


def run_http(coroutine):
    global _runner
    with _lock:
        if _runner is None:
            _runner = HttpRunner()
    return _runner.run(coroutine)


async def write_http(function):
    loop = asyncio.get_running_loop()
    if not isinstance(loop, HttpLoop):
        raise RuntimeError('Bounded HTTP writer requires the shared loop')
    return await loop.write_once(function)
