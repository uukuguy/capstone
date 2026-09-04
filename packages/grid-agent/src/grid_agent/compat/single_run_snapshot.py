"""Opaque application delivery copies; never a second authority root.

All three views are staged before publication. Each public name is installed
exclusively. Only successful return means the delivery finished; publication is
not atomic across the three names. Failed staging/publication is retained for
diagnosis and never changes canonical answers or becomes authority input.
"""

from __future__ import annotations

import ctypes
import errno
import os
import secrets
import stat
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Callable, Iterator


_READ = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
_DIRECTORY = _READ | os.O_DIRECTORY
_CREATE = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC
_VIEWS = ("events.jsonl", "tool-results", "evidence")


@dataclass(frozen=True)
class _StagedObject:
    identity: tuple[int, ...]
    digest: str | None = None


def publish_compatibility_snapshot(workspace: Path) -> None:
    """Publish complete physical copies, refusing existing delivery targets."""
    with _directory_chain(workspace) as (root, validate):
        for name in _VIEWS:
            try:
                os.stat(name, dir_fd=root, follow_symlinks=False)
            except FileNotFoundError:
                continue
            raise FileExistsError("compatibility destination already exists")
        stage_name = ".single-run-snapshot-" + secrets.token_hex(16)
        os.mkdir(stage_name, mode=0o700, dir_fd=root)
        expected: dict[tuple[str, ...], _StagedObject] = {}
        with _directory_at(root, stage_name) as stage:
            with _directory_at(root, "core") as core:
                expected[("events.jsonl",)] = _copy_file(core, "events.jsonl", stage, "events.jsonl")
            with _directory_at(root, "domains") as domains:
                with _directory_at(domains, "grid") as grid:
                    for name in ("tool-results", "evidence"):
                        os.mkdir(name, mode=0o700, dir_fd=stage)
                        with _directory_at(stage, name) as destination:
                            try:
                                metadata = os.stat(name, dir_fd=grid, follow_symlinks=False)
                            except FileNotFoundError:
                                if name != "evidence":
                                    raise
                            else:
                                if not stat.S_ISDIR(metadata.st_mode):
                                    raise ValueError("snapshot source is not a directory")
                                with _directory_at(grid, name) as source:
                                    _copy_tree(source, destination, expected, (name,))
                            os.fsync(destination)
                            expected[(name,)] = _StagedObject(_published_identity(os.fstat(destination)))
            os.fsync(stage)
            for name in _VIEWS:
                _verify_staged_tree(stage, name, expected, (name,))
            for name in _VIEWS:
                validate()
                _check_directory_binding(root, stage_name, stage)
                _verify_staged_tree(stage, name, expected, (name,))
                _rename_exclusive(stage, name, root, name)
                _verify_staged_tree(root, name, expected, (name,))
                os.fsync(root)
                validate()
        # Only the now-empty, task-created staging directory is removed.
        # On any exception it remains, and published names are never rolled back
        # through replaceable paths that might have acquired another owner.
        os.rmdir(stage_name, dir_fd=root)


@contextmanager
def _directory_chain(path: Path) -> Iterator[tuple[int, Callable[[], None]]]:
    absolute = Path(os.path.abspath(path))
    descriptors = [os.open(absolute.anchor, _DIRECTORY)]
    bindings: list[tuple[int, str, int]] = []

    def validate() -> None:
        for parent, name, child in bindings:
            _check_directory_binding(parent, name, child)

    try:
        for name in absolute.parts[1:]:
            child = os.open(name, _DIRECTORY, dir_fd=descriptors[-1])
            bindings.append((descriptors[-1], name, child))
            descriptors.append(child)
            _check_directory_binding(*bindings[-1])
        validate()
        yield descriptors[-1], validate
        validate()
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


@contextmanager
def _directory_at(parent: int, name: str) -> Iterator[int]:
    descriptor = os.open(name, _DIRECTORY, dir_fd=parent)
    try:
        _check_directory_binding(parent, name, descriptor)
        yield descriptor
        _check_directory_binding(parent, name, descriptor)
    finally:
        os.close(descriptor)


def _check_directory_binding(parent: int, name: str, descriptor: int) -> None:
    opened = os.fstat(descriptor)
    named = os.stat(name, dir_fd=parent, follow_symlinks=False)
    if (
        not stat.S_ISDIR(named.st_mode)
        or not stat.S_ISDIR(opened.st_mode)
        or (opened.st_dev, opened.st_ino) != (named.st_dev, named.st_ino)
    ):
        raise ValueError("snapshot directory binding changed")


def _identity(metadata: os.stat_result) -> tuple[int, ...]:
    return (
        metadata.st_dev, metadata.st_ino, metadata.st_mode, metadata.st_size,
        metadata.st_mtime_ns, metadata.st_ctime_ns,
    )


