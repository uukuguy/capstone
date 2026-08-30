from __future__ import annotations

import pytest

from capability_agent.runtime.lock import PiRuntimeLock, PiRuntimeLockError


def _valid_lock() -> dict[str, object]:
    return {
        "schema_version": 2,
        "source": {
            "repository": "https://github.com/earendil-works/pi.git",
            "commit": "2b3fda9921b5590f285165287bd442a25817f17b",
        },
        "package": {
            "name": "@earendil-works/pi-coding-agent",
            "version": "0.80.6",
            "directory": "packages/coding-agent",
            "executable": "dist/cli.js",
            "oauth_helper": "packages/ai/dist/cli.js",
            "npm_integrity": "sha512-vcfD6tOk402isLl3Cm/qbn2O10TvgroMp1+/fEGM24ZdvETFCdOYv5VZ7m59EI5fPsjfSJh+CpQ5bhBrhfOg7g==",
        },
        "runtime": {
            "node_minimum": "22.19.0",
            "pi_ai_version": "0.80.6",
            "pi_ai_npm_integrity": "sha512-7xfLk8sANBp+bpPEbjoOZTbPxsa+++b1JXAoSJsNa3vbs9AHHEclmvg54XLQcxH+fuwaeti/g2jeIfJ+mVYLpA==",
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
