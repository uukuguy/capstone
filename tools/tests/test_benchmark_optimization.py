from __future__ import annotations

import io
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools/benchmark_optimization.py"


def module():
    assert SCRIPT.is_file(), "resource benchmark must exist"
    return runpy.run_path(str(SCRIPT))


def test_io_probe_counts_real_stream_and_descriptor_bytes_without_duplication(tmp_path):
    probe_type = module()["IOProbe"]
    path = tmp_path / "input"
    path.write_bytes(b"abc\ndef\n")
    with probe_type() as probe:
        with path.open("rb") as stream:
            assert list(stream) == [b"abc\n", b"def\n"]
        descriptor = os.open(path, os.O_RDONLY)
        try:
            assert os.read(descriptor, 3) == b"abc"
        finally:
            os.close(descriptor)
        with io.open(tmp_path / "output", "w", encoding="utf-8") as stream:
            stream.write("中文")
    assert probe.read_bytes == 11
    assert probe.write_bytes == 6


def test_percentiles_use_nearest_rank():
    percentile = module()["percentile"]
    assert percentile([3, 1, 2], 0.5) == 2
    assert percentile([3, 1, 2], 0.95) == 3


@pytest.mark.parametrize("writes,complete,expected", [
    ([100, 1000, 10000], True, "NOT_NEEDED"),
    ([100, 10000, 1000000], True, "TRIGGERED"),
    ([100, 3000], True, "NOT_NEEDED"),
    ([100, 3001], True, "TRIGGERED"),
    ([100], False, "INCONCLUSIVE"),
    ([100], True, "INCONCLUSIVE"),
    ([100, 10000], False, "TRIGGERED"),
])
def test_storage_decision_uses_measured_per_event_growth_and_incomplete_guard(writes, complete, expected):
    rows = [
        {"events": 1000 * 10 ** index, "ledger_write_bytes": value}
        for index, value in enumerate(writes)
    ]
    assert module()["storage_decision"](rows, complete=complete)["status"] == expected


def test_tiny_real_workloads_report_validity_io_and_cache(tmp_path):
    assert SCRIPT.is_file(), "resource benchmark must exist"
    output = tmp_path / "report.json"
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--events", "4", "8", "--repeats", "3",
         "--batch-size", "2", "--output", str(output)],
        cwd=ROOT, capture_output=True, text=True, timeout=90,
    )
    assert completed.returncode == 0, completed.stderr
    report = json.loads(output.read_text())
    assert report["schema_version"] == "optimization-benchmark/1.0"
    assert report["complete"] is True and len(report["samples"]) == 6
    assert report["source"]["commit"]
    assert report["workload"]["runs_per_sample"] == 1
    assert report["decision"]["status"] == "INCONCLUSIVE"
    for sample in report["samples"]:
        assert sample["status"] == "ok"
        operations = sample["operations"]
        assert set(operations) == {"context_append", "context_replay", "run_list", "projection_cold", "projection_hot", "request_preview"}
        assert operations["context_append"]["ledger_write_bytes"] > sample["context_ledger_bytes"]
        assert operations["context_replay"]["equal"] is True
        assert operations["projection_hot"]["equal"] is True
        assert all(value == 0 for value in operations["projection_hot"]["calls"].values())
        assert operations["request_preview"]["valid"] is True
        assert operations["request_preview"]["read_bytes"] >= sample["request_artifact_bytes"]
        assert sample["peak_rss_bytes"] > 0
    assert all(row["successful_repeats"] == 3 for row in report["aggregates"])


def test_timeout_is_reported_not_silently_dropped(tmp_path):
    assert SCRIPT.is_file(), "resource benchmark must exist"
    output = tmp_path / "report.json"
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--events", "100000", "--repeats", "1",
         "--timeout-seconds", "0.01", "--output", str(output)],
        cwd=ROOT, capture_output=True, text=True, timeout=30,
    )
    assert completed.returncode != 0 and output.is_file()
    report = json.loads(output.read_text())
    assert report["complete"] is False
    assert report["samples"][0]["events"] == 100000
    assert report["samples"][0]["status"] == "timeout"
    assert report["decision"]["status"] == "INCONCLUSIVE"


