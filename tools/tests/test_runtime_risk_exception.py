from __future__ import annotations

import json
import hashlib
import subprocess
import sys
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CHECKER = ROOT / "tools/check_runtime_risk_exception.py"


def test_runtime_risk_exception_accepts_the_exact_bounded_baseline(tmp_path: Path) -> None:
    write_fixture(tmp_path)

    result = run_checker(tmp_path, "2026-08-28")

    assert result.returncode == 0, result.stderr
    assert result.stdout == "runtime-risk-exception: accepted 2 high, 2 moderate through 2026-09-30\n"


def test_runtime_risk_exception_rejects_expiry_and_a_worsened_lock(tmp_path: Path) -> None:
    write_fixture(tmp_path)

    expired = run_checker(tmp_path, "2026-10-01")
    assert expired.returncode == 1
    assert "expired" in expired.stderr

    lock_path = tmp_path / "packages/pi-grid-tools/package-lock.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    lock["packages"]["node_modules/@earendil-works/pi-coding-agent/node_modules/undici"]["version"] = "8.4.0"
    lock_path.write_text(json.dumps(lock), encoding="utf-8")

    worsened = run_checker(tmp_path, "2026-08-28")
    assert worsened.returncode == 1
    assert "vulnerability baseline changed" in worsened.stderr


def test_runtime_risk_exception_rejects_an_installed_graph_that_drifted_from_lock(
    tmp_path: Path,
) -> None:
    write_fixture(tmp_path)
    write_json(
        tmp_path / "packages/pi-grid-tools/node_modules/@earendil-works/pi-ai/package.json",
        {"name": "@earendil-works/pi-ai", "version": "0.80.10"},
    )

    result = run_checker(tmp_path, "2026-08-28")

    assert result.returncode == 1
    assert "installed graph" in result.stderr


def test_runtime_risk_exception_accepts_a_complete_remediation_record_offline(
    tmp_path: Path,
) -> None:
    write_remediated_fixture(tmp_path)

    result = run_checker(tmp_path, "2026-09-05")

    assert result.returncode == 0, result.stderr
    assert "remediation" in result.stdout


def test_runtime_risk_exception_rejects_remediated_lock_without_record(
    tmp_path: Path,
) -> None:
    write_remediated_fixture(tmp_path)
    (tmp_path / "configs/runtime/pi-security-remediation-v1.json").unlink()

    result = run_checker(tmp_path, "2026-09-05")

    assert result.returncode == 1
    assert "unvalidated" in result.stderr


def test_runtime_risk_exception_rejects_remediation_source_lock_and_patch_drift(
    tmp_path: Path,
) -> None:
    write_remediated_fixture(tmp_path)
    source_lock = tmp_path / ".grid-agent/runtime/pi/source/package-lock.json"
    source_lock.write_text(source_lock.read_text(encoding="utf-8") + " ", encoding="utf-8")

    source_drift = run_checker(tmp_path, "2026-09-05")
    assert source_drift.returncode == 1
    assert "managed-pi-runtime" in source_drift.stderr

    write_remediated_fixture(tmp_path)
    patch = tmp_path / "configs/runtime/patches/pi-0.84.4-before-model-request.patch"
    patch.write_text("changed patch", encoding="utf-8")

    patch_drift = run_checker(tmp_path, "2026-09-05")
    assert patch_drift.returncode == 1
    assert "patch" in patch_drift.stderr


def test_runtime_risk_exception_rejects_nested_missing_and_unsafe_remediated_graphs(
    tmp_path: Path,
) -> None:
    write_remediated_fixture(tmp_path)
    nested = tmp_path / "packages/pi-grid-tools/node_modules/@earendil-works/pi-coding-agent/node_modules/undici/package.json"
    nested.write_text('{"name":"undici","version":"9.9.9"}', encoding="utf-8")
    drifted = run_checker(tmp_path, "2026-09-05")
    assert drifted.returncode == 1
    assert "installed graph" in drifted.stderr

    write_remediated_fixture(tmp_path)
    mandatory = tmp_path / "packages/pi-capability-tools/node_modules/@earendil-works/pi-ai/package.json"
    mandatory.unlink()
    missing = run_checker(tmp_path, "2026-09-05")
    assert missing.returncode == 1
    assert "missing" in missing.stderr

    write_remediated_fixture(tmp_path)
    installed_root = tmp_path / "packages/pi-grid-tools/node_modules"
    outside = tmp_path / "outside"
    outside.mkdir()
    installed_root.rename(tmp_path / "saved-node-modules")
    installed_root.symlink_to(outside, target_is_directory=True)
    unsafe = run_checker(tmp_path, "2026-09-05")
    assert unsafe.returncode == 1
    assert "unsafe" in unsafe.stderr

    write_remediated_fixture(tmp_path)
    write_json(
        tmp_path / "packages/pi-grid-tools/node_modules/unrecorded/package.json",
        {"name": "unrecorded", "version": "1.0.0"},
    )
    unrecorded = run_checker(tmp_path, "2026-09-05")
    assert unrecorded.returncode == 1
    assert "unlocked" in unrecorded.stderr


