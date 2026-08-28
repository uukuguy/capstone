#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
STATE_DIR=${CLIMB_STATE_DIR:-"$ROOT/docs/status/climb"}
if [ "$#" -ge 1 ]; then
  RUN_DIR=$1
  mkdir -p "$RUN_DIR"
else
  ARTIFACT_DIR=${CLIMB_ARTIFACT_DIR:-"$ROOT/runs/climb"}
  mkdir -p "$ARTIFACT_DIR"
  RUN_DIR=$(mktemp -d "$ARTIFACT_DIR/eval-XXXXXX")
fi

python3 - "$ROOT" "$STATE_DIR" "$RUN_DIR" <<'PY'
from __future__ import annotations

import json
import csv
import os
import subprocess
import sys
from pathlib import Path


root = Path(sys.argv[1])
state_dir = Path(sys.argv[2])
run_dir = Path(sys.argv[3])
config = json.loads((state_dir / "config.yaml").read_text(encoding="utf-8"))
manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
hypothesis_id = manifest["hypothesis_id"]
weights = {key: float(value) for key, value in config["score_weights"].items()}
gates = config.get("score_gates", {})
hypotheses = json.loads((state_dir / "hypotheses.yaml").read_text(encoding="utf-8"))["hypotheses"]
hypothesis = next((item for item in hypotheses if item["id"] == hypothesis_id), None)
if hypothesis is None:
    raise SystemExit(f"unknown hypothesis: {hypothesis_id}")
focused_gate = hypothesis.get("focused_gate")
if focused_gate not in weights:
    raise SystemExit(f"unknown focused gate for {hypothesis_id}: {focused_gate}")


def artifact_dir() -> Path:
    raw = os.environ.get("CLIMB_ARTIFACT_DIR") or str(config.get("artifact_dir", "runs/climb"))
    path = Path(raw)
    return path if path.is_absolute() else root / path


def stable_path(path: Path) -> str:
    resolved = path.resolve()
    for base in (root.resolve(), artifact_dir().resolve(), state_dir.resolve()):
        try:
            return resolved.relative_to(base).as_posix()
        except ValueError:
            continue
    return path.name


def current_source_commit() -> str:
    override = os.environ.get("CLIMB_SOURCE_COMMIT")
    if override:
        return override
    completed = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise SystemExit(completed.stderr.strip() or "could not resolve source commit")
    return completed.stdout.strip()


def resolve_path(raw: str) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else root / path


def resolve_artifact_or_root_path(raw: str) -> Path:
    path = Path(raw)
    if path.is_absolute():
        return path
    root_path = root / path
    if root_path.exists():
        return root_path
    return artifact_dir() / path


