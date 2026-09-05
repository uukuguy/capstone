#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import stat
import sys
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


EXCEPTION_PATH = Path("configs/runtime/pi-security-risk-exception-v1.json")
REMEDIATION_PATH = Path("configs/runtime/pi-security-remediation-v1.json")
MANAGED_RUNTIME_ROOT = Path(".grid-agent/runtime/pi")
REMEDIATION_SCHEMA = "pi-runtime-security-remediation/1.0"
REMEDIATION_AUDIT_SCOPE = [
    "managed-pi-runtime",
    "pi-capability-tools",
    "pi-grid-tools",
]
ZERO_AUDIT_COUNTS = {
    "info": 0,
    "low": 0,
    "moderate": 0,
    "high": 0,
    "critical": 0,
    "total": 0,
}
MAXIMUM_EXPIRY = date(2026, 9, 30)
PI_VERSION = "0.80.6"
RISK_COUNTS = {"high": 2, "moderate": 2}
VULNERABLE_VERSIONS = {
    "brace-expansion": "5.0.6",
    "protobufjs": "7.6.4",
    "undici": "8.5.0",
}
NESTED_PACKAGE_ROOT = "node_modules/@earendil-works/pi-coding-agent/node_modules"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--today", type=date.fromisoformat, default=date.today())
    args = parser.parse_args()
    try:
        state = verify(args.root.resolve(), args.today)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"runtime-risk-exception: rejected: {exc}", file=sys.stderr)
        return 1
    if state == "legacy":
        print("runtime-risk-exception: accepted 2 high, 2 moderate through 2026-09-30")
    else:
        print("runtime-risk-exception: accepted validated remediation")
    return 0


def verify(root: Path, today: date) -> str:
    runtime_lock = load_object(root / "configs/runtime/pi-runtime.lock.json")
    package = require_object(runtime_lock, "package")
    if package.get("version") == PI_VERSION:
        verify_legacy_exception(root, today)
        return "legacy"
    verify_remediation(root, today, runtime_lock)
    return "remediation"


def verify_legacy_exception(root: Path, today: date) -> None:
    exception = load_object(root / EXCEPTION_PATH)
    if exception.get("schema_version") != "pi-runtime-security-risk-exception/1.0":
        raise ValueError("unsupported risk exception schema")
    if not non_empty_string(exception.get("exception_id")):
        raise ValueError("exception_id must be non-empty")
    if not non_empty_string(exception.get("owner")):
        raise ValueError("owner must be non-empty")
    issued_on = date.fromisoformat(require_string(exception, "issued_on"))
    expires_on = date.fromisoformat(require_string(exception, "expires_on"))
    if issued_on > today:
        raise ValueError("risk exception is not yet effective")
    if today > expires_on:
        raise ValueError(f"risk exception expired on {expires_on.isoformat()}")
    if expires_on > MAXIMUM_EXPIRY:
        raise ValueError("risk exception expiry exceeds 2026-09-30")
    if exception.get("risk_counts") != RISK_COUNTS:
        raise ValueError("risk counts must remain exactly 2 high and 2 moderate")
    if exception.get("vulnerable_lock_versions") != VULNERABLE_VERSIONS:
        raise ValueError("declared vulnerability baseline changed")
    affected = require_object(exception, "affected_runtime")
    if affected != {
        "package": "@earendil-works/pi-coding-agent",
        "version": PI_VERSION,
    }:
        raise ValueError("affected Pi runtime does not match the validated pin")
    for field in ("attack_surface", "mitigations", "advisories"):
        value = exception.get(field)
        if not isinstance(value, list) or not value or not all(non_empty_string(item) for item in value):
            raise ValueError(f"{field} must be a non-empty string list")
    if not non_empty_string(exception.get("upgrade_trigger")):
        raise ValueError("upgrade_trigger must be non-empty")
    if exception.get("target_pi_upgrade") != ">=0.84.3":
        raise ValueError("target Pi security upgrade must remain >=0.84.3")

    runtime_lock = load_object(root / "configs/runtime/pi-runtime.lock.json")
    if require_object(runtime_lock, "package").get("version") != PI_VERSION:
        raise ValueError("Pi runtime lock does not match the accepted version")
    for package in ("pi-capability-tools", "pi-grid-tools"):
        package_root = root / "packages" / package
        manifest = load_object(package_root / "package.json")
        dependencies = require_object(manifest, "dependencies")
        if dependencies.get("@earendil-works/pi-coding-agent") != PI_VERSION:
            raise ValueError(f"{package} Pi dependency pin changed")
        lock = load_object(package_root / "package-lock.json")
        packages = require_object(lock, "packages")
        coding_agent = require_object(
            packages,
            "node_modules/@earendil-works/pi-coding-agent",
        )
        if coding_agent.get("version") != PI_VERSION:
            raise ValueError(f"{package} locked Pi version changed")
        for dependency, expected_version in VULNERABLE_VERSIONS.items():
            locked = require_object(
                packages,
                f"{NESTED_PACKAGE_ROOT}/{dependency}",
            )
            if locked.get("version") != expected_version:
                raise ValueError(
                    f"{package} vulnerability baseline changed for {dependency}"
                )
        verify_installed_graph(package_root, packages)