def test_runtime_risk_exception_rejects_ordinary_package_symlink(
    tmp_path: Path,
) -> None:
    write_remediated_fixture(tmp_path)
    target = tmp_path / "packages/pi-grid-tools/node_modules/@earendil-works/pi-coding-agent/node_modules/undici"
    outside = tmp_path / "outside-undici"
    write_json(outside / "package.json", {"name": "undici", "version": "9.0.0"})
    shutil.rmtree(target)
    target.symlink_to(outside, target_is_directory=True)

    result = run_checker(tmp_path, "2026-09-05")

    assert result.returncode == 1
    assert "unsafe" in result.stderr

    write_remediated_fixture(tmp_path)
    scope = tmp_path / "packages/pi-grid-tools/node_modules/@earendil-works"
    outside_scope = tmp_path / "outside-scope"
    scope.rename(outside_scope)
    scope.symlink_to(outside_scope, target_is_directory=True)

    ancestor_result = run_checker(tmp_path, "2026-09-05")

    assert ancestor_result.returncode == 1
    assert "unsafe" in ancestor_result.stderr


def test_runtime_risk_exception_allows_absent_optional_but_rejects_incomplete_audit(
    tmp_path: Path,
) -> None:
    write_remediated_fixture(tmp_path)
    optional = tmp_path / "packages/pi-grid-tools/node_modules/optional-native/package.json"
    optional.unlink()

    optional_absent = run_checker(tmp_path, "2026-09-05")
    assert optional_absent.returncode == 0, optional_absent.stderr

    record_path = tmp_path / "configs/runtime/pi-security-remediation-v1.json"
    record = json.loads(record_path.read_text(encoding="utf-8"))
    record["fresh_audit"]["severity_counts"].pop("info")
    write_json(record_path, record)

    incomplete = run_checker(tmp_path, "2026-09-05")
    assert incomplete.returncode == 1
    assert "audit" in incomplete.stderr

    write_remediated_fixture(tmp_path)
    record = json.loads(record_path.read_text(encoding="utf-8"))
    record["fresh_audit"]["vulnerabilities"] = {"only-info": {}}
    write_json(record_path, record)

    nonempty = run_checker(tmp_path, "2026-09-05")
    assert nonempty.returncode == 1
    assert "vulnerabilities" in nonempty.stderr

    write_remediated_fixture(tmp_path)
    record = json.loads(record_path.read_text(encoding="utf-8"))
    record["fresh_audit"]["audited_on"] = "2026-09-06"
    write_json(record_path, record)

    future = run_checker(tmp_path, "2026-09-05")
    assert future.returncode == 1
    assert "not yet effective" in future.stderr


def test_runtime_risk_exception_rejects_unbound_or_failed_focused_capture(
    tmp_path: Path,
) -> None:
    write_remediated_fixture(tmp_path)
    record_path = tmp_path / "configs/runtime/pi-security-remediation-v1.json"
    record = json.loads(record_path.read_text(encoding="utf-8"))
    record["focused_capture_validation"]["source_revision"] = "wrong-source"
    write_json(record_path, record)

    wrong_source = run_checker(tmp_path, "2026-09-05")
    assert wrong_source.returncode == 1
    assert "focused capture" in wrong_source.stderr

    write_remediated_fixture(tmp_path)
    record = json.loads(record_path.read_text(encoding="utf-8"))
    record["focused_capture_validation"]["result"]["suites"]["pi-capture-grid-tools"]["exit_code"] = 1
    record["focused_capture_validation"]["result_sha256"] = focused_result_digest(record)
    write_json(record_path, record)

    failed_suite = run_checker(tmp_path, "2026-09-05")
    assert failed_suite.returncode == 1
    assert "focused capture" in failed_suite.stderr

    write_remediated_fixture(tmp_path)
    record = json.loads(record_path.read_text(encoding="utf-8"))
    record["focused_capture_validation"]["result_sha256"] = "f" * 64
    write_json(record_path, record)

    digest_drift = run_checker(tmp_path, "2026-09-05")
    assert digest_drift.returncode == 1
    assert "focused capture" in digest_drift.stderr


