from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_projection_benchmark_uses_valid_fixture_and_measures_real_work() -> None:
    script = ROOT / "tools/benchmark_projection_cache.py"
    assert script.is_file(), "reproducible projection benchmark must exist"
    result = subprocess.run(
        [sys.executable, str(script), "--sizes", "4"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    document = json.loads(result.stdout)
    assert document["schema_version"] == "projection-cache-benchmark/1.0"
    case = document["cases"][0]
    assert case["events"] == 4
    assert case["verified_events"] == 4
    assert case["event_bytes"] > 0
    assert case["cache_bytes"] > 0
    assert case["projection_equal"] is True
    assert case["cold_calls"]["materialize"] == 1
    assert case["cold_calls"]["project_agent"] == 1
    assert case["cold_seconds"] >= 0
    assert case["hot_seconds"] >= 0


def test_projection_benchmark_rejects_unbounded_invalid_sizes() -> None:
    script = ROOT / "tools/benchmark_projection_cache.py"
    assert script.is_file(), "reproducible projection benchmark must exist"
    for size in ("0", "-1", "100001"):
        result = subprocess.run(
            [sys.executable, str(script), "--sizes", size],
            cwd=ROOT, capture_output=True, text=True,
        )
        assert result.returncode != 0
