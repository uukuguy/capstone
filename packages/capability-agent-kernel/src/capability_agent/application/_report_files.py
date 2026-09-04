"""Descriptor-bound publication for optional application reports."""

from __future__ import annotations

import os
import secrets
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from capability_agent._safe_files import open_bound_parent
from capability_agent.application.errors import PresentationError


_DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
_CREATE_FLAGS = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC


@contextmanager
def _publication_parent(target: Path) -> Iterator[int]:
    descriptor = os.open(target.anchor, _DIRECTORY_FLAGS)
    try:
        for component in target.parts[1:-1]:
            try:
                os.mkdir(component, 0o700, dir_fd=descriptor)
            except FileExistsError:
                pass
            child = os.open(component, _DIRECTORY_FLAGS, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        yield descriptor
    finally:
        os.close(descriptor)


def _identity(metadata: os.stat_result) -> tuple[int, int]:
    return metadata.st_dev, metadata.st_ino


def _file_state(metadata: os.stat_result) -> tuple[int, int, int, int, int, int]:
    return (
        metadata.st_dev, metadata.st_ino, metadata.st_mode, metadata.st_size,
        metadata.st_mtime_ns, metadata.st_ctime_ns,
    )


def _check_parent_binding(target: Path, parent: int) -> None:
    with open_bound_parent(target) as (named_parent, _name):
        if _identity(os.fstat(parent)) != _identity(os.fstat(named_parent)):
            raise OSError("report parent changed")


def _reject_unsafe_leaf(parent: int, name: str) -> None:
    try:
        metadata = os.stat(name, dir_fd=parent, follow_symlinks=False)
    except FileNotFoundError:
        return
    if not stat.S_ISREG(metadata.st_mode):
        raise OSError("report destination is not a regular file")


def write_report_atomically(path: Path, report: str) -> None:
    """Publish a complete private file without traversing substituted parents."""
    target = Path(os.path.abspath(os.fspath(path)))
    try:
        with _publication_parent(target) as parent:
            _reject_unsafe_leaf(parent, target.name)
            temporary = f".{target.name}.{secrets.token_hex(16)}.tmp"
            descriptor = os.open(temporary, _CREATE_FLAGS, 0o600, dir_fd=parent)
            published = False
            try:
                os.fchmod(descriptor, 0o600)
                pending = memoryview(report.encode("utf-8"))
                while pending:
                    written = os.write(descriptor, pending)
                    if written <= 0:
                        raise OSError("report write made no progress")
                    pending = pending[written:]
                os.fsync(descriptor)
                expected = os.fstat(descriptor)
                named = os.stat(temporary, dir_fd=parent, follow_symlinks=False)
                if _file_state(expected) != _file_state(named):
                    raise OSError("report stage changed")
                _check_parent_binding(target, parent)
                _reject_unsafe_leaf(parent, target.name)
                os.replace(temporary, target.name, src_dir_fd=parent, dst_dir_fd=parent)
                published = True
                after = os.fstat(descriptor)
                named = os.stat(target.name, dir_fd=parent, follow_symlinks=False)
                if (
                    _identity(after) != _identity(expected)
                    or after.st_size != expected.st_size
                    or after.st_mtime_ns != expected.st_mtime_ns
                    or _file_state(after) != _file_state(named)
                ):
                    raise OSError("published report changed")
                os.fsync(parent)
                _check_parent_binding(target, parent)
            finally:
                if not published:
                    try:
                        named = os.stat(temporary, dir_fd=parent, follow_symlinks=False)
                        if _identity(named) == _identity(os.fstat(descriptor)):
                            os.unlink(temporary, dir_fd=parent)
                    except OSError:
                        pass
                os.close(descriptor)
    except OSError as exc:
        raise PresentationError("report could not be persisted") from exc
