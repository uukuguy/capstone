#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
STATE_DIR=${CLIMB_STATE_DIR:-"$ROOT/docs/status/climb"}
if [ "$#" -ge 1 ]; then
  RUN_DIR=$1
  mkdir -p "$RUN_DIR"
else
  ARTIFACT_DIR=${CLIMB_ARTIFACT_DIR:-"$ROOT/runs/climb"}
  RUN_DIR=$(mktemp -d "$ARTIFACT_DIR/eval-XXXXXX")
fi

python3 - "$ROOT" "$STATE_DIR" "$RUN_DIR" <<'PY'
from __future__ import annotations

import json
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


def resolve_path(raw: str) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else root / path


def run_gate(key: str, gate: dict[str, object]) -> tuple[float, dict[str, object]]:
    required_paths = [resolve_path(str(item)) for item in gate.get("required_paths", [])]
    missing = [str(path) for path in required_paths if not path.exists()]
    if missing:
        return 0.0, {"status": "missing", "missing_paths": missing}

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


per_task: dict[str, float] = {}
gate_evidence: dict[str, dict[str, object]] = {}
for key in weights:
    gate = gates.get(key, {})
    if not owns_hypothesis(gate):
        required_paths = [resolve_path(str(item)) for item in gate.get("required_paths", [])]
        missing = [str(path) for path in required_paths if not path.exists()]
        if missing:
            per_task[key] = 0.0
            gate_evidence[key] = {"status": "missing", "missing_paths": missing}
        else:
            per_task[key] = 0.0
            gate_evidence[key] = {"status": "not-owned-by-hypothesis", "hypothesis_id": gate.get("hypothesis_id"), "hypothesis_ids": gate.get("hypothesis_ids", [])}
        continue
    per_task[key], gate_evidence[key] = run_gate(key, gate)

owned_keys = [
    key
    for key, gate in gates.items()
    if key in weights and (gate.get("hypothesis_id") == hypothesis_id or hypothesis_id in gate.get("hypothesis_ids", []))
]
hypothesis_gate_passed = bool(owned_keys) and all(
    gate_evidence[key]["status"] == "passed" for key in owned_keys
)
total = sum(per_task.values())
release_ready = total >= 100.0 and all(per_task[key] == weights[key] for key in weights)
print(
    json.dumps(
        {
            "total": total,
            "per_task": per_task,
            "release_ready": release_ready,
            "hypothesis_gate_passed": hypothesis_gate_passed,
            "gate_evidence": gate_evidence,
            "score_name": config["score_name"],
            "session": config["session"],
            "hypothesis_id": hypothesis_id,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
)
PY
