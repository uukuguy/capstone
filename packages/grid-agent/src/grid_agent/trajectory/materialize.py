"""Disposable canonical JSON cache for projected trajectories."""

from __future__ import annotations

import os
import hashlib
import json
import secrets
import stat
from dataclasses import dataclass
from pathlib import Path

from capability_agent.trajectory.canonical import canonical_json_bytes
from grid_agent.trajectory.projection_models import ProjectedRun


PROJECTION_SCHEMA = "trajectory-projection/3.0"


@dataclass(frozen=True, slots=True)
class MaterializedPaths:
    cache_root: Path
    projected_run: Path
    agent: Path
    business: Path
    context: Path
    artifacts: Path

    @property
    def all_paths(self) -> tuple[Path, ...]:
        return (self.projected_run, self.agent, self.business, self.context, self.artifacts)


class ProjectionMaterializer:
    def __init__(self, cache_root: Path) -> None:
        self.cache_root = Path(cache_root)

    def _paths(self, analysis_id: str, fingerprint: str) -> MaterializedPaths:
        _validate_cache_segment("analysis_id", analysis_id)
        _validate_cache_segment("source_fingerprint", fingerprint)
        root = self.cache_root / analysis_id / fingerprint / PROJECTION_SCHEMA
        return MaterializedPaths(root, root / "projected-run.json", root / "agent.json", root / "business.json", root / "context.json", root / "artifacts.json")

    def write(self, projected_run: ProjectedRun, source_fingerprint: str, *, cache_identity: str | None = None) -> MaterializedPaths:
        if projected_run.source_fingerprint != source_fingerprint:
            raise ValueError("projected run fingerprint does not match cache key")
        paths = self._paths(projected_run.analysis_id, cache_identity or source_fingerprint)
        projected_payload = projected_run.model_dump(mode="json")
        payloads = {
            paths.projected_run: {"schema": PROJECTION_SCHEMA, "identity": cache_identity or source_fingerprint, "analysis_id": projected_run.analysis_id, "payload": projected_payload, "payload_sha256": hashlib.sha256(canonical_json_bytes(projected_payload)).hexdigest()},
            paths.agent: projected_run.agent.model_dump(mode="json"),
            paths.business: projected_run.business.model_dump(mode="json"),
            paths.context: projected_run.context.model_dump(mode="json"),
            paths.artifacts: projected_run.artifacts.model_dump(mode="json"),
        }
        directory = self._open_leaf(projected_run.analysis_id, cache_identity or source_fingerprint, create=True)
        try:
            for path, value in payloads.items():
                _atomic_write_at(directory, path.name, canonical_json_bytes(value))
        finally:
            os.close(directory)
        return paths

    def load_if_current(self, analysis_id: str, source_fingerprint: str, *, cache_identity: str | None = None) -> ProjectedRun | None:
        expected = cache_identity or source_fingerprint
        path = self._paths(analysis_id, expected).projected_run
        try:
            directory = self._open_leaf(analysis_id, expected, create=False)
            try:
                envelope = json.loads(_read_at(directory, path.name))
            finally:
                os.close(directory)
            if not isinstance(envelope, dict) or envelope.get("schema") != PROJECTION_SCHEMA or envelope.get("identity") != expected or envelope.get("analysis_id") != analysis_id:
                return None
            payload = envelope.get("payload")
            if not isinstance(payload, dict) or envelope.get("payload_sha256") != hashlib.sha256(canonical_json_bytes(payload)).hexdigest():
                return None
            projected = ProjectedRun.model_validate(payload)
        except (OSError, ValueError):
            return None
        return projected if projected.analysis_id == analysis_id and projected.source_fingerprint == source_fingerprint else None

    def _open_leaf(self, analysis_id: str, fingerprint: str, *, create: bool) -> int:
        flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)
        directory = self._open_cache_root(create, flags)
        try:
            for segment in (analysis_id, fingerprint, *PROJECTION_SCHEMA.split("/")):
                if create:
                    try:
                        os.mkdir(segment, dir_fd=directory)
                    except FileExistsError:
                        pass
                child = os.open(segment, flags, dir_fd=directory)
                os.close(directory)
                directory = child
            return directory
        except BaseException:
            os.close(directory)
            raise

    def _open_cache_root(self, create: bool, flags: int) -> int:
        root = self.cache_root.absolute()
        directory = os.open("/", flags)
        try:
            for component in root.parts[1:]:
                if create:
                    try:
                        os.mkdir(component, dir_fd=directory)
                    except FileExistsError:
                        pass
                child = os.open(component, flags, dir_fd=directory)
                os.close(directory)
                directory = child
            return directory
        except BaseException:
            os.close(directory)
            raise


def _read_at(directory: int, name: str) -> bytes:
    descriptor = os.open(name, os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0), dir_fd=directory)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise OSError("trajectory cache is not a regular file")
        with os.fdopen(descriptor, "rb", closefd=True) as stream:
            descriptor = -1
            return stream.read()
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _atomic_write_at(directory: int, name: str, value: bytes) -> None:
    temporary = f".{name}.{secrets.token_hex(8)}"
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=directory)
    try:
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            descriptor = -1
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.rename(temporary, name, src_dir_fd=directory, dst_dir_fd=directory)
        os.fsync(directory)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            os.unlink(temporary, dir_fd=directory)
        except FileNotFoundError:
            pass


def _validate_cache_segment(name: str, value: str) -> None:
    if (
        not isinstance(value, str)
        or not value
        or value in {".", ".."}
        or Path(value).is_absolute()
        or "/" in value
        or "\\" in value
    ):
        raise ValueError(f"{name} must be a safe cache path segment")


__all__ = ["MaterializedPaths", "PROJECTION_SCHEMA", "ProjectionMaterializer"]
