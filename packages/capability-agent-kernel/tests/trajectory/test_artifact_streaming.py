"""Regression coverage for descriptor-bound streaming artifact verification."""

from __future__ import annotations

import os
import stat
import tracemalloc
from hashlib import sha256
from pathlib import Path

import pytest

import capability_agent.trajectory.artifacts as artifact_module
from capability_agent.trajectory.artifacts import (
    ArtifactIntegrityError,
    ImmutableArtifactRegistry,
)


_CHUNK_SIZE = 1024 * 1024


def _artifact_path(tmp_path: Path) -> Path:
    return tmp_path / "run" / "requests" / "request-1" / "input.json"


def _write_incrementally(path: Path, size_bytes: int) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    digest = sha256()
    remaining = size_bytes
    with path.open("wb") as stream:
        while remaining:
            chunk = bytes(min(_CHUNK_SIZE, remaining))
            stream.write(chunk)
            digest.update(chunk)
            remaining -= len(chunk)
    return digest.hexdigest()


@pytest.mark.parametrize("size_bytes", [8 * _CHUNK_SIZE, 64 * _CHUNK_SIZE])
def test_register_and_verify_large_artifacts_stream_without_full_read_helper(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, size_bytes: int
) -> None:
    path = _artifact_path(tmp_path)
    expected_digest = _write_incrementally(path, size_bytes)
    registry = ImmutableArtifactRegistry(tmp_path / "run")
    reads: list[tuple[int, int]] = []
    real_read = os.read

    def recording_read(descriptor: int, requested: int) -> bytes:
        value = real_read(descriptor, requested)
        reads.append((requested, len(value)))
        return value

    def forbidden_full_read(_: int) -> bytes:
        raise AssertionError("register_existing/verify must not use _read_descriptor")

    monkeypatch.setattr(artifact_module.os, "read", recording_read)
    monkeypatch.setattr(artifact_module, "_read_descriptor", forbidden_full_read)
    tracemalloc.start()
    before_current, _ = tracemalloc.get_traced_memory()
    pointer = registry.register_existing("request-input", "request-1", path)
    registry.verify(pointer)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert pointer.sha256 == expected_digest
    assert pointer.size_bytes == size_bytes
    assert reads
    assert max(request for request, _ in reads) <= _CHUNK_SIZE
    assert sum(actual for _, actual in reads) == size_bytes * 3
    # Three streaming verification passes retain at most a bounded read buffer.
    assert peak - before_current <= 5 * _CHUNK_SIZE


