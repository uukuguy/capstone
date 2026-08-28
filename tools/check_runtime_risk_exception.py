#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any


EXCEPTION_PATH = Path("configs/runtime/pi-security-risk-exception-v1.json")
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
        verify(args.root.resolve(), args.today)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"runtime-risk-exception: rejected: {exc}", file=sys.stderr)
        return 1
    print(
        "runtime-risk-exception: accepted 2 high, 2 moderate through 2026-09-30"
    )
    return 0


def verify(root: Path, today: date) -> None:
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


if __name__ == "__main__":
    raise SystemExit(main())
