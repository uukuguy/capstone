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

import csv
import json
import subprocess
import sys
from pathlib import Path


root = Path(sys.argv[1])
state_dir = Path(sys.argv[2])
run_dir = Path(sys.argv[3])
sys.path.insert(0, str(root / "tools" / "climb"))

from climb_evidence import (  # noqa: E402
    JsonObject,
    artifact_dir as configured_artifact_dir,
    as_object,
    contained_artifact_path,
    load_json_object,
    receipt_path_for,
    source_revision,
    stable_path as stable_artifact_path,
)


def object_or_empty(value: object) -> JsonObject:
    return value if isinstance(value, dict) else {}


def list_or_empty(value: object) -> list[object]:
    return value if isinstance(value, list) else []


config = load_json_object(state_dir / "config.yaml")
manifest = load_json_object(run_dir / "manifest.json")
hypothesis_id = str(manifest["hypothesis_id"])
session_id = str(config["session"])
weights = {key: float(value) for key, value in as_object(config["score_weights"], "score_weights").items()}
gates = as_object(config.get("score_gates"), "score_gates")
hypotheses_document = load_json_object(state_dir / "hypotheses.yaml")
hypotheses = list_or_empty(hypotheses_document.get("hypotheses"))
hypothesis = next(
    (as_object(item, "hypothesis") for item in hypotheses if isinstance(item, dict) and item.get("id") == hypothesis_id),
    None,
)
if hypothesis is None:
    raise SystemExit(f"unknown hypothesis: {hypothesis_id}")
focused_gate = str(hypothesis.get("focused_gate") or "")
if focused_gate not in weights:
    raise SystemExit(f"unknown focused gate for {hypothesis_id}: {focused_gate}")
artifact_base = configured_artifact_dir(config, root)
release_revision = source_revision(config, root)


def stable_path(path: Path) -> str:
    return stable_artifact_path(path, root=root, state=state_dir, artifact=artifact_base)


def resolve_path(raw: str) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else root / path


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


def exact_command(gate: JsonObject, key: str) -> list[str]:
    raw = gate.get("command")
    if not isinstance(raw, list):
        raise SystemExit(f"score gate {key} command must be a list")
    return [str(part) for part in raw]