def run_gate(key: str, gate: dict[str, object]) -> tuple[float, dict[str, object]]:
    required_paths = [resolve_path(str(item)) for item in gate.get("required_paths", [])]
    missing = [path for path in required_paths if not path.exists()]
    if missing:
        return 0.0, {"status": "missing", "missing_paths": [stable_path(path) for path in missing]}

    command = gate.get("command")
    if not command:
        return 0.0, {"status": "missing", "missing_command": True}
    if not isinstance(command, list):
        raise SystemExit(f"score gate {key} command must be a list")

    completed = subprocess.run(
        [str(part) for part in command],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    evidence = {
        "artifact_path": stable_path(output_path(key, completed)),
        "status": "passed" if completed.returncode == 0 else "failed",
        "command": [str(part) for part in command],
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }
    return (weights[key] if completed.returncode == 0 else 0.0), evidence


def owns_hypothesis(gate: dict[str, object]) -> bool:
    if gate.get("hypothesis_id") == hypothesis_id:
        return True
    return hypothesis_id in gate.get("hypothesis_ids", [])


def output_path(key: str, completed: subprocess.CompletedProcess[str]) -> Path:
    path = run_dir / f"gate-output-{key}.json"
    path.write_text(
        json.dumps(
            {
                "command": [str(part) for part in completed.args],
                "returncode": completed.returncode,
                "stderr": completed.stderr,
                "stdout": completed.stdout,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def run_rows() -> dict[str, dict[str, str]]:
    runs_path = state_dir / "runs.csv"
    if not runs_path.is_file():
        return {}
    with runs_path.open(newline="", encoding="utf-8") as handle:
        return {row["run_id"]: row for row in csv.DictReader(handle)}


def carry_forward(key: str) -> tuple[float, dict[str, object]] | None:
    rows = run_rows()
    for event in reversed(json.loads((state_dir / "hypotheses.yaml").read_text(encoding="utf-8")).get("events", [])):
        if event.get("status") != "confirmed":
            continue
        if float(event.get("per_task", {}).get(key, 0.0)) != weights[key]:
            continue
        source_run_id = str(event.get("run_id", ""))
        row = rows.get(source_run_id, {})
        manifest_path = str(row.get("manifest_path") or "")
        if not manifest_path:
            return None
        manifest_file = resolve_artifact_or_root_path(manifest_path)
        local_eval_file = manifest_file.with_name("local-eval.json")
        if not local_eval_file.is_file():
            return None
        source_eval = json.loads(local_eval_file.read_text(encoding="utf-8"))
        source_evidence = source_eval.get("gate_evidence", {}).get(key, {})
        if source_evidence.get("status") != "passed":
            return None
        return weights[key], {
            "artifact_path": stable_path(local_eval_file),
            "command": [str(part) for part in source_evidence.get("command", [])],
            "returncode": source_evidence.get("returncode"),
            "source_hypothesis_id": event.get("hypothesis_id"),
            "source_run_id": source_run_id,
            "status": "carried-forward",
        }
    return None


def default_receipt_path(key: str) -> Path:
    return artifact_dir() / "gate-receipts" / f"{key}.json"


def validate_receipt(key: str, gate: dict[str, object]) -> tuple[float, dict[str, object]]:
    raw_path = str(gate.get("receipt_path") or default_receipt_path(key))
    receipt_path = resolve_path(raw_path) if not Path(raw_path).is_absolute() else Path(raw_path)
    if not receipt_path.is_file():
        return 0.0, {"artifact_path": stable_path(receipt_path), "status": "missing-receipt"}
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    command = [str(part) for part in gate.get("command", [])]
    evidence = {
        "artifact_path": stable_path(receipt_path),
        "command": receipt.get("command", []),
        "output_artifact_path": receipt.get("output_artifact_path", ""),
        "returncode": receipt.get("returncode"),
        "source_commit": receipt.get("source_commit"),
    }
    if receipt.get("gate_key") != key:
        return 0.0, {**evidence, "status": "receipt-gate-mismatch"}
    if [str(part) for part in receipt.get("command", [])] != command:
        return 0.0, {**evidence, "status": "receipt-command-mismatch"}
    if receipt.get("source_commit") != current_source_commit():
        return 0.0, {**evidence, "status": "stale-receipt"}
    if int(receipt.get("returncode", 1)) != 0 or receipt.get("status") != "passed":
        return 0.0, {**evidence, "status": "failed-receipt"}
    return weights[key], {**evidence, "status": "receipt-passed"}


per_task: dict[str, float] = {}
gate_evidence: dict[str, dict[str, object]] = {}
for key in weights:
    gate = gates.get(key, {})
    if key != focused_gate and gate.get("receipt_required"):
        per_task[key], gate_evidence[key] = validate_receipt(key, gate)
        continue
    if key != focused_gate:
        carried = carry_forward(key)
        if carried is not None:
            per_task[key], gate_evidence[key] = carried
            continue
        required_paths = [resolve_path(str(item)) for item in gate.get("required_paths", [])]
        missing = [path for path in required_paths if not path.exists()]
        if missing:
            per_task[key] = 0.0
            gate_evidence[key] = {"status": "missing", "missing_paths": [stable_path(path) for path in missing]}
        else:
            per_task[key] = 0.0
            gate_evidence[key] = {"status": "not-focused", "focused_gate": focused_gate}
        continue
    if not owns_hypothesis(gate):
        per_task[key] = 0.0
        gate_evidence[key] = {
            "status": "not-owned-by-hypothesis",
            "hypothesis_id": gate.get("hypothesis_id"),
            "hypothesis_ids": gate.get("hypothesis_ids", []),
        }
        continue
    per_task[key], gate_evidence[key] = run_gate(key, gate)

hypothesis_gate_passed = gate_evidence[focused_gate]["status"] == "passed"
total = sum(per_task.values())
release_blockers = [
    f"{key}: {gate_evidence[key]['status']}"
    for key in weights
    if per_task[key] != weights[key] or gate_evidence[key]["status"] not in {"passed", "carried-forward", "receipt-passed"}
]
release_ready = total >= 100.0 and all(per_task[key] == weights[key] for key in weights) and not release_blockers
print(
    json.dumps(
        {
            "total": total,
            "per_task": per_task,
            "release_ready": release_ready,
            "release_blockers": release_blockers,
            "hypothesis_gate_passed": hypothesis_gate_passed,
            "gate_evidence": gate_evidence,
            "score_name": config["score_name"],
            "session": config["session"],
            "hypothesis_id": hypothesis_id,
            "focused_gate": focused_gate,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
)
PY