def verify_remediation(root: Path, today: date, runtime_lock: dict[str, Any]) -> None:
    record_path = root / REMEDIATION_PATH
    try:
        record = load_object(record_path)
    except FileNotFoundError as exc:
        raise ValueError("unvalidated Pi runtime: remediation record is missing") from exc
    if record.get("schema_version") != REMEDIATION_SCHEMA:
        raise ValueError("unsupported remediation schema")
    if not non_empty_string(record.get("remediation_id")):
        raise ValueError("remediation_id must be non-empty")
    exception = load_object(root / EXCEPTION_PATH)
    replaces = require_object(record, "replaces_exception")
    if replaces.get("exception_id") != exception.get("exception_id") or replaces.get("sha256") != sha256_file(root / EXCEPTION_PATH):
        raise ValueError("remediation does not bind the historical exception")

    runtime = require_object(record, "validated_runtime")
    if runtime.get("runtime_lock_sha256") != sha256_file(root / "configs/runtime/pi-runtime.lock.json"):
        raise ValueError("remediation runtime lock binding drifted")
    source = require_object(runtime_lock, "source")
    package = require_object(runtime_lock, "package")
    runtime_config = require_object(runtime_lock, "runtime")
    expected_runtime = {
        "package": package.get("name"),
        "version": package.get("version"),
        "source_repository": source.get("repository"),
        "source_commit": source.get("commit"),
        "npm_integrity": package.get("npm_integrity"),
        "pi_ai_version": runtime_config.get("pi_ai_version"),
        "pi_ai_npm_integrity": runtime_config.get("pi_ai_npm_integrity"),
    }
    if any(runtime.get(field) != value for field, value in expected_runtime.items()):
        raise ValueError("remediation runtime source or package identity drifted")
    verify_patch_binding(root, runtime_lock, runtime)

    package_locks = require_object(record, "package_locks")
    lock_graphs = require_object(record, "frozen_lock_graphs")
    bindings = remediation_lock_bindings(root)
    lock_digests: dict[str, str] = {}
    for identity, binding in bindings.items():
        lock_entry = require_object(package_locks, identity)
        if lock_entry != binding["lock"]:
            raise ValueError(f"{identity} remediation lock path changed")
        lock_digests[identity] = str(binding["lock"]["sha256"])
        graph_entry = require_object(lock_graphs, identity)
        if graph_entry != binding["graph"]:
            raise ValueError(f"{identity} normalized lock graph drifted")
        verify_remediated_installed_graph(
            binding["package_root"], binding["graph"]["packages"], identity
        )

    verify_audit(record, lock_digests, today)
    verify_focused_capture(record, source.get("commit"), runtime.get("patch_set_sha256"), today)