def run_gate(key: str, gate: JsonObject) -> tuple[float, JsonObject]:
    required_paths = [resolve_path(str(item)) for item in list_or_empty(gate.get("required_paths"))]
    missing = [path for path in required_paths if not path.exists()]
    if missing:
        return 0.0, {"status": "missing", "missing_paths": [stable_path(path) for path in missing]}

    command = exact_command(gate, key)
    completed = subprocess.run(
        command,
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    evidence: JsonObject = {
        "artifact_path": stable_path(output_path(key, completed)),
        "status": "passed" if completed.returncode == 0 else "failed",
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }
    return (weights[key] if completed.returncode == 0 else 0.0), evidence


def allowed_hypotheses(gate: JsonObject) -> set[str]:
    allowed: set[str] = set()
    raw_single = gate.get("hypothesis_id")
    if raw_single:
        allowed.add(str(raw_single))
    for raw in list_or_empty(gate.get("hypothesis_ids")):
        allowed.add(str(raw))
    return allowed


def owns_hypothesis(gate: JsonObject) -> bool:
    return hypothesis_id in allowed_hypotheses(gate)


def run_rows() -> dict[str, dict[str, str]]:
    runs_path = state_dir / "runs.csv"
    if not runs_path.is_file():
        return {}
    with runs_path.open(newline="", encoding="utf-8") as handle:
        return {row["run_id"]: row for row in csv.DictReader(handle)}


def float_equals(raw: object, expected: float) -> bool:
    try:
        return float(str(raw)) == expected
    except (TypeError, ValueError):
        return False


def invalid(status: str, **extra: object) -> tuple[float, JsonObject]:
    evidence: JsonObject = {"status": status, **extra}
    return 0.0, evidence


def matching_direct_event(event: JsonObject, key: str) -> bool:
    event_evidence = object_or_empty(object_or_empty(event.get("gate_evidence")).get(key))
    return event.get("status") == "confirmed" and event_evidence.get("status") == "passed"


def validate_carry_forward_event(event: JsonObject, row: dict[str, str], key: str, gate: JsonObject) -> tuple[float, JsonObject]:
    source_run_id = str(event.get("run_id") or "")
    source_hypothesis_id = str(event.get("hypothesis_id") or "")
    expected_weight = weights[key]
    expected_command = exact_command(gate, key)
    source_evidence = object_or_empty(object_or_empty(event.get("gate_evidence")).get(key))
    event_per_task = object_or_empty(event.get("per_task"))

    if source_hypothesis_id not in allowed_hypotheses(gate):
        return invalid("invalid-carry-forward-hypothesis", source_hypothesis_id=source_hypothesis_id)
    if row.get("session") != session_id:
        return invalid("invalid-carry-forward-session", source_run_id=source_run_id, session=row.get("session", ""))
    if row.get("hypothesis_id") != source_hypothesis_id:
        return invalid("invalid-carry-forward-row-hypothesis", source_run_id=source_run_id)
    if not float_equals(event.get("local_score"), expected_weight):
        return invalid("invalid-carry-forward-event-score", source_run_id=source_run_id)
    if not float_equals(event_per_task.get(key), expected_weight):
        return invalid("invalid-carry-forward-per-task", source_run_id=source_run_id)
    if not float_equals(row.get(f"local_{key}"), expected_weight):
        return invalid("invalid-carry-forward-row-score", source_run_id=source_run_id)
    if not float_equals(row.get("local_score"), expected_weight):
        return invalid("invalid-carry-forward-row-total", source_run_id=source_run_id)
    if [str(part) for part in list_or_empty(source_evidence.get("command"))] != expected_command:
        return invalid("invalid-carry-forward-command", source_run_id=source_run_id)
    if source_evidence.get("status") != "passed":
        return invalid("invalid-carry-forward-status", source_run_id=source_run_id)
    if int(source_evidence.get("returncode", 1)) != 0:
        return invalid("invalid-carry-forward-returncode", source_run_id=source_run_id)

    try:
        manifest_file = contained_artifact_path(row.get("manifest_path"), root=root, artifact=artifact_base)
    except ValueError as exc:
        return invalid("invalid-carry-forward-artifact-path", source_run_id=source_run_id, reason=str(exc))
    if not manifest_file.is_file():
        return invalid("missing-carry-forward-manifest", source_run_id=source_run_id, artifact_path=stable_path(manifest_file))

    source_manifest = load_json_object(manifest_file)
    if source_manifest.get("session") != session_id:
        return invalid("invalid-carry-forward-manifest-session", source_run_id=source_run_id)
    if source_manifest.get("hypothesis_id") != source_hypothesis_id:
        return invalid("invalid-carry-forward-manifest-hypothesis", source_run_id=source_run_id)

    raw_eval_path: object = source_manifest.get("local_eval_artifact_path") or f"{source_run_id}/local-eval.json"
    try:
        local_eval_file = contained_artifact_path(raw_eval_path, root=root, artifact=artifact_base)
    except ValueError as exc:
        return invalid("invalid-carry-forward-artifact-path", source_run_id=source_run_id, reason=str(exc))
    if not local_eval_file.is_file():
        return invalid("missing-carry-forward-local-eval", source_run_id=source_run_id, artifact_path=stable_path(local_eval_file))

    source_eval = load_json_object(local_eval_file)
    local_evidence = object_or_empty(object_or_empty(source_eval.get("gate_evidence")).get(key))
    local_per_task = object_or_empty(source_eval.get("per_task"))
    if source_eval.get("session") != session_id:
        return invalid("invalid-carry-forward-local-eval-session", source_run_id=source_run_id)
    if source_eval.get("hypothesis_id") != source_hypothesis_id:
        return invalid("invalid-carry-forward-local-eval-hypothesis", source_run_id=source_run_id)
    if source_eval.get("focused_gate") != key:
        return invalid("invalid-carry-forward-local-eval-focused-gate", source_run_id=source_run_id)
    if not float_equals(source_eval.get("total"), expected_weight):
        return invalid("invalid-carry-forward-local-eval-total", source_run_id=source_run_id)
    if not float_equals(local_per_task.get(key), expected_weight):
        return invalid("invalid-carry-forward-local-eval-per-task", source_run_id=source_run_id)
    if local_evidence != source_evidence:
        return invalid("invalid-carry-forward-local-eval-evidence", source_run_id=source_run_id)

    return expected_weight, {
        "artifact_path": stable_path(local_eval_file),
        "command": expected_command,
        "returncode": 0,
        "source_hypothesis_id": source_hypothesis_id,
        "source_run_id": source_run_id,
        "status": "carried-forward",
    }


def carry_forward(key: str, gate: JsonObject) -> tuple[float, JsonObject] | None:
    rows = run_rows()
    events = list_or_empty(load_json_object(state_dir / "hypotheses.yaml").get("events"))
    for raw_event in reversed(events):
        if not isinstance(raw_event, dict):
            continue
        event = as_object(raw_event, "event")
        if not matching_direct_event(event, key):
            continue
        source_run_id = str(event.get("run_id") or "")
        row = rows.get(source_run_id)
        if row is None:
            return invalid("missing-carry-forward-run-row", source_run_id=source_run_id)
        return validate_carry_forward_event(event, row, key, gate)
    return None


def any_stale_receipt_for(key: str) -> bool:
    receipt_root = artifact_base / "gate-receipts"
    if not receipt_root.is_dir():
        return False
    for candidate in receipt_root.glob(f"*/{key}.json"):
        try:
            receipt = load_json_object(candidate)
        except Exception:
            continue
        if receipt.get("release_source_revision") != release_revision:
            return True
    return False


def validate_receipt(key: str, gate: JsonObject) -> tuple[float, JsonObject]:
    receipt_path = receipt_path_for(config, key, release_revision, root=root)
    command = exact_command(gate, key)
    if not receipt_path.is_file():
        return 0.0, {
            "artifact_path": stable_path(receipt_path),
            "release_source_revision": release_revision,
            "status": "stale-receipt" if any_stale_receipt_for(key) else "missing-receipt",
        }
    receipt = load_json_object(receipt_path)
    evidence: JsonObject = {
        "artifact_path": stable_path(receipt_path),
        "command": [str(part) for part in list_or_empty(receipt.get("command"))],
        "output_artifact_path": str(receipt.get("output_artifact_path") or ""),
        "release_source_revision": str(receipt.get("release_source_revision") or ""),
        "returncode": receipt.get("returncode"),
    }
    if receipt.get("gate_key") != key:
        return 0.0, {**evidence, "status": "receipt-gate-mismatch"}
    if [str(part) for part in list_or_empty(receipt.get("command"))] != command:
        return 0.0, {**evidence, "status": "receipt-command-mismatch"}
    if receipt.get("release_source_revision") != release_revision:
        return 0.0, {**evidence, "status": "stale-receipt"}
    if int(receipt.get("returncode", 1)) != 0 or receipt.get("status") != "passed":
        return 0.0, {**evidence, "status": "failed-receipt"}
    return weights[key], {**evidence, "status": "receipt-passed"}


per_task: dict[str, float] = {}
gate_evidence: dict[str, JsonObject] = {}
for key in weights:
    gate = as_object(gates.get(key), f"score_gates.{key}")
    if key != focused_gate and gate.get("receipt_required"):
        per_task[key], gate_evidence[key] = validate_receipt(key, gate)
        continue
    if key != focused_gate:
        carried = carry_forward(key, gate)
        if carried is not None:
            per_task[key], gate_evidence[key] = carried
            continue
        required_paths = [resolve_path(str(item)) for item in list_or_empty(gate.get("required_paths"))]
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
valid_statuses = {"passed", "carried-forward", "receipt-passed"}
release_blockers = [
    f"{key}: {gate_evidence[key]['status']}"
    for key in weights
    if per_task[key] != weights[key] or gate_evidence[key]["status"] not in valid_statuses
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
            "release_source_revision": release_revision,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
)
PY
