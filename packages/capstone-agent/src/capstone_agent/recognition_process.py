"""One bounded tool-free process; every new task starts with empty model history."""
from contextlib import contextmanager
import tempfile
import threading
import time
from pathlib import Path


class RecognitionProcess:
    def __init__(self):
        self._lock = threading.RLock()
        self._directory = None
        self._client = None
        self._uses = 0
        self._last_used = 0.0

    @contextmanager
    def lease(self, create, *, on_heartbeat, timeout_seconds):
        with self._lock:
            if self._uses >= 32 or time.monotonic() - self._last_used > 180:
                self.close()
            reused = self._client is not None
            try:
                if reused:
                    assert self._client is not None
                    self._client.new_session(timeout_seconds=timeout_seconds, on_heartbeat=on_heartbeat)
                else:
                    self._directory = tempfile.TemporaryDirectory(prefix="capstone-recognition-")
                    self._client = create(Path(self._directory.name).resolve())
                assert self._client is not None
                yield self._client, reused
                self._uses += 1
                self._last_used = time.monotonic()
            except BaseException:
                self.close()
                raise

    def close(self):
        with self._lock:
            try:
                if self._client is not None:
                    self._client.stop()
            finally:
                self._client = None
                if self._directory is not None:
                    self._directory.cleanup()
                self._directory = None
                self._uses = 0

    def sweep_idle(self):
        with self._lock:
            if self._client is not None and time.monotonic() - self._last_used > 180:
                self.close()
                return 1
            return 0
