"""Native Thread worker using the shared ledger, lease loop, and Pi runtime.

This process has no Authority or professional model catalog. The isolated Pi
host retains its existing private control and Provider transport boundaries.
"""
import os
import threading
from pathlib import Path

from .general_executor_composition import configured_general_executor
from .intent_runtime import IntentRuntimeFactory
from .thread_service import PostgresThreadService
from .thread_worker import serve_thread_attempts
from .worker_wake import create_wake_app


def native_runtime_factory(executor, *, research_root: Path | None = None):
    def unavailable(*args):
        raise RuntimeError('professional execution is not registered on this worker')
    factory = IntentRuntimeFactory(unavailable, unavailable, unavailable,
                                   general_executor=executor)
    factory.native_research_root = research_root
    return factory


def main() -> int:
    import uvicorn
    from .hosting import load_host_settings
    settings = load_host_settings(os.environ)
    executor = configured_general_executor(os.environ)
    if executor is None:
        raise RuntimeError('native conversation executor is not configured')
    service = PostgresThreadService(settings.database_url)
    service.initialize()
    service.set_native_executor(executor)
    factory = native_runtime_factory(executor, research_root=settings.runs_root / 'native-research')
    stop, wake = threading.Event(), threading.Event()
    scheduler = threading.Thread(target=serve_thread_attempts, kwargs={
        'service': service, 'runtime_factory': factory,
        'worker_id': 'capstone-native-worker', 'implementation_family': 'native',
        'wake_event': wake, 'stop_event': stop}, daemon=True, name='capstone-native-worker')
    scheduler.start()
    try:
        uvicorn.run(create_wake_app(wake, settings.operator_token,
            implementation_family='native', input_catalog=service.input_catalog,
            thread_family=lambda _: 'native', health_check=scheduler.is_alive),
            host=settings.bind_host, port=settings.port, access_log=False)
    finally:
        stop.set()
        wake.set()
        scheduler.join(timeout=5)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
