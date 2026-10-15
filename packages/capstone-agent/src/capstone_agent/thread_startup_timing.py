"""Bounded, secret-free timing for Thread creation and model preparation."""
from __future__ import annotations

import json
import sys
import time


def record_thread_startup(thread_id: str, phase: str, started: float) -> float:
    milliseconds = (time.perf_counter() - started) * 1000
    try:
        print(json.dumps({'event': 'thread_startup_timing', 'thread_id': thread_id,
                          'phase': phase, 'duration_ms': round(milliseconds, 3)}),
              file=sys.stderr, flush=True)
    except (OSError, ValueError):
        # A lost diagnostic stream must not fail a persisted Thread or model.
        pass
    return milliseconds
