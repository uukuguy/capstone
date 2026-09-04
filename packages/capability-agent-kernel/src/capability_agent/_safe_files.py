"""Small descriptor-relative readers for integrity-sensitive artifacts."""

from __future__ import annotations

import os
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


_CLOSE_ON_EXEC = getattr(os, "O_CLOEXEC", 0)
_NO_FOLLOW = getattr(os, "O_NOFOLLOW", 0)
_DIRECTORY = getattr(os, "O_DIRECTORY", 0)
_READ_FLAGS = os.O_RDONLY | _CLOSE_ON_EXEC | _NO_FOLLOW
_DIRECTORY_FLAGS = _READ_FLAGS | _DIRECTORY


@contextmanager
def open_bound_parent(path: Path) -> Iterator[tuple[int, str]]:
    """Pin every parent component without traversing a symbolic link."""

    absolute = Path(os.path.abspath(os.fspath(path)))
    parts = absolute.parts
    if len(parts) < 2 or not absolute.name:
        raise OSError("artifact path has no leaf name")
    descriptor = os.open(absolute.anchor, _DIRECTORY_FLAGS)
    try:
        for component in parts[1:-1]:
            child = os.open(
                component,
                _DIRECTORY_FLAGS,
                dir_fd=descriptor,
            )
            previous = descriptor
            descriptor = child
            os.close(previous)
        yield descriptor, absolute.name
    finally:
        os.close(descriptor)


def read_bound_regular_file(parent: int, name: str) -> bytes:
    """Read one pinned-directory leaf and reject identity or content changes."""

    if not isinstance(name, str) or not name or Path(name).name != name:
        raise OSError("artifact leaf name is invalid")
    descriptor = os.open(name, _READ_FLAGS, dir_fd=parent)
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise OSError("artifact must be a regular file")
        chunks: list[bytes] = []
        while chunk := os.read(descriptor, 64 * 1024):
            chunks.append(chunk)
        after = os.fstat(descriptor)
        named = os.stat(name, dir_fd=parent, follow_symlinks=False)
        if (
            _file_identity(before) != _file_identity(after)
            or _file_identity(named) != _file_identity(after)
        ):
            raise OSError("artifact changed while read")
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def read_bound_regular_path(path: Path) -> bytes:
    """Read one path through a descriptor-pinned, no-follow parent chain."""

    with open_bound_parent(path) as (parent, name):
        return read_bound_regular_file(parent, name)


def _file_identity(metadata: os.stat_result) -> tuple[int, int, int, int, int, int]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


__all__ = [
    "open_bound_parent",
    "read_bound_regular_file",
    "read_bound_regular_path",
]