def remediation_roots(root: Path) -> dict[str, tuple[Path, str]]:
    return {
        "managed-pi-runtime": (root / MANAGED_RUNTIME_ROOT / "source", "source/package-lock.json"),
        "pi-capability-tools": (
            root / "packages/pi-capability-tools",
            "packages/pi-capability-tools/package-lock.json",
        ),
        "pi-grid-tools": (
            root / "packages/pi-grid-tools",
            "packages/pi-grid-tools/package-lock.json",
        ),
    }


def remediation_lock_bindings(root: Path) -> dict[str, dict[str, object]]:
    """Return deterministic record fields for the three audited frozen locks.

    This performs local reads only; the explicit OP-06 audit helper may call it
    when preparing a candidate record, but it does not contact a registry.
    """
    bindings: dict[str, dict[str, object]] = {}
    for identity, (package_root, record_path_value) in remediation_roots(root).items():
        lock_path = package_root / "package-lock.json"
        packages = require_object(load_object(lock_path), "packages")
        graph = normalized_lock_graph(packages, package_root)
        bindings[identity] = {
            "package_root": package_root,
            "lock": {"path": record_path_value, "sha256": sha256_file(lock_path)},
            "graph": {"sha256": sha256_json(graph), "packages": graph},
        }
    return bindings


def verify_patch_binding(root: Path, runtime_lock: dict[str, Any], runtime: dict[str, Any]) -> None:
    patches = runtime_lock.get("patches")
    if not isinstance(patches, list) or not patches:
        raise ValueError("runtime lock patches must be a non-empty list")
    normalized: list[dict[str, str]] = []
    for raw_patch in patches:
        if not isinstance(raw_patch, dict):
            raise ValueError("runtime lock patch is invalid")
        path = raw_patch.get("path")
        digest = raw_patch.get("sha256")
        if not non_empty_string(path) or not non_empty_string(digest):
            raise ValueError("runtime lock patch is invalid")
        patch_path = root / "configs/runtime" / path
        if sha256_file(patch_path) != digest:
            raise ValueError("runtime patch digest drifted")
        normalized.append({"path": path, "sha256": digest})
    if runtime.get("patches") != normalized or runtime.get("patch_set_sha256") != sha256_json(normalized):
        raise ValueError("remediation patch binding drifted")


def verify_audit(record: dict[str, Any], lock_digests: dict[str, str], today: date) -> None:
    audit = require_object(record, "fresh_audit")
    audited_on = date.fromisoformat(require_string(audit, "audited_on"))
    if audited_on > today:
        raise ValueError("remediation audit is not yet effective")
    if audit.get("tool") != "npm audit" or not non_empty_string(audit.get("tool_version")):
        raise ValueError("remediation audit tool is invalid")
    if audit.get("audit_format") != "npm-audit-v2":
        raise ValueError("remediation audit format is invalid")
    if audit.get("audit_scope") != REMEDIATION_AUDIT_SCOPE:
        raise ValueError("remediation audit scope is invalid")
    if audit.get("audited_lock_sha256") != lock_digests:
        raise ValueError("remediation audit lock binding drifted")
    if audit.get("severity_counts") != ZERO_AUDIT_COUNTS:
        raise ValueError("remediation audit counts must be complete and zero")
    if audit.get("vulnerabilities") != {}:
        raise ValueError("remediation audit vulnerabilities must be empty")
    if not sha256_hex(audit.get("result_sha256")):
        raise ValueError("remediation audit result digest is invalid")


def verify_focused_capture(
    record: dict[str, Any],
    source_commit: object,
    patch_set_sha256: object,
    today: date,
) -> None:
    capture = require_object(record, "focused_capture_validation")
    if date.fromisoformat(require_string(capture, "completed_on")) > today:
        raise ValueError("focused capture is not yet effective")
    if capture.get("source_revision") != source_commit:
        raise ValueError("focused capture source revision is not the selected runtime")
    result = require_object(capture, "result")
    if result.get("runtime_commit") != source_commit or result.get("patch_set_sha256") != patch_set_sha256:
        raise ValueError("focused capture runtime binding is invalid")
    suites = require_object(result, "suites")
    expected_suites = {"pi-capture-capability-tools", "pi-capture-grid-tools"}
    if set(suites) != expected_suites:
        raise ValueError("focused capture suite binding is invalid")
    for suite in expected_suites:
        outcome = require_object(suites, suite)
        if outcome.get("exit_code") != 0 or not positive_int(outcome.get("assertion_count")):
            raise ValueError("focused capture suite did not pass")
    if capture.get("result_sha256") != sha256_json(result):
        raise ValueError("focused capture result digest drifted")


