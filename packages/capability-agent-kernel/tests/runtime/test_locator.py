from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from capability_agent.runtime.locator import (
    ENV_PI_COMMAND,
    PiRuntimeLocator,
    PiRuntimeLocatorError,
)
from capability_agent.runtime.lock import PiRuntimeLock


def _managed_fixture(root: Path, lock: PiRuntimeLock) -> tuple[Path, Path, Path]:
    runtime_dir = root / "pi"
    source = runtime_dir / "source"
    cli = source / lock.executable
    helper = source / lock.oauth_helper
    cli.parent.mkdir(parents=True)
    helper.parent.mkdir(parents=True, exist_ok=True)
    cli.write_text("#!/usr/bin/env node\n", encoding="utf-8")
    helper.write_text("#!/usr/bin/env node\n", encoding="utf-8")
    marker = runtime_dir / "active"
    marker.write_text(
        f"{source}\n"
        f"commit={lock.commit}\n"
        f"lock_sha256={lock.sha256}\n"
        f"patches_sha256={lock.patches_sha256}\n",
        encoding="utf-8",
    )
    return runtime_dir, source, marker


@pytest.fixture
def runtime_lock() -> PiRuntimeLock:
    return PiRuntimeLock.load()


def test_locator_rejects_symlinked_managed_source(
    tmp_path: Path, runtime_lock: PiRuntimeLock
) -> None:
    runtime_dir = tmp_path / "pi"
    runtime_dir.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (runtime_dir / "source").symlink_to(outside, target_is_directory=True)

    with pytest.raises(PiRuntimeLocatorError, match="symlink"):
        PiRuntimeLocator(runtime_dir, {}, runtime_lock=runtime_lock).resolve(
            require_managed=True
        )


def test_locator_rejects_symlinked_active_marker(
    tmp_path: Path, runtime_lock: PiRuntimeLock
) -> None:
    runtime_dir, _source, marker = _managed_fixture(tmp_path, runtime_lock)
    outside = tmp_path / "marker"
    outside.write_text(marker.read_text(encoding="utf-8"), encoding="utf-8")
    marker.unlink()
    marker.symlink_to(outside)

    with pytest.raises(PiRuntimeLocatorError, match="symlink"):
        PiRuntimeLocator(runtime_dir, {}, runtime_lock=runtime_lock).resolve(
            require_managed=True
        )


def test_locator_rejects_symlinked_managed_executable(
    tmp_path: Path, runtime_lock: PiRuntimeLock
) -> None:
    runtime_dir, source, _marker = _managed_fixture(tmp_path, runtime_lock)
    cli = source / runtime_lock.executable
    outside = tmp_path / "pi.js"
    outside.write_text("#!/usr/bin/env node\n", encoding="utf-8")
    cli.unlink()
    cli.symlink_to(outside)

    with pytest.raises(PiRuntimeLocatorError, match="symlink"):
        PiRuntimeLocator(runtime_dir, {}, runtime_lock=runtime_lock).resolve(
            require_managed=True
        )


def test_locator_sanitizes_non_text_version_probe_output(
    tmp_path: Path, runtime_lock: PiRuntimeLock
) -> None:
    def bad_runner(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[object]:
        return subprocess.CompletedProcess([], 0, None, None)

    with pytest.raises(PiRuntimeLocatorError, match="version probe"):
        PiRuntimeLocator(
            tmp_path / "pi",
            {ENV_PI_COMMAND: "/opt/pi"},
            runtime_lock=runtime_lock,
            runner=bad_runner,
        ).probe()
