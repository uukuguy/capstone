from __future__ import annotations

import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]


def _run_entrypoint(tmp_path: Path, role: str, application: str | None) -> list[str]:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir(parents=True)
    calls = tmp_path / "calls"
    fake_uv = fake_bin / "uv"
    fake_uv.write_text(
        "#!/bin/sh\nprintf '%s\\n' \"$*\" > \"$CAPSTONE_TEST_CALLS\"\n"
        "printf '%s' \"${CAPSTONE_THREAD_FAMILY:-}\" > \"$CAPSTONE_TEST_CALLS.family\"\n",
        encoding="utf-8",
    )
    fake_uv.chmod(0o755)
    environment = os.environ | {
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "CAPSTONE_TEST_CALLS": str(calls),
        "CAPSTONE_THREAD_FAMILY": "wrong-family",
    }
    if application is None:
        environment.pop("CAPSTONE_HOSTED_APPLICATION", None)
    else:
        environment["CAPSTONE_HOSTED_APPLICATION"] = application
    subprocess.run(
        ["sh", str(ROOT / "deploy" / "entrypoint.sh"), role],
        cwd=ROOT,
        env=environment,
        check=True,
    )
    return calls.read_text(encoding="utf-8").splitlines()


def test_entrypoint_defaults_to_pandapower_adapter(tmp_path: Path) -> None:
    assert _run_entrypoint(tmp_path, "api", None) == [
        "run --no-sync --project /app/packages/grid-agent python -m grid_agent.hosted",
    ]


def test_entrypoint_selects_pypsa_adapter_for_api_and_worker(tmp_path: Path) -> None:
    assert _run_entrypoint(tmp_path / "api", "api", "pypsa") == [
        "run --no-sync --project /app/packages/pypsa-agent python -m pypsa_agent.hosted",
    ]
    assert _run_entrypoint(tmp_path / "worker", "worker", "pypsa") == [
        "run --no-sync --project /app/packages/pypsa-agent python -m pypsa_agent.hosted_worker",
    ]


def test_entrypoint_rejects_unknown_hosted_application(tmp_path: Path) -> None:
    environment = os.environ | {"CAPSTONE_HOSTED_APPLICATION": "unknown"}
    result = subprocess.run(
        ["sh", str(ROOT / "deploy" / "entrypoint.sh"), "api"],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 64
    assert "CAPSTONE_HOSTED_APPLICATION" in result.stderr


def test_federated_api_and_pinned_family_workers(tmp_path: Path) -> None:
    assert _run_entrypoint(tmp_path / "api", "api", "capstone") == [
        "run --no-sync --project /app/packages/capstone-agent python -m capstone_agent.federated_hosted",
    ]
    for family in ("pandapower", "pypsa"):
        _run_entrypoint(tmp_path / family, "worker", family)
        assert (tmp_path / family / "calls.family").read_text() == family
    result = subprocess.run(["sh", str(ROOT / "deploy/entrypoint.sh"), "worker"],
                            env=os.environ | {"CAPSTONE_HOSTED_APPLICATION": "capstone"},
                            capture_output=True)
    assert result.returncode == 64