def normalized_lock_graph(
    packages: dict[str, Any], package_root: Path
) -> list[dict[str, object]]:
    graph: list[dict[str, object]] = []
    for path, metadata in sorted(packages.items()):
        if not isinstance(path, str) or not path.startswith("node_modules/") or not isinstance(metadata, dict):
            continue
        if metadata.get("link") is True:
            resolved = metadata.get("resolved")
            if not non_empty_string(resolved):
                raise ValueError(f"invalid linked lock package {path}")
            target_manifest = load_object(package_root / resolved / "package.json")
            name = target_manifest.get("name")
            version = target_manifest.get("version")
            if not non_empty_string(name) or not non_empty_string(version):
                raise ValueError(f"invalid linked lock package target {path}")
            graph.append(
                {
                    "path": path,
                    "link": True,
                    "resolved": resolved,
                    "name": name,
                    "version": version,
                }
            )
            continue
        version = metadata.get("version")
        integrity = metadata.get("integrity")
        resolved = metadata.get("resolved")
        if not non_empty_string(version):
            raise ValueError(f"invalid frozen lock package {path}")
        entry: dict[str, object] = {
            "path": path,
            "name": package_name(path),
            "version": version,
            "optional": metadata.get("optional") is True,
        }
        if non_empty_string(integrity):
            entry["integrity"] = integrity
        elif is_registry_url(resolved):
            entry["resolved"] = resolved
        else:
            raise ValueError(f"invalid frozen lock package identity {path}")
        graph.append(entry)
    if not graph:
        raise ValueError("frozen lock graph contains no packages")
    return graph


def verify_remediated_installed_graph(
    package_root: Path,
    expected_graph: list[dict[str, object]],
    identity: str,
) -> None:
    installed_root = package_root / "node_modules"
    try:
        installed_status = installed_root.lstat()
    except FileNotFoundError as exc:
        raise ValueError(f"{identity} installed graph is unavailable") from exc
    if not stat.S_ISDIR(installed_status.st_mode) or stat.S_ISLNK(installed_status.st_mode):
        raise ValueError(f"{identity} installed graph root is unsafe")
    expected = {str(entry["path"]): entry for entry in expected_graph}
    for path, entry in expected.items():
        target = package_root / path
        if entry.get("link") is True:
            verify_workspace_link(target, entry, package_root, identity)
            continue
        manifest = target / "package.json"
        verify_ordinary_package_path(package_root, target, identity)
        if not manifest.exists():
            if entry.get("optional") is True:
                continue
            raise ValueError(f"{identity} installed graph is missing mandatory package {path}")
        installed = load_object(manifest)
        if installed.get("name") != entry.get("name") or installed.get("version") != entry.get("version"):
            raise ValueError(f"{identity} installed graph drift for {path}")
    for manifest_path in installed_root.rglob("package.json"):
        relative = manifest_path.parent.relative_to(package_root).as_posix()
        if not is_dependency_root(relative):
            continue
        if relative not in expected:
            raise ValueError(f"{identity} installed graph contains unlocked package {relative}")