def _copy_tree(
    source: int,
    destination: int,
    expected: dict[tuple[str, ...], _StagedObject],
    prefix: tuple[str, ...],
) -> None:
    before = os.fstat(source)
    for name in sorted(os.listdir(source)):
        metadata = os.stat(name, dir_fd=source, follow_symlinks=False)
        if stat.S_ISDIR(metadata.st_mode):
            os.mkdir(name, mode=0o700, dir_fd=destination)
            with _directory_at(source, name) as child:
                with _directory_at(destination, name) as copied:
                    _copy_tree(child, copied, expected, (*prefix, name))
                    os.fsync(copied)
                    expected[(*prefix, name)] = _StagedObject(_published_identity(os.fstat(copied)))
        elif stat.S_ISREG(metadata.st_mode):
            expected[(*prefix, name)] = _copy_file(source, name, destination, name)
        else:
            raise ValueError("snapshot source contains a non-regular entry")
    if _identity(before) != _identity(os.fstat(source)):
        raise ValueError("snapshot source directory changed")


def _copy_file(source: int, name: str, destination: int, target: str) -> _StagedObject:
    descriptor = os.open(name, _READ | os.O_NONBLOCK, dir_fd=source)
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("snapshot source must be regular")
        output = os.open(target, _CREATE, mode=0o600, dir_fd=destination)
        try:
            digest = sha256()
            while chunk := os.read(descriptor, 64 * 1024):
                digest.update(chunk)
                _write_all(output, chunk)
            after = os.fstat(descriptor)
            named = os.stat(name, dir_fd=source, follow_symlinks=False)
            if _identity(before) != _identity(after) or _identity(after) != _identity(named):
                raise ValueError("snapshot source changed while copied")
            os.fsync(output)
            if _identity(os.fstat(output)) != _identity(os.stat(target, dir_fd=destination, follow_symlinks=False)):
                raise ValueError("snapshot staged file changed")
            return _StagedObject(_published_identity(os.fstat(output)), digest.hexdigest())
        finally:
            os.close(output)
    finally:
        os.close(descriptor)


def _write_all(descriptor: int, data: bytes) -> None:
    remaining = memoryview(data)
    while remaining:
        written = os.write(descriptor, remaining)
        if written <= 0:
            raise OSError("snapshot write did not progress")
        remaining = remaining[written:]


def _published_identity(metadata: os.stat_result) -> tuple[int, ...]:
    # Rename changes ctime, but not inode/type/contents. Content digests are
    # checked separately; directory contents are matched against the manifest.
    return _identity(metadata)[:-1]


def _verify_staged_tree(
    parent: int,
    name: str,
    expected: dict[tuple[str, ...], _StagedObject],
    prefix: tuple[str, ...],
) -> None:
    record = expected[prefix]
    named = os.stat(name, dir_fd=parent, follow_symlinks=False)
    if _published_identity(named) != record.identity:
        raise ValueError("snapshot publication object changed")
    if record.digest is None:
        with _directory_at(parent, name) as directory:
            children = {key[len(prefix)] for key in expected if len(key) == len(prefix) + 1 and key[:len(prefix)] == prefix}
            if set(os.listdir(directory)) != children:
                raise ValueError("snapshot publication directory changed")
            for child in sorted(children):
                _verify_staged_tree(directory, child, expected, (*prefix, child))
    else:
        descriptor = os.open(name, _READ | os.O_NONBLOCK, dir_fd=parent)
        try:
            before = os.fstat(descriptor)
            if _published_identity(before) != record.identity:
                raise ValueError("snapshot publication file changed")
            digest = sha256()
            while chunk := os.read(descriptor, 64 * 1024):
                digest.update(chunk)
            after = os.fstat(descriptor)
            named = os.stat(name, dir_fd=parent, follow_symlinks=False)
            if _identity(before) != _identity(after) or _identity(after) != _identity(named) or digest.hexdigest() != record.digest:
                raise ValueError("snapshot publication contents changed")
        finally:
            os.close(descriptor)


def _rename_exclusive(source: int, name: str, destination: int, target: str) -> None:
    """Use native no-replace rename; never fall back to overwriting rename.

    Darwin: xnu bsd/sys/stdio.h RENAME_EXCL (0x4).
    Linux: include/uapi/linux/fs.h RENAME_NOREPLACE (1).
    """
    library = ctypes.CDLL(None, use_errno=True)
    symbol, flag = ("renameatx_np", 4) if sys.platform == "darwin" else ("renameat2", 1)
    if sys.platform not in {"darwin", "linux"} or not hasattr(library, symbol):
        raise OSError(errno.ENOTSUP, "exclusive snapshot publication is unsupported")
    rename = getattr(library, symbol)
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(source, os.fsencode(name), destination, os.fsencode(target), flag) != 0:
        raise OSError(ctypes.get_errno(), "exclusive snapshot publication failed")


__all__ = ["publish_compatibility_snapshot"]
