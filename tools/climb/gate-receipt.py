#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from climb_evidence import (
    JsonObject,
    artifact_dir as resolve_artifact_dir,
    load_json_object,
    receipt_output_path_for,
    receipt_path_for,
    source_revision,
    stable_path,
    state_dir as resolve_state_dir,
)

ROOT = Path(__file__).resolve().parents[2]


def _state_dir() -> Path:
    return resolve_state_dir(ROOT)


def _resolve_path(raw: str) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else ROOT / path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("gate_key")
    args = parser.parse_args()

    state_dir = _state_dir()
    config = load_json_object(state_dir / "config.yaml")
    gates = config.get("score_gates", {})
    if not isinstance(gates, dict) or args.gate_key not in gates:
        raise SystemExit(f"unknown score gate: {args.gate_key}")
    gate = gates[args.gate_key]
    if not isinstance(gate, dict):
        raise SystemExit(f"score gate must be an object: {args.gate_key}")
    command = gate.get("command")
    if not isinstance(command, list):
        raise SystemExit(f"score gate {args.gate_key} command must be a list")

    artifact_dir = resolve_artifact_dir(config, ROOT)
    revision = source_revision(config, ROOT)
    receipt_path = receipt_path_for(config, args.gate_key, revision, root=ROOT)
    output_path = receipt_output_path_for(config, args.gate_key, revision, root=ROOT)
    if receipt_path.exists() or output_path.exists():
        raise SystemExit(f"receipt already exists for {args.gate_key} at release source revision {revision}")
    receipt_dir = receipt_path.parent
    receipt_dir.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        [str(part) for part in command],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    output_path.write_text(
        "\n".join(
            [
                f"$ {' '.join(str(part) for part in command)}",
                f"returncode={completed.returncode}",
                "",
                "[stdout]",
                completed.stdout,
                "[stderr]",
                completed.stderr,
            ]
        ),
        encoding="utf-8",
    )
    receipt = {
        "artifact_path": stable_path(receipt_path, root=ROOT, state=state_dir, artifact=artifact_dir),
        "command": [str(part) for part in command],
        "created_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "gate_key": args.gate_key,
        "output_artifact_path": stable_path(output_path, root=ROOT, state=state_dir, artifact=artifact_dir),
        "release_source_revision": revision,
        "returncode": completed.returncode,
        "status": "passed" if completed.returncode == 0 else "failed",
    }
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(receipt_path)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