def run_checker(root: Path, today: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CHECKER), "--root", str(root), "--today", today],
        text=True,
        capture_output=True,
        check=False,
    )


def write_fixture(root: Path) -> None:
    exception = {
        "schema_version": "pi-runtime-security-risk-exception/1.0",
        "exception_id": "PI-SEC-2026-001",
        "issued_on": "2026-08-28",
        "expires_on": "2026-09-30",
        "owner": "grid-agent maintainers",
        "affected_runtime": {"package": "@earendil-works/pi-coding-agent", "version": "0.80.6"},
        "risk_counts": {"high": 2, "moderate": 2},
        "vulnerable_lock_versions": {
            "brace-expansion": "5.0.6",
            "protobufjs": "7.6.4",
            "undici": "8.5.0",
        },
        "attack_surface": ["provider HTTP responses reach the pinned undici client"],
        "mitigations": ["provider credentials remain isolated from simulator children"],
        "upgrade_trigger": "Upgrade when Pi >=0.84.3 passes the request-capture compatibility suite.",
        "target_pi_upgrade": ">=0.84.3",
        "advisories": [
            "GHSA-3jxr-9vmj-r5cp",
            "GHSA-mh99-v99m-4gvg",
            "GHSA-rgw5-rvv9-x895",
            "GHSA-j3f2-48v5-ccww",
            "GHSA-8xcm-r25x-g524",
            "GHSA-4cwx-7wf7-3272",
            "GHSA-m8rv-5g2x-5cg5",
            "GHSA-jr45-8vmc-qm54",
            "GHSA-v3r7-h72x-cjcm",
        ],
    }
    write_json(root / "configs/runtime/pi-security-risk-exception-v1.json", exception)
    write_json(
        root / "configs/runtime/pi-runtime.lock.json",
        {"package": {"name": "@earendil-works/pi-coding-agent", "version": "0.80.6"}},
    )
    for package in ("pi-capability-tools", "pi-grid-tools"):
        dependencies = {
            "@earendil-works/pi-ai": "0.80.6",
            "@earendil-works/pi-coding-agent": "0.80.6",
        }
        if package == "pi-grid-tools":
            dependencies["@capability-agent/pi-tools"] = "file:../pi-capability-tools"
        write_json(
            root / f"packages/{package}/package.json",
            {"name": f"@fixture/{package}", "version": "0.1.0", "dependencies": dependencies},
        )
        locked_packages: dict[str, dict[str, object]] = {
            "node_modules/@earendil-works/pi-ai": {"version": "0.80.6"},
            "node_modules/@earendil-works/pi-coding-agent": {"version": "0.80.6"},
            "node_modules/@earendil-works/pi-coding-agent/node_modules/brace-expansion": {"version": "5.0.6"},
            "node_modules/@earendil-works/pi-coding-agent/node_modules/protobufjs": {"version": "7.6.4"},
            "node_modules/@earendil-works/pi-coding-agent/node_modules/undici": {"version": "8.5.0"},
        }
        if package == "pi-grid-tools":
            locked_packages["node_modules/@capability-agent/pi-tools"] = {
                "resolved": "../pi-capability-tools",
                "link": True,
            }
        write_json(
            root / f"packages/{package}/package-lock.json",
            {"packages": locked_packages},
        )
        for relative, locked in locked_packages.items():
            if locked.get("link") is True:
                continue
            name = relative.rsplit("node_modules/", 1)[-1]
            write_json(
                root / f"packages/{package}/{relative}/package.json",
                {"name": name, "version": locked["version"]},
            )
    local_link = root / "packages/pi-grid-tools/node_modules/@capability-agent/pi-tools"
    local_link.parent.mkdir(parents=True, exist_ok=True)
    local_link.symlink_to(root / "packages/pi-capability-tools", target_is_directory=True)


