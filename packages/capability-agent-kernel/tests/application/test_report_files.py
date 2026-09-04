from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from capability_agent.application.errors import PresentationError
from capability_agent.application.runner import _write_report_atomically


def test_report_writer_publishes_complete_private_file(tmp_path: Path) -> None:
    target = tmp_path / "output" / "report.md"

    _write_report_atomically(target, "complete report\n")

    assert target.read_text() == "complete report\n"
    assert target.stat().st_mode & 0o777 == 0o600
    assert tuple(target.parent.iterdir()) == (target,)


@pytest.mark.parametrize("replace_parent", [False, True])
def test_report_writer_rejects_existing_symlinks(
    tmp_path: Path, replace_parent: bool
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "report.md"
    sentinel.write_text("outside bytes")
    parent = tmp_path / "output"
    if replace_parent:
        parent.symlink_to(outside, target_is_directory=True)
    else:
        parent.mkdir()
        (parent / "report.md").symlink_to(sentinel)

    with pytest.raises(PresentationError):
        _write_report_atomically(parent / "report.md", "new report")

    assert sentinel.read_text() == "outside bytes"
    assert tuple(outside.iterdir()) == (sentinel,)


def test_report_writer_rejects_substituted_stage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parent = tmp_path / "output"
    parent.mkdir()
    target = parent / "report.md"
    original_fsync = os.fsync
    swapped = False

    def swap_after_file_flush(descriptor: int) -> None:
        nonlocal swapped
        original_fsync(descriptor)
        if not swapped and stat.S_ISREG(os.fstat(descriptor).st_mode):
            staged = tuple(parent.glob(".report.md.*"))
            if staged:
                swapped = True
                staged[0].rename(parent / "original-stage")
                staged[0].write_text("substituted bytes")

    monkeypatch.setattr(os, "fsync", swap_after_file_flush)
    with pytest.raises(PresentationError):
        _write_report_atomically(target, "trusted report")

    assert swapped
    assert not target.exists()


def test_report_writer_handles_partial_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_write = os.write

    def partial_write(descriptor: int, data) -> int:
        return original_write(descriptor, data[:2])

    monkeypatch.setattr(os, "write", partial_write)
    target = tmp_path / "report.md"
    _write_report_atomically(target, "完整报告\n")
    assert target.read_text() == "完整报告\n"


def test_report_writer_does_not_follow_parent_swapped_before_temp_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parent = tmp_path / "output"
    parent.mkdir()
    detached = tmp_path / "detached-output"
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "report.md"
    sentinel.write_text("outside bytes")
    original_open = os.open
    swapped = False

    def swap_then_open(path, flags, mode=0o777, *, dir_fd=None):
        nonlocal swapped
        if not swapped and flags & os.O_CREAT and Path(path).name.startswith(".report.md."):
            swapped = True
            parent.rename(detached)
            parent.symlink_to(outside, target_is_directory=True)
        return original_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(os, "open", swap_then_open)
    try:
        _write_report_atomically(parent / "report.md", "private report bytes")
    except PresentationError:
        pass

    assert swapped
    assert sentinel.read_text() == "outside bytes"
    assert tuple(outside.iterdir()) == (sentinel,)
