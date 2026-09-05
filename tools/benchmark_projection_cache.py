"""Provider-free, synthetic cold/hot projection measurements; JSON on stdout."""

from __future__ import annotations

import argparse
from contextlib import ExitStack
from datetime import UTC, datetime
import json
from pathlib import Path
import platform
import tempfile
from time import perf_counter
from unittest.mock import patch

from capability_agent.trajectory.canonical import canonical_json_bytes
from capability_agent.trajectory.events import EventDraft, ZERO_PREDECESSOR_HASH, build_event
from capability_agent.trajectory.reader import RunEventReader
from grid_agent.trajectory import service as projection_service
from grid_agent.trajectory.materialize import ProjectionMaterializer


def bounded_size(value: str) -> int:
    size = int(value)
    if not 2 <= size <= 100_000:
        raise argparse.ArgumentTypeError("event count must be between 2 and 100000")
    return size


def write_fixture(run: Path, size: int) -> Path:
    """Generate a valid chain directly, avoiding recorder/fsync setup costs."""
    events_path = run / "events/run-events.jsonl"
    events_path.parent.mkdir(parents=True)
    timestamp = datetime(2026, 9, 5, tzinfo=UTC)
    predecessor = ZERO_PREDECESSOR_HASH
    with events_path.open("wb") as stream:
        for sequence in range(1, size + 1):
            if sequence == 1:
                draft = EventDraft(event_type="analysis.started")
            elif sequence == size:
                draft = EventDraft(
                    event_type="analysis.completed",
                    payload={"completed_turns": 0, "total_turns": 0},
                )
            else:
                draft = EventDraft(
                    event_type="audit.diagnostic.recorded",
                    payload={"severity": "info", "category": "benchmark", "message": "synthetic event"},
                )
            event = build_event(
                draft, analysis_id=run.name, sequence=sequence,
                timestamp=timestamp, previous_event_hash=predecessor,
            )
            predecessor = event.event_hash
            stream.write(canonical_json_bytes(event.model_dump(mode="json")))
    (run / "manifest.json").write_bytes(canonical_json_bytes({
        "schema_version": "grid-agent-analysis-manifest/1.0",
        "analysis_id": run.name, "status": "completed", "total_turns": 0,
        "events_path": "events/run-events.jsonl",
    }))
    return events_path


def observe(stack: ExitStack, owner: object, name: str, counts: dict[str, int], label: str) -> None:
    original = getattr(owner, name)
    counts[label] = 0

    def counted(*args: object, **kwargs: object) -> object:
        counts[label] += 1
        return original(*args, **kwargs)

    stack.enter_context(patch.object(owner, name, counted))


def measure_case(size: int) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="projection-benchmark-") as directory:
        # Canonicalize our newly created temporary root (macOS /var is an
        # alias); the cache itself deliberately rejects symlink traversal.
        base = Path(directory).resolve(strict=True)
        run = base / "runs" / f"benchmark-{size}"
        events_path = write_fixture(run, size)
        prefix = RunEventReader(events_path).read_prefix()
        if prefix.failure is not None or len(prefix.events) != size:
            raise RuntimeError("benchmark fixture did not produce a complete valid prefix")
        verified_events = len(prefix.events)
        del prefix
        cache = base / "cache"
        service = projection_service.ProjectionService(cache)
        counts: dict[str, int] = {}
        with ExitStack() as stack:
            for name in ("project_agent", "project_business", "project_context", "project_artifacts", "project_core_timeline"):
                observe(stack, projection_service, name, counts, name)
            observe(stack, ProjectionMaterializer, "write", counts, "materialize")
            started = perf_counter()
            cold = service.open_run(run)
            cold_seconds = perf_counter() - started
            cold_calls = dict(counts)
            started = perf_counter()
            hot = service.open_run(run)
            hot_seconds = perf_counter() - started
            hot_calls = {name: count - cold_calls[name] for name, count in counts.items()}
        return {
            "events": size, "verified_events": verified_events,
            "event_bytes": events_path.stat().st_size,
            "cold_seconds": cold_seconds, "hot_seconds": hot_seconds,
            "cold_calls": cold_calls, "hot_calls": hot_calls,
            "projection_equal": cold == hot,
            "cache_bytes": sum(path.stat().st_size for path in cache.rglob("*") if path.is_file()),
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", type=bounded_size, nargs="+", default=[1000, 10_000, 100_000])
    args = parser.parse_args()
    print(json.dumps({
        "schema_version": "projection-cache-benchmark/1.0",
        "python": platform.python_version(), "platform": platform.platform(),
        "fixture": "hash-chained lifecycle/diagnostic events without external artifacts",
        "timing_scope": "open_run only; generation and fixture validation excluded; cold is a projection-cache miss, not a cold OS page cache",
        "limitations": "synthetic single-process single-sample cold/hot pair; not production latency or artifact I/O scaling",
        "cases": [measure_case(size) for size in args.sizes],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
