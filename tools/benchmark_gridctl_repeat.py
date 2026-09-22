"""Measure repeated real gridctl analyses without Provider calls or result reuse."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from statistics import median
from time import perf_counter
from uuid import uuid4


def _request(executable: str, workspace: Path, capability: str, arguments: dict[str, object]) -> tuple[dict[str, object], float]:
    request_id = f"benchmark-{uuid4().hex}"
    payload = {
        "protocol": "grid-capability",
        "protocol_version": "1.0",
        "request_id": request_id,
        "capability": capability,
        "arguments": arguments,
    }
    started = perf_counter()
    completed = subprocess.run(
        [executable, "request", "--workspace", str(workspace)],
        input=json.dumps(payload, ensure_ascii=False) + "\n",
        text=True,
        capture_output=True,
        check=False,
        timeout=120,
    )
    elapsed = perf_counter() - started
    if completed.returncode != 0:
        raise RuntimeError(f"gridctl {capability} exited {completed.returncode}")
    try:
        response = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"gridctl {capability} returned invalid JSON") from exc
    if (
        not isinstance(response, dict)
        or response.get("protocol") != "grid-capability"
        or response.get("protocol_version") != "1.0"
        or response.get("request_id") != request_id
        or response.get("ok") is not True
        or not isinstance(response.get("result"), dict)
    ):
        raise RuntimeError(f"gridctl {capability} did not return correlated success")
    return response["result"], elapsed


def _run_model(executable: str, scratch: Path, model_id: str, repeats: int) -> dict[str, object]:
    workspace = scratch / model_id
    workspace.mkdir()
    _environment, startup_seconds = _request(executable, workspace, "environment.describe", {})
    opened, context_seconds = _request(executable, workspace, "context.open", {"model_id": model_id})
    context_ref = opened.get("context_ref")
    if not isinstance(context_ref, str):
        raise RuntimeError("gridctl did not return a context reference")
    timings: list[float] = []
    refs: list[str] = []
    for _ in range(repeats):
        result, elapsed = _request(executable, workspace, "analysis.run", {
            "context_ref": context_ref,
            "operation": "powerflow.ac",
            "options": {},
        })
        reference = result.get("result_ref")
        if not isinstance(reference, str):
            raise RuntimeError("gridctl did not return a result reference")
        timings.append(elapsed)
        refs.append(reference)
    return {
        "model_id": model_id,
        "startup_seconds": startup_seconds,
        "context_open_seconds": context_seconds,
        "analysis_seconds": timings,
        "warm_analysis_median_seconds": median(timings[1:]),
        "same_result_ref": len(set(refs)) == 1,
        "result_refs": refs,
        "workspace_bytes": sum(path.stat().st_size for path in workspace.rglob("*") if path.is_file()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--output", type=Path, default=Path("runs/optimization/gridctl-repeat.json"))
    arguments = parser.parse_args()
    if not 2 <= arguments.repeats <= 10:
        parser.error("--repeats must be between 2 and 10")
    executable = shutil.which("gridctl")
    if executable is None:
        parser.error("gridctl is unavailable in the selected environment")
    with tempfile.TemporaryDirectory(prefix="gridctl-repeat-") as temporary:
        scratch = Path(temporary).resolve()
        models = [
            _run_model(executable, scratch, model_id, arguments.repeats)
            for model_id in ("case9", "ieee39")
        ]
    report = {
        "schema_version": "gridctl-repeat-benchmark/1.0",
        "recorded_at": datetime.now(UTC).isoformat(),
        "method": "separate gridctl process per request; wall time includes startup, load, solve and persistence",
        "repeats": arguments.repeats,
        "models": models,
    }
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
