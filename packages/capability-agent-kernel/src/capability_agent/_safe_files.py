"""Small descriptor-relative readers for integrity-sensitive artifacts."""

from __future__ import annotations

import os
import secrets
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


_CLOSE_ON_EXEC = getattr(os, "O_CLOEXEC", 0)
_NO_FOLLOW = getattr(os, "O_NOFOLLOW", 0)
_DIRECTORY = getattr(os, "O_DIRECTORY", 0)
_READ_FLAGS = os.O_RDONLY | _CLOSE_ON_EXEC | _NO_FOLLOW
_DIRECTORY_FLAGS = _READ_FLAGS | _DIRECTORY
_CREATE_FLAGS = os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NO_FOLLOW | _CLOSE_ON_EXEC


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


def write_bound_text(path: Path, content: str) -> None:
    """Atomically publish text without following parent or leaf symlinks."""

    target = Path(os.path.abspath(os.fspath(path)))
    with _created_bound_parent(target) as parent:
        _require_regular_or_absent(parent, target.name)
        temporary = f".{target.name}.{secrets.token_hex(16)}.tmp"
        descriptor = os.open(temporary, _CREATE_FLAGS, 0o600, dir_fd=parent)
        published = False
        try:
            pending = memoryview(content.encode("utf-8"))
            while pending:
                written = os.write(descriptor, pending)
                if written <= 0:
                    raise OSError("file write made no progress")
                pending = pending[written:]
            os.fsync(descriptor)
            staged = os.fstat(descriptor)
            named_stage = os.stat(temporary, dir_fd=parent, follow_symlinks=False)
            if _file_identity(staged) != _file_identity(named_stage):
                raise OSError("publication stage changed")
            _require_same_parent(target, parent)
            _require_regular_or_absent(parent, target.name)
            os.replace(temporary, target.name, src_dir_fd=parent, dst_dir_fd=parent)
            published = True
            after = os.fstat(descriptor)
            named_target = os.stat(target.name, dir_fd=parent, follow_symlinks=False)
            if _file_identity(after) != _file_identity(named_target):
                raise OSError("published file changed")
            os.fsync(parent)
            _require_same_parent(target, parent)
        finally:
            if not published:
                try:
                    os.unlink(temporary, dir_fd=parent)
                except FileNotFoundError:
                    pass
            os.close(descriptor)


def ensure_bound_directory(path: Path) -> Path:
    """Create each missing directory while refusing symbolic-link components."""

    target = Path(os.path.abspath(os.fspath(path)))
    descriptor = os.open(target.anchor, _DIRECTORY_FLAGS)
    try:
        for component in target.parts[1:]:
            try:
                os.mkdir(component, 0o700, dir_fd=descriptor)
            except FileExistsError:
                pass
            child = os.open(component, _DIRECTORY_FLAGS, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        with open_bound_parent(target) as (parent, name):
            named = os.stat(name, dir_fd=parent, follow_symlinks=False)
            current = os.fstat(descriptor)
            if (
                not stat.S_ISDIR(named.st_mode)
                or (named.st_dev, named.st_ino) != (current.st_dev, current.st_ino)
            ):
                raise OSError("directory changed while prepared")
    finally:
        os.close(descriptor)
    return target


@contextmanager
def _created_bound_parent(path: Path) -> Iterator[int]:
    if not path.name:
        raise OSError("publication path has no leaf name")
    descriptor = os.open(path.anchor, _DIRECTORY_FLAGS)
    try:
        for component in path.parts[1:-1]:
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


def _require_regular_or_absent(parent: int, name: str) -> None:
    try:
        metadata = os.stat(name, dir_fd=parent, follow_symlinks=False)
    except FileNotFoundError:
        return
    if not stat.S_ISREG(metadata.st_mode):
        raise OSError("publication destination is not a regular file")


def _require_same_parent(path: Path, parent: int) -> None:
    with open_bound_parent(path) as (named_parent, _name):
        actual = os.fstat(named_parent)
        expected = os.fstat(parent)
        if (actual.st_dev, actual.st_ino) != (expected.st_dev, expected.st_ino):
            raise OSError("publication parent changed")


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
    "ensure_bound_directory",
    "read_bound_regular_file",
    "read_bound_regular_path",
    "write_bound_text",
]
