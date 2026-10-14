"""Application cache for immutable registered model geometry, never task layers."""
from collections import OrderedDict
from collections.abc import Callable
import json
from threading import RLock
from typing import Any

from .memory_pressure import worker_memory_pressure


class RegisteredDiagramCache:
    def __init__(self, loader: Callable[[str, str], dict[str, Any]], *,
                 max_bytes: int = 16 * 1024 * 1024,
                 memory_pressure: Callable[[], bool] = worker_memory_pressure) -> None:
        if max_bytes < 1:
            raise ValueError('diagram cache budget must be positive')
        self._loader = loader
        self._budget = max_bytes
        self._pressure = memory_pressure
        self._entries: OrderedDict[tuple[str, str], bytes] = OrderedDict()
        self._bytes = 0
        self._lock = RLock()

    def __call__(self, model_id: str, revision: str) -> dict[str, Any]:
        key = model_id, revision
        # Coalesce concurrent requests. Exporters allocate independent Authority
        # processes; serial cold loads also bound their memory use.
        with self._lock:
            if self._pressure():
                self._entries.clear()
                self._bytes = 0
            cached = self._entries.get(key)
            if cached is not None:
                self._entries.move_to_end(key)
                return json.loads(cached)
            value = self._loader(model_id, revision)
            model = value.get('model', {})
            if model.get('id') != model_id or model.get('revision') != revision:
                raise ValueError('registered diagram identity mismatch')
            encoded = json.dumps(value, ensure_ascii=False, allow_nan=False).encode()
            if not self._pressure() and len(encoded) <= self._budget:
                while self._entries and self._bytes + len(encoded) > self._budget:
                    _, removed = self._entries.popitem(last=False)
                    self._bytes -= len(removed)
                self._entries[key] = encoded
                self._bytes += len(encoded)
            return value
