"""Provider-free synthetic resource benchmarks, isolated by scale and repetition."""
from __future__ import annotations

import argparse
import builtins
from contextlib import ExitStack
from datetime import UTC, datetime
import hashlib
import io
import json
import math
import os
from pathlib import Path
import platform
import resource
import subprocess
import sys
import tempfile
from time import perf_counter
from unittest.mock import patch

from capability_agent.application import context_store
from capability_agent.application.context_models import ContextEventDraft
from capability_agent.application.context_store import ApplicationContextStore
from capability_agent.application.workspace import ApplicationWorkspace
from capability_agent.trajectory.artifacts import ImmutableArtifactRegistry
from capability_agent.trajectory.canonical import canonical_json_bytes
from capability_agent.trajectory.events import EventDraft, EventRefs, ZERO_PREDECESSOR_HASH, build_event
from capability_agent.trajectory.reader import RunEventReader
from grid_agent.trajectory import service as projection_service
from grid_agent.trajectory.api.app import _canonical_request_preview
from grid_agent.trajectory.api.catalog import TrajectoryRunCatalog
from grid_agent.trajectory.materialize import ProjectionMaterializer
from grid_agent.trajectory.request_input import semantic_request_sha256

ROOT = Path(__file__).resolve().parents[1]
STATE_TEXT_BYTES = 256
REQUEST_TEXT_BYTES = 65536
PROJECTORS = ("project_agent", "project_business", "project_context", "project_artifacts", "project_core_timeline")


class _StreamProbe:
    def __init__(self, stream, probe):
        self.stream, self.probe = stream, probe

    def __getattr__(self, name):
        return getattr(self.stream, name)

    def __enter__(self):
        self.stream.__enter__()
        return self

    def __exit__(self, *args):
        return self.stream.__exit__(*args)

    def _size(self, value):
        return len(value.encode(self.stream.encoding or "utf-8")) if isinstance(value, str) else len(value)

    def read(self, *args, **kwargs):
        value = self.stream.read(*args, **kwargs)
        self.probe.read_bytes += self._size(value)
        return value

    def readline(self, *args, **kwargs):
        value = self.stream.readline(*args, **kwargs)
        self.probe.read_bytes += self._size(value)
        return value

    def readlines(self, *args, **kwargs):
        values = self.stream.readlines(*args, **kwargs)
        self.probe.read_bytes += sum(self._size(value) for value in values)
        return values

    def readinto(self, buffer):
        count = self.stream.readinto(buffer)
        self.probe.read_bytes += count or 0
        return count

    def write(self, value):
        count = self.stream.write(value)
        self.probe.write_bytes += self._size(value[:count])
        return count

    def writelines(self, values):
        for value in values:
            self.write(value)

    def __iter__(self):
        return self

    def __next__(self):
        line = self.readline()
        if not line:
            raise StopIteration
        return line


class IOProbe:
    """Python logical I/O, not syscalls or physical disk traffic."""
    def __init__(self):
        self.read_bytes = self.write_bytes = 0
        self.stack = ExitStack()

    def __enter__(self):
        for owner, name in ((io, "open"), (builtins, "open"), (os, "fdopen")):
            original = getattr(owner, name)
            def opened(*args, _original=original, **kwargs):
                stream = _original(*args, **kwargs)
                if isinstance(stream, _StreamProbe) and stream.probe is self:
                    return stream
                return _StreamProbe(stream, self)
            self.stack.enter_context(patch.object(owner, name, opened))
        read, write = os.read, os.write
        def counted_read(*args):
            value = read(*args)
            self.read_bytes += len(value)
            return value
        def counted_write(descriptor, value):
            count = write(descriptor, value)
            self.write_bytes += count
            return count
        self.stack.enter_context(patch.object(os, "read", counted_read))
        self.stack.enter_context(patch.object(os, "write", counted_write))
        return self

    def __exit__(self, *args):
        return self.stack.__exit__(*args)


def percentile(values, fraction):
    ordered = sorted(values)
    if not ordered:
        raise ValueError("percentile requires samples")
    return ordered[max(0, math.ceil(len(ordered) * fraction) - 1)]