def write_remediated_fixture(root: Path) -> None:
    shutil.rmtree(root)
    root.mkdir()
    write_fixture(root)
    for package in ("pi-capability-tools", "pi-grid-tools"):
        shutil.rmtree(root / "packages" / package / "node_modules")
    runtime_lock = {
        "schema_version": 2,
        "source": {"repository": "https://example.test/pi.git", "commit": "candidate-0844"},
        "package": {
            "name": "@earendil-works/pi-coding-agent",
            "version": "0.84.4",
            "directory": "packages/coding-agent",
            "executable": "dist/cli.js",
            "oauth_helper": "packages/ai/dist/cli.js",
            "npm_integrity": "sha512-coding-agent",
        },
        "runtime": {
            "node_minimum": "22.19.0",
            "pi_ai_version": "0.84.4",
            "pi_ai_npm_integrity": "sha512-pi-ai",
        },
        "patches": [{"path": "patches/pi-0.84.4-before-model-request.patch", "sha256": ""}],
    }
    patch_path = root / "configs/runtime/patches/pi-0.84.4-before-model-request.patch"
    patch_path.parent.mkdir(parents=True, exist_ok=True)
    patch_path.write_text("candidate patch", encoding="utf-8")
    runtime_lock["patches"][0]["sha256"] = sha256_file(patch_path)
    write_json(root / "configs/runtime/pi-runtime.lock.json", runtime_lock)

    package_locks: dict[str, dict[str, object]] = {}
    for package in ("pi-capability-tools", "pi-grid-tools"):
        package_root = root / "packages" / package
        dependencies = {
            "@earendil-works/pi-ai": "0.84.4",
            "@earendil-works/pi-coding-agent": "0.84.4",
        }
        if package == "pi-grid-tools":
            dependencies["@capability-agent/pi-tools"] = "file:../pi-capability-tools"
        write_json(package_root / "package.json", {"name": f"@fixture/{package}", "version": "0.1.0", "dependencies": dependencies})
        packages: dict[str, dict[str, object]] = {
            "node_modules/@earendil-works/pi-ai": {"version": "0.84.4", "integrity": "sha512-ai"},
            "node_modules/@earendil-works/pi-coding-agent": {"version": "0.84.4", "integrity": "sha512-agent"},
            "node_modules/@earendil-works/pi-coding-agent/node_modules/@earendil-works/pi-agent-core": {
                "version": "0.84.4",
                "resolved": "https://registry.npmjs.org/@earendil-works/pi-agent-core/-/pi-agent-core-0.84.4.tgz",
            },
            "node_modules/@earendil-works/pi-coding-agent/node_modules/undici": {"version": "9.0.0", "integrity": "sha512-undici"},
        }
        if package == "pi-grid-tools":
            packages["node_modules/optional-native"] = {"version": "1.0.0", "integrity": "sha512-optional", "optional": True}
            packages["node_modules/@capability-agent/pi-tools"] = {"resolved": "../pi-capability-tools", "link": True}
        package_locks[package] = packages
        write_json(package_root / "package-lock.json", {"lockfileVersion": 3, "packages": packages})
        for relative, locked in packages.items():
            if locked.get("link") is not True:
                write_json(package_root / relative / "package.json", {"name": package_name(relative), "version": locked["version"]})
        write_json(
            package_root / "node_modules/@earendil-works/pi-coding-agent/dist/esm/package.json",
            {"name": "pi-coding-agent-dist-metadata", "version": "0.84.4"},
        )

    local_link = root / "packages/pi-grid-tools/node_modules/@capability-agent/pi-tools"
    if local_link.exists() or local_link.is_symlink():
        local_link.unlink()
    local_link.parent.mkdir(parents=True, exist_ok=True)
    local_link.symlink_to(root / "packages/pi-capability-tools", target_is_directory=True)

    source_root = root / ".grid-agent/runtime/pi/source"
    source_packages: dict[str, dict[str, object]] = {
        "node_modules/@earendil-works/pi-coding-agent": {"version": "0.84.4", "integrity": "sha512-agent"},
        "node_modules/@earendil-works/pi-ai": {"version": "0.84.4", "integrity": "sha512-ai"},
    }
    write_json(source_root / "package-lock.json", {"lockfileVersion": 3, "packages": source_packages})
    for relative, locked in source_packages.items():
        write_json(source_root / relative / "package.json", {"name": package_name(relative), "version": locked["version"]})

    exception_path = root / "configs/runtime/pi-security-risk-exception-v1.json"
    runtime_path = root / "configs/runtime/pi-runtime.lock.json"
    record = {
        "schema_version": "pi-runtime-security-remediation/1.0",
        "remediation_id": "PI-SEC-2026-001-0.84.4",
        "replaces_exception": {"exception_id": "PI-SEC-2026-001", "sha256": sha256_file(exception_path)},
        "validated_runtime": {
            "package": "@earendil-works/pi-coding-agent",
            "version": "0.84.4",
            "runtime_lock_sha256": sha256_file(runtime_path),
            "source_repository": "https://example.test/pi.git",
            "source_commit": "candidate-0844",
            "npm_integrity": "sha512-coding-agent",
            "pi_ai_version": "0.84.4",
            "pi_ai_npm_integrity": "sha512-pi-ai",
            "patches": runtime_lock["patches"],
            "patch_set_sha256": patch_set_sha256(runtime_lock["patches"]),
        },
        "package_locks": {},
        "frozen_lock_graphs": {},
        "fresh_audit": {
            "audited_on": "2026-09-05",
            "tool": "npm audit",
            "tool_version": "11.0.0",
            "audit_scope": ["managed-pi-runtime", "pi-capability-tools", "pi-grid-tools"],
            "audited_lock_sha256": {},
            "result_sha256": "0" * 64,
            "audit_format": "npm-audit-v2",
            "severity_counts": {"info": 0, "low": 0, "moderate": 0, "high": 0, "critical": 0, "total": 0},
            "vulnerabilities": {},
        },
        "focused_capture_validation": {
            "completed_on": "2026-09-05",
            "source_revision": "candidate-0844",
            "result": {
                "runtime_commit": "candidate-0844",
                "patch_set_sha256": patch_set_sha256(runtime_lock["patches"]),
                "suites": {
                    "pi-capture-capability-tools": {"exit_code": 0, "assertion_count": 1},
                    "pi-capture-grid-tools": {"exit_code": 0, "assertion_count": 1},
                },
            },
        },
    }
    roots = {
        "managed-pi-runtime": (source_root, "source/package-lock.json", source_packages),
        "pi-capability-tools": (root / "packages/pi-capability-tools", "packages/pi-capability-tools/package-lock.json", package_locks["pi-capability-tools"]),
        "pi-grid-tools": (root / "packages/pi-grid-tools", "packages/pi-grid-tools/package-lock.json", package_locks["pi-grid-tools"]),
    }
    for identity, (package_root, lock_path, packages) in roots.items():
        digest = sha256_file(package_root / "package-lock.json")
        record["package_locks"][identity] = {"path": lock_path, "sha256": digest}
        record["fresh_audit"]["audited_lock_sha256"][identity] = digest
        graph = normalized_graph(packages)
        record["frozen_lock_graphs"][identity] = {"sha256": sha256_json(graph), "packages": graph}
    record["focused_capture_validation"]["result_sha256"] = focused_result_digest(record)
    write_json(root / "configs/runtime/pi-security-remediation-v1.json", record)


def package_name(relative: str) -> str:
    return relative.rsplit("node_modules/", 1)[-1]


def normalized_graph(packages: dict[str, dict[str, object]]) -> list[dict[str, object]]:
    graph: list[dict[str, object]] = []
    for path, metadata in sorted(packages.items()):
        if metadata.get("link") is True:
            graph.append({
                "path": path,
                "link": True,
                "resolved": metadata["resolved"],
                "name": "@fixture/pi-capability-tools",
                "version": "0.1.0",
            })
        else:
            entry: dict[str, object] = {
                "path": path,
                "name": package_name(path),
                "version": metadata["version"],
                "optional": metadata.get("optional", False),
            }
            if "integrity" in metadata:
                entry["integrity"] = metadata["integrity"]
            else:
                entry["resolved"] = metadata["resolved"]
            graph.append(entry)
    return graph


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_json(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def patch_set_sha256(patches: list[dict[str, str]]) -> str:
    return sha256_json(patches)


def focused_result_digest(record: dict[str, object]) -> str:
    capture = record["focused_capture_validation"]
    assert isinstance(capture, dict)
    return sha256_json(capture["result"])


def write_json(path: Path, document: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document), encoding="utf-8")
