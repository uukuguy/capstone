from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from climb_evidence import (
    CANONICAL_SCORE_WEIGHTS,
    CLOSURE_GATE_ORDER,
    JsonObject,
    artifact_dir,
    as_object,
    canonical_json_bytes,
    load_json_object,
    policy_sha256,
    release_source_tree_sha256,
    require_clean_release_source,
    secure_artifact_makedirs,
    sha256_bytes,
    source_revision,
    stable_path,
    validate_release_policy,
)


def run_gate_command(
    command: list[str], root: Path
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def execute_release_closure(root: Path, run_dir: Path) -> JsonObject:
    root = root.resolve()
    config_path = root / "docs/status/climb/config.yaml"
    config = load_json_object(config_path)
    validate_release_policy(config)
    require_clean_release_source(config, root)
    release_revision = source_revision(config, root)
    tree_sha256 = release_source_tree_sha256(config, release_revision, root)
    command_policy_sha256 = policy_sha256(config)
    artifact_root = artifact_dir(config, root).absolute()
    run_absolute = run_dir.absolute()
    try:
        run_absolute.relative_to(artifact_root)
    except ValueError as exc:
        raise ValueError("release closure run directory escapes artifact_dir") from exc
    secure_artifact_makedirs(run_absolute, artifact=artifact_root)
    result_dir = run_absolute / "release-closure"
    secure_artifact_makedirs(result_dir, artifact=artifact_root)
    closure_path = run_absolute / "release-closure.json"
    if closure_path.exists():
        raise ValueError("release closure result already exists")

    score_gates = as_object(config.get("score_gates"), "score_gates")
    receipt_gates = as_object(config.get("receipt_gates"), "receipt_gates")
    gate_results: list[JsonObject] = []
    for index, key in enumerate(CLOSURE_GATE_ORDER, start=1):
        _assert_release_binding(
            root,
            config_path,
            release_revision,
            tree_sha256,
            command_policy_sha256,
        )
        section = receipt_gates if key in {"doctor", "test", "test-e2e"} else score_gates
        gate = as_object(section.get(key), f"gate {key}")
        command = _command(gate, key)
        raw_required_paths = gate.get("required_paths", [])
        if not isinstance(raw_required_paths, list):
            raise ValueError(f"release gate required_paths is invalid: {key}")
        missing = [
            str(raw_path)
            for raw_path in raw_required_paths
            if not _root_path(root, str(raw_path)).exists()
        ]
        if missing:
            raise ValueError(f"release gate required paths are missing for {key}: {missing}")
        completed = run_gate_command(command, root)
        stdout_bytes = completed.stdout.encode("utf-8")
        stderr_bytes = completed.stderr.encode("utf-8")
        output_document = {
            "command": command,
            "gate_key": key,
            "returncode": completed.returncode,
            "stderr": completed.stderr,
            "stdout": completed.stdout,
        }
        output_bytes = canonical_json_bytes(output_document) + b"\n"
        output_path = result_dir / f"{index:02d}-{key}.output.json"
        _write_readonly_exclusive(output_path, output_bytes)
        gate_results.append(
            {
                "command": command,
                "gate_key": key,
                "output_artifact_path": stable_path(
                    output_path,
                    root=root,
                    state=config_path.parent,
                    artifact=artifact_root,
                ),
                "output_sha256": sha256_bytes(output_bytes),
                "returncode": completed.returncode,
                "status": "passed" if completed.returncode == 0 else "failed",
                "stderr_sha256": sha256_bytes(stderr_bytes),
                "stdout_sha256": sha256_bytes(stdout_bytes),
            }
        )
        _assert_release_binding(
            root,
            config_path,
            release_revision,
            tree_sha256,
            command_policy_sha256,
        )

    closure: JsonObject = {
        "all_passed": all(result["returncode"] == 0 for result in gate_results),
        "gate_order": list(CLOSURE_GATE_ORDER),
        "gate_results": gate_results,
        "mode": "rerun-all-gates-v1",
        "policy_sha256": command_policy_sha256,
        "release_source_revision": release_revision,
        "release_source_tree_sha256": tree_sha256,
        "schema_version": "workstream-b-release-closure/1.0",
        "trust_scope": "local live execution; same-user HMAC is integrity-only",
    }
    closure_digest = sha256_bytes(canonical_json_bytes(closure))
    closure["closure_digest"] = closure_digest
    _write_readonly_exclusive(
        closure_path,
        json.dumps(closure, ensure_ascii=False, sort_keys=True).encode("utf-8") + b"\n",
    )
    return _score_from_closure(
        config,
        closure_path,
        closure_digest,
        gate_results,
        release_revision,
        tree_sha256,
        command_policy_sha256,
        root,
        artifact_root,
    )


def _assert_release_binding(
    root: Path,
    config_path: Path,
    revision: str,
    tree_sha256: str,
    expected_policy_sha256: str,
) -> None:
    current = load_json_object(config_path)
    validate_release_policy(current)
    require_clean_release_source(current, root)
    if policy_sha256(current) != expected_policy_sha256:
        raise ValueError("release policy digest changed during closure")
    if source_revision(current, root) != revision:
        raise ValueError("release source revision changed during closure")
    if release_source_tree_sha256(current, revision, root) != tree_sha256:
        raise ValueError("release source tree changed during closure")


def _score_from_closure(
    config: JsonObject,
    closure_path: Path,
    closure_digest: str,
    gate_results: list[JsonObject],
    revision: str,
    tree_sha256: str,
    command_policy_sha256: str,
    root: Path,
    artifact_root: Path,
) -> JsonObject:
    results = {str(result["gate_key"]): result for result in gate_results}
    closure_artifact_path = stable_path(
        closure_path,
        root=root,
        state=root / "docs/status/climb",
        artifact=artifact_root,
    )
    per_task: dict[str, float] = {}
    evidence: dict[str, JsonObject] = {}
    for key, weight in CANONICAL_SCORE_WEIGHTS.items():
        result = results[key]
        passed = result["returncode"] == 0
        per_task[key] = weight if passed else 0.0
        evidence[key] = {
            **result,
            "artifact_path": closure_artifact_path,
            "closure_digest": closure_digest,
            "policy_sha256": command_policy_sha256,
            "release_source_revision": revision,
            "release_source_tree_sha256": tree_sha256,
            "status": "closure-passed" if passed else "closure-failed",
        }
    product = evidence["product_compatibility"]
    product["prerequisite_receipts"] = {
        key: {
            **results[key],
            "artifact_path": closure_artifact_path,
            "closure_digest": closure_digest,
            "policy_sha256": command_policy_sha256,
            "release_source_revision": revision,
            "release_source_tree_sha256": tree_sha256,
            "status": (
                "closure-passed" if results[key]["returncode"] == 0 else "closure-failed"
            ),
        }
        for key in ("doctor", "test", "test-e2e")
    }
    prerequisites_passed = all(results[key]["returncode"] == 0 for key in ("doctor", "test", "test-e2e"))
    if not prerequisites_passed:
        per_task["product_compatibility"] = 0.0
        product["status"] = "closure-prerequisite-failed"
    total = sum(per_task.values())
    blockers = [
        f"{key}: {evidence[key]['status']}"
        for key, weight in CANONICAL_SCORE_WEIGHTS.items()
        if per_task[key] != weight or evidence[key]["status"] != "closure-passed"
    ]
    return {
        "closure_artifact_path": closure_artifact_path,
        "closure_digest": closure_digest,
        "focused_gate": "product_compatibility",
        "gate_evidence": evidence,
        "hypothesis_gate_passed": product["status"] == "closure-passed",
        "hypothesis_id": "B-H005",
        "per_task": per_task,
        "policy_sha256": command_policy_sha256,
        "release_blockers": blockers,
        "release_ready": total == 100.0 and not blockers,
        "release_source_revision": revision,
        "release_source_tree_sha256": tree_sha256,
        "score_name": config["score_name"],
        "session": config["session"],
        "total": total,
        "trust_scope": "live local closure; no claim of same-user unforgeability",
    }


def _command(gate: JsonObject, key: str) -> list[str]:
    raw = gate.get("command")
    if not isinstance(raw, list) or not all(isinstance(part, str) for part in raw):
        raise ValueError(f"release gate command is invalid: {key}")
    return list(raw)


def _root_path(root: Path, raw: str) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else root / path


def _write_readonly_exclusive(path: Path, payload: bytes) -> None:
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
        0o600,
    )
    try:
        if os.write(descriptor, payload) != len(payload):
            raise OSError(f"short write for {path}")
        os.fsync(descriptor)
        os.fchmod(descriptor, 0o400)
    finally:
        os.close(descriptor)