def storage_decision(rows, *, complete):
    comparisons = []
    ordered = sorted(rows, key=lambda row: row["events"])
    for previous, current in zip(ordered, ordered[1:]):
        if current["events"] != previous["events"] * 10:
            continue
        if previous["ledger_write_bytes"] <= 0:
            continue
        ratio = current["ledger_write_bytes"] / previous["ledger_write_bytes"]
        comparisons.append({
            "from_events": previous["events"], "to_events": current["events"],
            "cumulative_write_ratio": ratio,
            "mean_per_event_ratio": ratio / 10,
        })
    consecutive = any(
        left["to_events"] == right["from_events"]
        and left["cumulative_write_ratio"] > 30 and right["cumulative_write_ratio"] > 30
        for left, right in zip(comparisons, comparisons[1:])
    )
    triggered = consecutive or any(row["mean_per_event_ratio"] > 3 for row in comparisons)
    status = "TRIGGERED" if triggered else ("NOT_NEEDED" if complete and comparisons else "INCONCLUSIVE")
    return {"status": status, "comparisons": comparisons, "scope": "measured requested scales only"}


def _rss_bytes():
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if sys.platform == "darwin" else value * 1024)


def _emit(document):
    print(json.dumps(document, sort_keys=True), flush=True)


def _measure(name, operation, operations):
    _emit({"type": "phase", "name": name})
    started = perf_counter()
    with IOProbe() as probe:
        result = operation()
    metrics = {
        "seconds": perf_counter() - started, "read_bytes": probe.read_bytes,
        "write_bytes": probe.write_bytes, "rss_high_water_bytes": _rss_bytes(),
    }
    operations[name] = metrics
    return result, metrics


def _record(name, metrics):
    _emit({"type": "operation", "name": name, "metrics": metrics})


def _request_document():
    semantic = {
        "model": {"provider": "synthetic", "api": "synthetic", "id": "benchmark"},
        "context": {"system_prompt": "Synthetic benchmark, no provider invocation.",
                    "messages": [{"role": "user", "content": [{"type": "text", "text": "x" * REQUEST_TEXT_BYTES}]}],
                    "tools": []},
        "options": {},
    }
    return {
        "schema_version": "grid-model-request-input/2.0", "request_id": "request-benchmark",
        "request_index": 1, "turn_id": "benchmark-t001",
        "captured_at": "2026-09-05T00:00:00Z", "source_event_sequences": [2],
        "context_revision": 0, "context_state_hash": "0" * 64,
        "runtime": {"pi_coding_agent_version": "0.84.4", "pi_ai_version": "0.84.4",
                    "pi_source_commit": "1" * 40, "pi_patch_set_sha256": "2" * 64},
        "semantic_request": semantic, "semantic_request_sha256": semantic_request_sha256(semantic),
    }


def _trajectory_fixture(run, size):
    run.mkdir(parents=True)
    pointer = ImmutableArtifactRegistry(run).write_json("request-input", "request-benchmark", _request_document())
    path = run / "events/run-events.jsonl"
    path.parent.mkdir()
    predecessor = ZERO_PREDECESSOR_HASH
    with path.open("wb") as stream:
        for sequence in range(1, size + 1):
            if sequence == 1:
                draft = EventDraft(event_type="analysis.started")
            elif sequence == size:
                draft = EventDraft(event_type="analysis.completed", payload={"completed_turns": 0, "total_turns": 0})
            else:
                draft = EventDraft(
                    event_type="audit.diagnostic.recorded",
                    payload={"severity": "info", "category": "benchmark", "message": "synthetic event"},
                    refs=EventRefs(produced=(pointer.ref,) if sequence == 2 else ()),
                )
            event = build_event(draft, analysis_id=run.name, sequence=sequence,
                                timestamp=datetime(2026, 9, 5, tzinfo=UTC), previous_event_hash=predecessor)
            predecessor = event.event_hash
            stream.write(canonical_json_bytes(event.model_dump(mode="json")))
    (run / "manifest.json").write_bytes(canonical_json_bytes({
        "schema_version": "grid-agent-analysis-manifest/1.0", "analysis_id": run.name,
        "status": "completed", "total_turns": 0, "events_path": "events/run-events.jsonl",
    }))
    prefix = RunEventReader(path).read_prefix()
    if prefix.failure is not None or len(prefix.events) != size:
        raise ValueError("synthetic trajectory is not a complete valid prefix")
    return pointer


