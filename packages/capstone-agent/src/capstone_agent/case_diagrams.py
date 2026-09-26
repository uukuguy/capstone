"""Bounded, cached case diagrams obtained from registered application authorities."""

from __future__ import annotations

import json
import os
import subprocess
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Callable

from capstone_agent.network_diagram import MAX_DIAGRAM_BYTES, normalize_network_diagram
from capstone_agent.session import WorkerSpec, _worker_environment


def load_case_diagram(spec: WorkerSpec, case_id: str) -> dict[str, object]:
    if spec.preview_command is None or spec.scripted_cases is None or case_id not in spec.scripted_cases:
        raise ValueError("case diagram is not registered")
    completed = subprocess.run(
        [*spec.preview_command, "--case", case_id], cwd=spec.cwd,
        env=_worker_environment(spec.environment or os.environ, "scripted-demo"),
        capture_output=True, timeout=240, check=False,
    )
    if (completed.returncode != 0 or not completed.stdout or
            len(completed.stdout) > MAX_DIAGRAM_BYTES + 65_536):
        raise ValueError("case diagram authority is unavailable")
    try:
        document = json.loads(completed.stdout)
        return normalize_network_diagram(document)
    except (UnicodeDecodeError, ValueError, TypeError) as exc:
        raise ValueError("case diagram authority returned an invalid projection") from exc


class CaseDiagramCache:
    def __init__(self, cases: dict[tuple[str, str], WorkerSpec],
                 loader: Callable[[WorkerSpec, str], dict[str, object]] = load_case_diagram) -> None:
        self.cases = cases
        self.loader = loader
        self._pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="case-diagram")
        self._pending: dict[tuple[str, str], Future[dict[str, object]]] = {}
        self._lock = threading.Lock()

    def prewarm(self) -> None:
        for key in self.cases:
            self._future(key)

    def _future(self, key: tuple[str, str]) -> Future[dict[str, object]]:
        with self._lock:
            if key not in self._pending:
                spec = self.cases[key]
                self._pending[key] = self._pool.submit(self.loader, spec, key[1])
            return self._pending[key]

    def get(self, application_id: str, case_id: str) -> dict[str, object]:
        key = (application_id, case_id)
        if key not in self.cases:
            raise KeyError("case diagram is not registered")
        future = self._future(key)
        try:
            return normalize_network_diagram(future.result(timeout=240))
        except Exception:
            with self._lock:
                if self._pending.get(key) is future:
                    del self._pending[key]
            raise

    def close(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)
