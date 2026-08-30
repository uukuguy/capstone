from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from capability_agent.runtime.installer import PiRuntimeInstaller, PiRuntimeInstallerError
from capability_agent.runtime.lock import PiRuntimeLock


def test_installer_sanitizes_command_diagnostics(tmp_path: Path) -> None:
    lock = PiRuntimeLock.load()

    def failing_runner(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args[0] if args else [], 1, "", "secret=topsecret command failed"
        )

    installer = PiRuntimeInstaller(
        lock,
        tmp_path / "pi",
        runner=failing_runner,
    )
    with pytest.raises(PiRuntimeInstallerError, match="git") as captured:
        installer._run(["git", "status"])
    assert "topsecret" not in str(captured.value)


def test_installer_rejects_non_text_runner_diagnostic(tmp_path: Path) -> None:
    lock = PiRuntimeLock.load()

    def malformed_runner(*args: object, **kwargs: object) -> subprocess.CompletedProcess[object]:
        return subprocess.CompletedProcess(args[0] if args else [], 1, None, None)

    installer = PiRuntimeInstaller(lock, tmp_path / "pi", runner=malformed_runner)
    with pytest.raises(PiRuntimeInstallerError, match="command failed"):
        installer._run(["git", "status"])
