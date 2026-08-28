from __future__ import annotations

import json
import subprocess
import sys
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
        write_json(
            root / f"packages/{package}/package.json",
            {"dependencies": {"@earendil-works/pi-coding-agent": "0.80.6"}},
        )
        write_json(
            root / f"packages/{package}/package-lock.json",
            {
                "packages": {
                    "node_modules/@earendil-works/pi-coding-agent": {"version": "0.80.6"},
                    "node_modules/@earendil-works/pi-coding-agent/node_modules/brace-expansion": {"version": "5.0.6"},
                    "node_modules/@earendil-works/pi-coding-agent/node_modules/protobufjs": {"version": "7.6.4"},
                    "node_modules/@earendil-works/pi-coding-agent/node_modules/undici": {"version": "8.5.0"},
                }
            },
        )


def write_json(path: Path, document: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document), encoding="utf-8")
