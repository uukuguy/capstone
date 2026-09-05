"""Allowlisted, digest-verified access to trajectory artifacts."""

from __future__ import annotations

import errno
import os
import stat
import tempfile
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import BinaryIO

from grid_agent.trajectory.projection_models import ArtifactIndex


_MEDIA_TYPES = {
    ".json": "application/json; charset=utf-8",
    ".markdown": "text/markdown; charset=utf-8",
    ".md": "text/markdown; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
}
MAX_DOWNLOAD_BYTES = 256 * 1024 * 1024


class ArtifactAccessError(RuntimeError):
    """Raised when an artifact cannot be safely served from a run."""


class ArtifactTooLarge(ArtifactAccessError):
    """A download exceeds the per-response temporary snapshot limit."""


@dataclass(frozen=True, slots=True)
class ArtifactResponse:
    """A freshly verified artifact suitable for a fixed read-only response."""

    content: bytes
    media_type: str
    filename: str
    sha256: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class ArtifactSnapshot:
    """Verified download bytes; the response owns closing the temporary file."""

    file: BinaryIO
    metadata: ArtifactResponse


class ArtifactGateway:
    """Resolve only indexed artifact references and reverify them on every open."""

    def __init__(self, run_root: Path, artifact_index: ArtifactIndex) -> None:
        self.run_root = Path(run_root)
        self.artifact_index = artifact_index

    def open(self, artifact_ref: str, *, max_bytes: int | None = None) -> ArtifactResponse:
        """Return a regular, in-run file whose current bytes match its index digest."""
        if max_bytes is not None and not 1 <= max_bytes <= 131072:
            raise ArtifactAccessError("invalid preview size")
        return self._read(artifact_ref, max_bytes=max_bytes)

    def snapshot(self, artifact_ref: str) -> ArtifactSnapshot:
        """Verify into an anonymous disk file before publishing download headers."""
        target = tempfile.TemporaryFile(mode="w+b")
        try:
            metadata = self._read(artifact_ref, sink=target)
            target.seek(0)
            return ArtifactSnapshot(file=target, metadata=metadata)
        except BaseException:
            target.close()
            raise

    def _read(
        self, artifact_ref: str, *, max_bytes: int | None = None, sink: BinaryIO | None = None
    ) -> ArtifactResponse:
        _validate_reference(artifact_ref)
        record = self.artifact_index.records.get(artifact_ref)
        if record is None:
            raise ArtifactAccessError("artifact is not registered")

        try:
            root = self.run_root.resolve(strict=True)
        except OSError as exc:
            raise ArtifactAccessError("artifact is not a safe run path") from exc
        if not root.is_dir():
            raise ArtifactAccessError("artifact is not a safe run path")

        relative_path = _safe_relative_path(record.relative_path)
        media_type = media_type_for(Path(relative_path.name))
        try:
            descriptor = _open_nofollow(root, relative_path)
        except OSError as exc:
            if exc.errno == errno.ELOOP:
                raise ArtifactAccessError("artifact is not a safe run path") from exc
            raise ArtifactAccessError("artifact is not a regular file") from exc
        try:
            file_stat = os.fstat(descriptor)
            if not stat.S_ISREG(file_stat.st_mode):
                raise ArtifactAccessError("artifact is not a regular file")
            if sink is not None and file_stat.st_size > MAX_DOWNLOAD_BYTES:
                raise ArtifactTooLarge("artifact exceeds download limit")
            with os.fdopen(descriptor, "rb", closefd=True) as artifact_file:
                descriptor = -1
                digest = sha256()
                retained = bytearray()
                total = 0
                while chunk := artifact_file.read(65536):
                    total += len(chunk)
                    if total > file_stat.st_size:
                        raise ArtifactAccessError("artifact integrity mismatch")
                    digest.update(chunk)
                    if sink is not None:
                        sink.write(chunk)
                    elif max_bytes is None:
                        retained.extend(chunk)
                    elif len(retained) < max_bytes:
                        retained.extend(chunk[:max_bytes - len(retained)])
                final_stat = os.fstat(artifact_file.fileno())
        except OSError as exc:
            raise ArtifactAccessError("artifact is not a regular file") from exc
        finally:
            if descriptor >= 0:
                os.close(descriptor)
        if (
            file_stat.st_size != total
            or file_stat.st_mtime_ns != final_stat.st_mtime_ns
            or file_stat.st_ctime_ns != final_stat.st_ctime_ns
        ):
            raise ArtifactAccessError("artifact integrity mismatch")
        if digest.hexdigest() != record.sha256:
            raise ArtifactAccessError("artifact integrity mismatch")

        return ArtifactResponse(
            content=bytes(retained),
            media_type=media_type,
            filename=relative_path.name,
            sha256=record.sha256,
            size_bytes=total,
        )


def media_type_for(path: Path) -> str:
    """Return one of the fixed non-executable media types for an artifact file."""
    media_type = _MEDIA_TYPES.get(path.suffix.lower())
    if media_type is None:
        raise ArtifactAccessError("artifact media type is not allowed")
    return media_type


def _validate_reference(artifact_ref: str) -> None:
    if not isinstance(artifact_ref, str):
        raise ArtifactAccessError("invalid artifact reference")
    if "%2f" in artifact_ref.lower() or "%5c" in artifact_ref.lower():
        raise ArtifactAccessError("invalid artifact reference")


def _safe_relative_path(value: str) -> PurePosixPath:
    if not isinstance(value, str) or "\\" in value:
        raise ArtifactAccessError("artifact is not a safe run path")
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise ArtifactAccessError("artifact is not a safe run path")
    return path


def _open_nofollow(root: Path, relative_path: PurePosixPath) -> int:
    """Open an indexed file through descriptor-relative no-follow traversal."""
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY | nofollow)
    try:
        for part in relative_path.parts[:-1]:
            next_directory = os.open(
                part,
                os.O_RDONLY | os.O_DIRECTORY | nofollow,
                dir_fd=directory,
            )
            os.close(directory)
            directory = next_directory
        return os.open(relative_path.parts[-1], os.O_RDONLY | nofollow, dir_fd=directory)
    finally:
        os.close(directory)


__all__ = ["ArtifactAccessError", "ArtifactGateway", "ArtifactResponse", "media_type_for"]
