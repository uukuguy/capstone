#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from climb_evidence import (
    JsonObject,
    canonical_json_bytes,
    artifact_dir as resolve_artifact_dir,
    load_attestation_key,
    load_json_object,
    release_source_tree_sha256,
    require_clean_release_source,
    receipt_output_path_for,
    receipt_path_for,
    secure_artifact_makedirs,
    sha256_bytes,
    sign_receipt,
    source_revision,
    stable_path,
    state_dir as resolve_state_dir,
)

DEFAULT_ROOT = Path(__file__).resolve().parents[2]


def _state_dir(root: Path) -> Path:
    return resolve_state_dir(root)


def _resolve_path(raw: str, root: Path) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else root / path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("gate_key")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args()
    root = args.root.resolve()

    state_dir = _state_dir(root)
    config = load_json_object(state_dir / "config.yaml")
    score_gates = config.get("score_gates", {})
    receipt_gates = config.get("receipt_gates", {})
    if not isinstance(score_gates, dict) or not isinstance(receipt_gates, dict):
        raise SystemExit("score_gates and receipt_gates must be objects")
    gates = {**score_gates, **receipt_gates}
    if args.gate_key not in gates:
        raise SystemExit(f"unknown score gate: {args.gate_key}")
    gate = gates[args.gate_key]
    if not isinstance(gate, dict):
        raise SystemExit(f"score gate must be an object: {args.gate_key}")
    command = gate.get("command")
    if not isinstance(command, list):
        raise SystemExit(f"score gate {args.gate_key} command must be a list")

    artifact_dir = resolve_artifact_dir(config, root)
    require_clean_release_source(config, root)
    revision = source_revision(config, root)
    source_tree_sha256 = release_source_tree_sha256(config, revision, root)
    receipt_path = receipt_path_for(config, args.gate_key, revision, root=root)
    output_path = receipt_output_path_for(config, args.gate_key, revision, root=root)
    if receipt_path.exists() or output_path.exists():
        raise SystemExit(f"receipt already exists for {args.gate_key} at release source revision {revision}")
    receipt_dir = receipt_path.parent
    secure_artifact_makedirs(receipt_dir, artifact=artifact_dir)
    required_paths = gate.get("required_paths", [])
    if not isinstance(required_paths, list):
        raise SystemExit(f"score gate {args.gate_key} required_paths must be a list")
    missing = [
        path
        for path in (_resolve_path(str(raw), root) for raw in required_paths)
        if not path.exists()
    ]
    if missing:
        raise SystemExit(
            "gate required paths are missing: "
            + ", ".join(str(path) for path in missing)
        )
    completed = subprocess.run(
        [str(part) for part in command],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    output_bytes = (
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
        )
    ).encode("utf-8")
    _write_exclusive(output_path, output_bytes)
    key = load_attestation_key(root=root, create=True)
    receipt = sign_receipt(
        {
            "artifact_path": stable_path(receipt_path, root=root, state=state_dir, artifact=artifact_dir),
            "command": [str(part) for part in command],
            "created_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
            "gate_key": args.gate_key,
            "output_artifact_path": stable_path(output_path, root=root, state=state_dir, artifact=artifact_dir),
            "output_sha256": sha256_bytes(output_bytes),
            "release_source_revision": revision,
            "release_source_tree_sha256": source_tree_sha256,
            "returncode": completed.returncode,
            "status": "passed" if completed.returncode == 0 else "failed",
        },
        key,
    )
    _write_exclusive(
        receipt_path,
        json.dumps(receipt, ensure_ascii=False, sort_keys=True).encode("utf-8") + b"\n",
    )
    print(receipt_path)
    return completed.returncode


def _write_exclusive(path: Path, payload: bytes) -> None:
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
        0o600,
    )
    try:
        if os.write(descriptor, payload) != len(payload):
            raise OSError(f"short write for {path}")
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


if __name__ == "__main__":
    raise SystemExit(main())
