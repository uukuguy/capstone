from __future__ import annotations

import pytest

from capability_agent.runtime.lock import PiRuntimeLock, PiRuntimeLockError


def _valid_lock() -> dict[str, object]:
    return {
        "schema_version": 2,
        "source": {
            "repository": "https://github.com/earendil-works/pi.git",
            "commit": "b79e4cc834970cca69daebffab7df1da7d1e52c4",
        },
        "package": {
            "name": "@earendil-works/pi-coding-agent",
            "version": "0.84.4",
            "directory": "packages/coding-agent",
            "executable": "dist/cli.js",
            "oauth_helper": "packages/ai/dist/cli.js",
            "npm_integrity": "sha512-jmOlrqUmvhh/siNWFRXjYLJzhKFIHNsAQaysRwzQPQFnPAaV/vhqHsLH/MBsIISA1Rjj7WTUFR3nJrpXoLx39w==",
        },
        "runtime": {
            "node_minimum": "22.19.0",
            "pi_ai_version": "0.84.4",
            "pi_ai_npm_integrity": "sha512-AClAZxf5+c4RRu44NJPS6wyQy+Nmq+Mzyyrdvm4ZVMNuixelO02RZX4G4Aq1F145Yzp43wnM5S+hLlSI7ypfVw==",
        },
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("directory", "/tmp/managed-runtime"),
        ("directory", "../outside"),
        ("executable", "../outside.js"),
        ("oauth_helper", "/tmp/helper.js"),
    ],
)
def test_lock_rejects_package_paths_outside_managed_source(
    field: str, value: str
) -> None:
    payload = _valid_lock()
    package = dict(payload["package"])  # type: ignore[arg-type]
    package[field] = value
    payload["package"] = package

    with pytest.raises(PiRuntimeLockError, match="path"):
        PiRuntimeLock._validate(payload)


def test_lock_accepts_the_selected_candidate_identity() -> None:
    PiRuntimeLock._validate(_valid_lock())