def run_sample(size, batch_size):
    operations = {}
    _emit({"type": "phase", "name": "setup"})
    with tempfile.TemporaryDirectory(prefix="optimization-benchmark-") as temporary:
        root = Path(temporary).resolve(strict=True)
        _emit({"type": "phase", "name": "setup", "scratch_root": str(root)})
        workspace = ApplicationWorkspace.create(root / "context", "benchmark", ("benchmark",))
        store = ApplicationContextStore.initialize(workspace, domains={"benchmark": "benchmark-state/1.0"})
        staging = {"final": 0, "backup": 0}
        original_stage = context_store._stage_bytes
        def stage(path, payload, *, label):
            result = original_stage(path, payload, label=label)
            if path == workspace.context_events_path:
                staging["backup" if label.endswith("backup") else "final"] += len(payload)
            return result
        def append():
            with patch.object(context_store, "_stage_bytes", stage):
                for start in range(0, size, batch_size):
                    store.append_many(
                        ContextEventDraft(
                            event_type="domain.state.projected", binding_id="benchmark",
                            payload={"schema_id": "benchmark-state/1.0", "previous_revision": revision,
                                     "state": {"text": "x" * STATE_TEXT_BYTES}},
                        )
                        for revision in range(start, min(start + batch_size, size))
                    )
        _, metric = _measure("context_append", append, operations)
        metric.update(ledger_write_bytes=sum(staging.values()), ledger_staging_bytes=staging, appended_events=size)
        if metric["ledger_write_bytes"] <= 0:
            raise ValueError("ledger instrumentation did not observe the active storage backend")
        _record("context_append", metric)
        replayed, metric = _measure("context_replay", lambda: ApplicationContextStore.replay(workspace), operations)
        metric["equal"] = replayed == store.snapshot
        if not metric["equal"]:
            raise ValueError("context replay differs from committed state")
        _record("context_replay", metric)

        _emit({"type": "phase", "name": "trajectory_setup"})
        run = root / "runs/benchmark"
        pointer = _trajectory_fixture(run, size)
        service = projection_service.ProjectionService(root / "cache")
        catalog = TrajectoryRunCatalog(root / "runs", root / "cache", service)
        listed, metric = _measure("run_list", catalog.list_runs, operations)
        metric["run_count"] = len(listed)
        if len(listed) != 1:
            raise ValueError("synthetic run was not listed")
        _record("run_list", metric)
        calls = {}
        with ExitStack() as stack:
            for owner, name in [(projection_service, name) for name in PROJECTORS] + [(ProjectionMaterializer, "write")]:
                original = getattr(owner, name)
                calls[name] = 0
                def counted(*args, _original=original, _name=name, **kwargs):
                    calls[_name] += 1
                    return _original(*args, **kwargs)
                stack.enter_context(patch.object(owner, name, counted))
            cold, metric = _measure("projection_cold", lambda: service.open_run(run), operations)
            metric["calls"] = dict(calls)
            _record("projection_cold", metric)
            before = dict(calls)
            hot, metric = _measure("projection_hot", lambda: service.open_run(run), operations)
            metric.update(calls={name: value - before[name] for name, value in calls.items()}, equal=cold == hot)
            if not metric["equal"] or any(metric["calls"].values()):
                raise ValueError("hot projection rebuilt or differed")
            _record("projection_hot", metric)
        (preview, omitted), metric = _measure("request_preview", lambda: _canonical_request_preview(hot, run, pointer.ref), operations)
        metric["valid"] = not omitted and preview is not None and preview["semantic_request_sha256"] == _request_document()["semantic_request_sha256"]
        if not metric["valid"]:
            raise ValueError("real request preview failed")
        _record("request_preview", metric)
        return {
            "status": "ok", "events": size, "operations": operations,
            "context_ledger_bytes": workspace.context_events_path.stat().st_size,
            "context_ledger_events": size + 1, "trajectory_events": size,
            "request_artifact_bytes": pointer.size_bytes, "peak_rss_bytes": _rss_bytes(),
        }


def _bounded_integer(low, high):
    def parse(value):
        try:
            number = int(value)
        except ValueError as exc:
            raise argparse.ArgumentTypeError("must be an integer") from exc
        if not low <= number <= high:
            raise argparse.ArgumentTypeError(f"must be between {low} and {high}")
        return number
    return parse


def _timeout(value):
    number = float(value)
    if not math.isfinite(number) or not 0 < number <= 3600:
        raise argparse.ArgumentTypeError("timeout must be finite and in (0, 3600]")
    return number