@pytest.mark.parametrize("arguments", [
    ["--events", "0"], ["--events", "100001"], ["--repeats", "0"],
    ["--timeout-seconds", "nan"], ["--batch-size", "0"],
])
def test_invalid_bounds_are_rejected(arguments):
    assert SCRIPT.is_file(), "resource benchmark must exist"
    result = subprocess.run([sys.executable, str(SCRIPT), *arguments], cwd=ROOT, capture_output=True)
    assert result.returncode != 0


def test_fdopen_and_builtin_stream_reads_and_writes_are_counted_once(tmp_path):
    probe_type = module()["IOProbe"]
    path = tmp_path / "data"
    with probe_type() as probe:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.writelines([b"ab", b"cd"])
        with open(path, "rb") as stream:
            target = bytearray(4)
            assert stream.readinto(target) == 4
    assert probe.read_bytes == probe.write_bytes == 4


@pytest.mark.parametrize("buffering", [0, -1, 8192])
def test_chained_open_factories_and_fdopen_buffering_count_once(tmp_path, buffering):
    probe_type = module()["IOProbe"]
    path = tmp_path / "chained"
    def chained_open(*args, **kwargs):
        return io.open(*args, **kwargs)
    with patch("builtins.open", chained_open), probe_type() as probe:
        with open(path, "wb", buffering=buffering) as stream:
            stream.write(b"abcd")
        descriptor = os.open(path, os.O_RDONLY)
        with os.fdopen(descriptor, "rb", buffering=buffering) as stream:
            assert stream.read() == b"abcd"
    assert probe.read_bytes == probe.write_bytes == 4


def test_child_failure_retains_completed_phase_metrics(tmp_path):
    namespace = module()
    worker = tmp_path / "failed_worker.py"
    worker.write_text(
        'import json\n'
        'print(json.dumps({"type":"operation","name":"context_append","metrics":{"ledger_write_bytes":42}}), flush=True)\n'
        'print(json.dumps({"type":"phase","name":"context_replay"}), flush=True)\n'
        'raise SystemExit(7)\n',
        encoding="utf-8",
    )
    child = namespace["_child"]
    child.__globals__["__file__"] = str(worker)
    result = child(4, 1, SimpleNamespace(batch_size=2, timeout_seconds=5))
    assert result["status"] == "failed" and result["exit_code"] == 7
    assert result["phase"] == "context_replay"
    assert result["operations"]["context_append"]["ledger_write_bytes"] == 42


def test_child_malformed_progress_preserves_failure_and_scratch_location(tmp_path):
    namespace = module()
    worker = tmp_path / "broken_worker.py"
    worker.write_text(
        'import json\n'
        'print(json.dumps({"type":"phase","name":"setup","scratch_root":"/tmp/synthetic-test-only"}), flush=True)\n'
        'print("{truncated", flush=True)\n'
        'raise SystemExit(7)\n', encoding="utf-8",
    )
    child = namespace["_child"]
    child.__globals__["__file__"] = str(worker)
    result = child(4, 1, SimpleNamespace(batch_size=2, timeout_seconds=5))
    assert result["status"] == "failed" and result["exit_code"] == 7
    assert result["scratch_root"] == "/tmp/synthetic-test-only"
    assert result["progress_errors"] == 1


def test_makefile_runs_benchmark_selftests_and_exposes_explicit_long_run():
    tested = subprocess.run(["make", "-n", "test-verification-targets"], cwd=ROOT, capture_output=True, text=True, check=True)
    assert "tools/tests/test_benchmark_optimization.py" in tested.stdout
    benchmark = subprocess.run(["make", "-n", "benchmark-optimization"], cwd=ROOT, capture_output=True, text=True, check=True)
    assert "--events 1000 10000 100000" in benchmark.stdout