@pytest.mark.parametrize("mutation", ["equal_size", "append", "truncate"])
def test_verify_rejects_content_or_size_mutated_while_streaming(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    path = _artifact_path(tmp_path)
    _write_incrementally(path, 2 * _CHUNK_SIZE)
    registry = ImmutableArtifactRegistry(tmp_path / "run")
    pointer = registry.register_existing("request-input", "request-1", path)
    real_read = os.read
    changed = False

    def mutate_after_first_read(descriptor: int, requested: int) -> bytes:
        nonlocal changed
        value = real_read(descriptor, requested)
        if value and not changed:
            changed = True
            if mutation == "equal_size":
                with path.open("r+b") as stream:
                    stream.seek(0)
                    stream.write(b"x")
            elif mutation == "append":
                with path.open("ab") as stream:
                    stream.write(b"x")
            else:
                with path.open("r+b") as stream:
                    stream.truncate(_CHUNK_SIZE)
        return value

    monkeypatch.setattr(artifact_module.os, "read", mutate_after_first_read)
    with pytest.raises(ArtifactIntegrityError, match="changed during verification"):
        registry.verify(pointer)


def test_verify_rechecks_identity_after_named_binding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _artifact_path(tmp_path)
    _write_incrementally(path, _CHUNK_SIZE)
    registry = ImmutableArtifactRegistry(tmp_path / "run")
    pointer = registry.register_existing("request-input", "request-1", path)
    real_binding = registry._verify_named_binding

    def mutate_after_binding(*args: object, **kwargs: object) -> None:
        real_binding(*args, **kwargs)  # type: ignore[arg-type]
        with path.open("r+b") as stream:
            stream.seek(0)
            stream.write(b"x")

    monkeypatch.setattr(registry, "_verify_named_binding", mutate_after_binding)
    with pytest.raises(ArtifactIntegrityError, match="changed during verification"):
        registry.verify(pointer)


def test_verify_rechecks_identity_after_eof_probe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _artifact_path(tmp_path)
    _write_incrementally(path, _CHUNK_SIZE)
    registry = ImmutableArtifactRegistry(tmp_path / "run")
    pointer = registry.register_existing("request-input", "request-1", path)
    real_read = os.read
    changed = False

    def mutate_after_eof(descriptor: int, requested: int) -> bytes:
        nonlocal changed
        value = real_read(descriptor, requested)
        if not value and not changed:
            changed = True
            with path.open("r+b") as stream:
                stream.seek(0)
                stream.write(b"x")
        return value

    monkeypatch.setattr(artifact_module.os, "read", mutate_after_eof)
    with pytest.raises(ArtifactIntegrityError, match="changed during verification"):
        registry.verify(pointer)


@pytest.mark.parametrize("replacement", ["root", "parent", "leaf"])
def test_verify_rejects_named_binding_replacement_after_leaf_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, replacement: str
) -> None:
    path = _artifact_path(tmp_path)
    _write_incrementally(path, _CHUNK_SIZE)
    registry = ImmutableArtifactRegistry(tmp_path / "run")
    pointer = registry.register_existing("request-input", "request-1", path)
    real_binding = registry._verify_named_binding

    def replace_before_binding(*args: object, **kwargs: object) -> None:
        run_root = tmp_path / "run"
        if replacement == "root":
            moved = tmp_path / "old-run"
            run_root.rename(moved)
            _write_incrementally(run_root / "requests" / "request-1" / "input.json", _CHUNK_SIZE)
        elif replacement == "parent":
            parent = path.parent
            moved = tmp_path / "old-parent"
            parent.rename(moved)
            _write_incrementally(path, _CHUNK_SIZE)
        else:
            moved = path.with_name("old-input.json")
            path.rename(moved)
            _write_incrementally(path, _CHUNK_SIZE)
        real_binding(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(registry, "_verify_named_binding", replace_before_binding)
    with pytest.raises(ArtifactIntegrityError, match="changed during verification"):
        registry.verify(pointer)


def test_leaf_open_requests_nonblocking_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _artifact_path(tmp_path)
    _write_incrementally(path, 1)
    registry = ImmutableArtifactRegistry(tmp_path / "run")
    real_open = os.open

    def checking_open(
        name: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        if os.fspath(name) == "input.json":
            assert flags & os.O_NONBLOCK
        return real_open(name, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(artifact_module.os, "open", checking_open)
    registry.register_existing("request-input", "request-1", path)


@pytest.mark.skipif(
    not artifact_module._FILE_OPEN_FLAGS & os.O_NONBLOCK,
    reason="legacy blocking leaf open is guarded by test_leaf_open_requests_nonblocking_mode",
)
def test_fifo_is_opened_nonblocking_then_rejected_as_nonregular(tmp_path: Path) -> None:
    path = _artifact_path(tmp_path)
    path.parent.mkdir(parents=True)
    os.mkfifo(path)
    registry = ImmutableArtifactRegistry(tmp_path / "run")

    with pytest.raises(ArtifactIntegrityError, match="not regular"):
        registry.register_existing("request-input", "request-1", path)


def test_leaf_fstat_failure_closes_the_opened_descriptor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _artifact_path(tmp_path)
    _write_incrementally(path, 1)
    registry = ImmutableArtifactRegistry(tmp_path / "run")
    real_open = os.open
    real_fstat = os.fstat
    real_close = os.close
    leaf_descriptor: int | None = None
    closed: list[int] = []

    def recording_open(
        name: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        nonlocal leaf_descriptor
        descriptor = real_open(name, flags, mode, dir_fd=dir_fd)
        if os.fspath(name) == "input.json":
            leaf_descriptor = descriptor
        return descriptor

    def failing_fstat(descriptor: int) -> os.stat_result:
        if descriptor == leaf_descriptor:
            raise OSError("injected fstat failure")
        return real_fstat(descriptor)

    def recording_close(descriptor: int) -> None:
        closed.append(descriptor)
        real_close(descriptor)

    monkeypatch.setattr(artifact_module.os, "open", recording_open)
    monkeypatch.setattr(artifact_module.os, "fstat", failing_fstat)
    monkeypatch.setattr(artifact_module.os, "close", recording_close)
    with pytest.raises(ArtifactIntegrityError, match="could not be opened safely"):
        registry.register_existing("request-input", "request-1", path)
    assert leaf_descriptor is not None
    assert leaf_descriptor in closed


def test_leaf_fstat_failure_is_not_masked_by_close_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _artifact_path(tmp_path)
    _write_incrementally(path, 1)
    registry = ImmutableArtifactRegistry(tmp_path / "run")
    real_open = os.open
    real_fstat = os.fstat
    real_close = os.close
    leaf_descriptor: int | None = None

    def recording_open(
        name: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        nonlocal leaf_descriptor
        descriptor = real_open(name, flags, mode, dir_fd=dir_fd)
        if os.fspath(name) == "input.json":
            leaf_descriptor = descriptor
        return descriptor

    def failing_fstat(descriptor: int) -> os.stat_result:
        if descriptor == leaf_descriptor:
            raise OSError("injected fstat failure")
        return real_fstat(descriptor)

    def failing_close(descriptor: int) -> None:
        real_close(descriptor)
        if descriptor == leaf_descriptor:
            raise OSError("injected close failure")

    monkeypatch.setattr(artifact_module.os, "open", recording_open)
    monkeypatch.setattr(artifact_module.os, "fstat", failing_fstat)
    monkeypatch.setattr(artifact_module.os, "close", failing_close)
    with pytest.raises(ArtifactIntegrityError, match="could not be opened safely"):
        registry.register_existing("request-input", "request-1", path)


def test_named_binding_error_is_not_masked_by_rebound_close_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _artifact_path(tmp_path)
    _write_incrementally(path, 1)
    registry = ImmutableArtifactRegistry(tmp_path / "run")
    pointer = registry.register_existing("request-input", "request-1", path)
    real_open = os.open
    real_close = os.close
    leaf_descriptors: list[int] = []

    def recording_open(
        name: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        descriptor = real_open(name, flags, mode, dir_fd=dir_fd)
        if os.fspath(name) == "input.json":
            leaf_descriptors.append(descriptor)
        return descriptor

    def failing_rebound_close(descriptor: int) -> None:
        real_close(descriptor)
        if len(leaf_descriptors) > 1 and descriptor == leaf_descriptors[-1]:
            raise OSError("injected rebound close failure")

    monkeypatch.setattr(artifact_module.os, "open", recording_open)
    monkeypatch.setattr(artifact_module.os, "close", failing_rebound_close)
    real_binding = registry._verify_named_binding

    def replace_then_bind(*args: object, **kwargs: object) -> None:
        moved = path.with_name("old-input.json")
        path.rename(moved)
        _write_incrementally(path, 1)
        real_binding(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(registry, "_verify_named_binding", replace_then_bind)
    with pytest.raises(ArtifactIntegrityError, match="changed during verification"):
        registry.verify(pointer)


def test_read_failure_is_normalized_to_integrity_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _artifact_path(tmp_path)
    _write_incrementally(path, 1)
    registry = ImmutableArtifactRegistry(tmp_path / "run")

    def failing_read(_: int, __: int) -> bytes:
        raise OSError("injected read failure")

    monkeypatch.setattr(artifact_module.os, "read", failing_read)
    with pytest.raises(ArtifactIntegrityError, match="could not be read"):
        registry.register_existing("request-input", "request-1", path)


def test_verify_normalizes_leaf_close_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _artifact_path(tmp_path)
    _write_incrementally(path, 1)
    registry = ImmutableArtifactRegistry(tmp_path / "run")
    pointer = registry.register_existing("request-input", "request-1", path)
    real_open = os.open
    real_close = os.close
    leaf_descriptors: set[int] = set()

    def recording_open(
        name: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        descriptor = real_open(name, flags, mode, dir_fd=dir_fd)
        if os.fspath(name) == "input.json":
            leaf_descriptors.add(descriptor)
        return descriptor

    def failing_leaf_close(descriptor: int) -> None:
        real_close(descriptor)
        if descriptor in leaf_descriptors:
            raise OSError("injected leaf close failure")

    monkeypatch.setattr(artifact_module.os, "open", recording_open)
    monkeypatch.setattr(artifact_module.os, "close", failing_leaf_close)
    with pytest.raises(ArtifactIntegrityError, match="could not be verified safely"):
        registry.verify(pointer)


def test_parent_close_failure_does_not_mask_primary_integrity_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _artifact_path(tmp_path)
    _write_incrementally(path, 1)
    registry = ImmutableArtifactRegistry(tmp_path / "run")
    real_close = os.close
    raised = False
    active = False

    def failing_one_close(descriptor: int) -> None:
        nonlocal raised
        real_close(descriptor)
        if active and not raised:
            raised = True
            raise OSError("injected directory close failure")

    monkeypatch.setattr(artifact_module.os, "close", failing_one_close)
    with pytest.raises(ArtifactIntegrityError, match="primary integrity failure"):
        with registry._open_parent(path, create=False):
            active = True
            raise ArtifactIntegrityError("primary integrity failure")


def test_stable_preopen_tamper_keeps_specific_pointer_mismatch_errors(tmp_path: Path) -> None:
    path = _artifact_path(tmp_path)
    _write_incrementally(path, 2)
    registry = ImmutableArtifactRegistry(tmp_path / "run")
    pointer = registry.register_existing("request-input", "request-1", path)
    path.write_bytes(b"xyz")
    with pytest.raises(ArtifactIntegrityError, match="size does not match"):
        registry.verify(pointer)
    path.write_bytes(b"zz")
    with pytest.raises(ArtifactIntegrityError, match="digest does not match"):
        registry.verify(pointer)