def _child(size, repeat, args):
    command = [sys.executable, str(Path(__file__).resolve()), "--worker-events", str(size),
               "--batch-size", str(args.batch_size)]
    started = perf_counter()
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=args.timeout_seconds)
    except subprocess.TimeoutExpired:
        timed_out = True
        process.kill()
        stdout, stderr = process.communicate()
    sample = {
        "events": size, "repeat": repeat, "status": "timeout" if timed_out else "failed",
        "phase": "startup", "operations": {}, "elapsed_seconds": perf_counter() - started,
        "timeout_seconds": args.timeout_seconds, "exit_code": process.returncode,
        "stderr_tail": stderr[-4096:], "stderr_truncated": len(stderr) > 4096,
        "progress_errors": 0,
    }
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
            if event["type"] == "phase":
                sample["phase"] = event["name"]
                if "scratch_root" in event:
                    sample["scratch_root"] = event["scratch_root"]
            elif event["type"] == "operation":
                sample["operations"][event["name"]] = event["metrics"]
            elif event["type"] == "done":
                if process.returncode == 0 and not timed_out:
                    sample.update(event["result"])
            else:
                raise ValueError("unknown progress record")
        except (ValueError, KeyError, TypeError):
            sample["progress_errors"] += 1
    if sample["progress_errors"]:
        sample["status"] = "timeout" if timed_out else "failed"
        sample["stdout_tail"] = stdout[-4096:]
        sample["stdout_truncated"] = len(stdout) > 4096
    return sample


def _node_version():
    try:
        result = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def _aggregate(samples, sizes, repeats):
    aggregates, decision_rows = [], []
    for size in sizes:
        selected = [sample for sample in samples if sample["events"] == size]
        operations = {}
        for name in sorted({key for sample in selected for key in sample["operations"]}):
            metrics = [sample["operations"][name] for sample in selected if name in sample["operations"]]
            operations[name] = {
                key: {"p50": percentile([item[key] for item in metrics], 0.5),
                      "p95": percentile([item[key] for item in metrics], 0.95)}
                for key in ("seconds", "read_bytes", "write_bytes", "rss_high_water_bytes")
            }
            operations[name]["successful_repeats"] = len(metrics)
        append = [sample["operations"]["context_append"] for sample in selected if "context_append" in sample["operations"]]
        if len(append) == repeats:
            decision_rows.append({"events": size, "ledger_write_bytes": percentile([item["ledger_write_bytes"] for item in append], 0.5)})
        aggregates.append({"events": size, "successful_repeats": sum(sample["status"] == "ok" for sample in selected),
                           "operations": operations})
    return aggregates, decision_rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", nargs="+", type=_bounded_integer(3, 100000), default=[1000, 10000, 100000])
    parser.add_argument("--repeats", type=_bounded_integer(1, 10), default=3)
    parser.add_argument("--batch-size", type=_bounded_integer(1, 10000), default=100)
    parser.add_argument("--timeout-seconds", type=_timeout, default=300.0)
    parser.add_argument("--output", type=Path, default=Path("runs/optimization/benchmarks/report.json"))
    parser.add_argument("--worker-events", type=_bounded_integer(3, 100000), help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker_events is not None:
        _emit({"type": "done", "result": run_sample(args.worker_events, args.batch_size)})
        return 0
    if len(set(args.events)) != len(args.events):
        parser.error("event sizes must be unique")
    source = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.splitlines()
    samples = []
    for size in args.events:
        for repeat in range(1, args.repeats + 1):
            sample = _child(size, repeat, args)
            samples.append(sample)
            print(f"events={size} repeat={repeat} status={sample['status']} phase={sample['phase']}", file=sys.stderr, flush=True)
    complete = all(sample["status"] == "ok" for sample in samples)
    aggregates, rows = _aggregate(samples, args.events, args.repeats)
    report = {
        "schema_version": "optimization-benchmark/1.0", "created_at": datetime.now(UTC).isoformat(),
        "environment": {"python": platform.python_version(), "platform": platform.platform(),
                        "machine": platform.machine(), "node": _node_version()},
        "source": {"commit": source, "dirty_paths": dirty, "benchmark_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
        "workload": {"event_sizes": args.events, "repeats": args.repeats, "append_batch_size": args.batch_size,
                     "state_text_bytes": STATE_TEXT_BYTES, "request_text_bytes": REQUEST_TEXT_BYTES, "runs_per_sample": 1,
                     "sample_timeout_seconds": args.timeout_seconds},
        "limitations": [
            "Synthetic fixed-state projections isolate ledger cost; not business or growing-state latency.",
            "Logical Python I/O with instrumentation overhead, not physical disk traffic.",
            "RSS is cumulative child-process high-water, not independent per-operation peak.",
            "Cold is a projection cache miss, not an OS page-cache flush.",
            "Preview is the real canonical-request file helper, not browser rendering or end-to-end HTTP.",
            "Three-sample nearest-rank p95 is the maximum, not a production latency estimate.",
        ],
        "complete": complete, "samples": samples, "aggregates": aggregates,
        "decision": storage_decision(rows, complete=complete),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "complete": complete, "decision": report["decision"]["status"]}))
    return 0 if complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
