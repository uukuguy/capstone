#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _state_dir() -> Path:
    raw = os.environ.get("CLIMB_STATE_DIR")
    if raw:
        path = Path(raw)
        return path if path.is_absolute() else ROOT / path
    return ROOT / "docs/status/climb"


def _artifact_dir(config: dict[str, object]) -> Path:
    raw = os.environ.get("CLIMB_ARTIFACT_DIR") or str(config.get("artifact_dir", "runs/climb"))
    path = Path(raw)
    return path if path.is_absolute() else ROOT / path


def _stable_path(path: Path, *, state_dir: Path, artifact_dir: Path) -> str:
    resolved = path.resolve()
    for base in (ROOT.resolve(), artifact_dir.resolve(), state_dir.resolve()):
        try:
            return resolved.relative_to(base).as_posix()
        except ValueError:
            continue
    return path.name


def _source_commit() -> str:
    override = os.environ.get("CLIMB_SOURCE_COMMIT")
    if override:
        return override
    completed = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise SystemExit(completed.stderr.strip() or "could not resolve source commit")
    return completed.stdout.strip()


def _resolve_path(raw: str) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else ROOT / path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("gate_key")
    args = parser.parse_args()

    state_dir = _state_dir()
    config = json.loads((state_dir / "config.yaml").read_text(encoding="utf-8"))
    gates = config.get("score_gates", {})
    if not isinstance(gates, dict) or args.gate_key not in gates:
        raise SystemExit(f"unknown score gate: {args.gate_key}")
    gate = gates[args.gate_key]
    if not isinstance(gate, dict):
        raise SystemExit(f"score gate must be an object: {args.gate_key}")
    command = gate.get("command")
    if not isinstance(command, list):
        raise SystemExit(f"score gate {args.gate_key} command must be a list")

    artifact_dir = _artifact_dir(config)
    receipt_dir = artifact_dir / "gate-receipts"
    receipt_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = receipt_dir / f"{args.gate_key}.json"
    output_path = receipt_dir / f"{args.gate_key}.output.txt"
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
        "artifact_path": _stable_path(receipt_path, state_dir=state_dir, artifact_dir=artifact_dir),
        "command": [str(part) for part in command],
        "created_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "gate_key": args.gate_key,
        "output_artifact_path": _stable_path(output_path, state_dir=state_dir, artifact_dir=artifact_dir),
        "returncode": completed.returncode,
        "source_commit": _source_commit(),
        "status": "passed" if completed.returncode == 0 else "failed",
    }
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(receipt_path)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