def verify_workspace_link(target: Path, entry: dict[str, object], package_root: Path, identity: str) -> None:
    try:
        status = target.lstat()
    except FileNotFoundError as exc:
        raise ValueError(f"{identity} installed graph is missing workspace link {entry['path']}") from exc
    if not stat.S_ISLNK(status.st_mode):
        raise ValueError(f"{identity} workspace link is unsafe")
    resolved = entry.get("resolved")
    if not isinstance(resolved, str):
        raise ValueError(f"{identity} workspace link is invalid")
    expected_target = (package_root / resolved).resolve()
    if target.resolve() != expected_target:
        raise ValueError(f"{identity} workspace link escaped its locked target")
    manifest = load_object(target / "package.json")
    if manifest.get("name") != entry.get("name") or manifest.get("version") != entry.get("version"):
        raise ValueError(f"{identity} workspace link package drifted")


def verify_ordinary_package_path(package_root: Path, target: Path, identity: str) -> None:
    relative = target.relative_to(package_root)
    current = package_root
    for part in relative.parts:
        current = current / part
        try:
            status = current.lstat()
        except FileNotFoundError:
            return
        if stat.S_ISLNK(status.st_mode) or not stat.S_ISDIR(status.st_mode):
            raise ValueError(f"{identity} installed graph package path is unsafe")


def is_dependency_root(relative: str) -> bool:
    tail = relative.rsplit("node_modules/", 1)[-1].split("/")
    return len(tail) == (2 if tail[0].startswith("@") else 1)


def is_registry_url(value: object) -> bool:
    if not non_empty_string(value):
        return False
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc)


def package_name(path: str) -> str:
    return path.rsplit("node_modules/", 1)[-1]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_json(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def sha256_hex(value: object) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def verify_installed_graph(
    package_root: Path,
    locked_packages: dict[str, Any],
) -> None:
    installed_root = package_root / "node_modules"
    try:
        installed_status = installed_root.lstat()
    except FileNotFoundError as exc:
        raise ValueError(
            f"{package_root.name} installed graph is unavailable; run make setup-tools"
        ) from exc
    if not stat.S_ISDIR(installed_status.st_mode) or stat.S_ISLNK(installed_status.st_mode):
        raise ValueError(f"{package_root.name} installed graph root is unsafe")

    checked = 0
    for manifest_path in installed_root.rglob("package.json"):
        package_dir = manifest_path.parent
        relative = package_dir.relative_to(package_root).as_posix()
        tail = relative.rsplit("node_modules/", 1)[-1].split("/")
        if len(tail) != (2 if tail[0].startswith("@") else 1):
            continue
        locked = locked_packages.get(relative)
        if not isinstance(locked, dict):
            raise ValueError(
                f"{package_root.name} installed graph contains unlocked package {relative}"
            )
        installed = load_object(manifest_path)
        if installed.get("version") != locked.get("version"):
            raise ValueError(
                f"{package_root.name} installed graph drift for {relative}: "
                f"{installed.get('version')} != {locked.get('version')}"
            )
        checked += 1
    if checked == 0:
        raise ValueError(f"{package_root.name} installed graph contains no locked packages")

    local_key = "node_modules/@capability-agent/pi-tools"
    local_lock = locked_packages.get(local_key)
    if isinstance(local_lock, dict) and local_lock.get("link") is True:
        local_path = package_root / local_key
        try:
            local_status = local_path.lstat()
        except FileNotFoundError as exc:
            raise ValueError("pi-grid-tools installed graph is missing the local owning package") from exc
        if not stat.S_ISLNK(local_status.st_mode):
            raise ValueError("pi-grid-tools local owning package must be a workspace link")
        expected = (package_root / str(local_lock.get("resolved"))).resolve()
        if local_path.resolve() != expected:
            raise ValueError("pi-grid-tools local owning package link escaped its locked target")
        local_manifest = load_object(local_path / "package.json")
        if local_manifest.get("version") != "0.1.0":
            raise ValueError("pi-grid-tools local owning package version drifted")


def load_object(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return document


def require_object(document: dict[str, Any], field: str) -> dict[str, Any]:
    value = document.get(field)
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object")
    return value


def require_string(document: dict[str, Any], field: str) -> str:
    value = document.get(field)
    if not non_empty_string(value):
        raise ValueError(f"{field} must be a non-empty string")
    return str(value)


def non_empty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def positive_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


if __name__ == "__main__":
    raise SystemExit(main())
