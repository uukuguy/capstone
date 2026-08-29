"""Portable, exclusive application run workspaces."""

from __future__ import annotations

import os
import secrets
import stat
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType

from capability_agent.application.context_models import PORTABLE_ID_PATTERN


class WorkspaceError(RuntimeError):
    """Raised when a run workspace cannot be safely created or addressed."""


@dataclass(frozen=True, slots=True)
class ApplicationWorkspace:
    """Filesystem paths for one application run and its declared bindings."""

    run_id: str
    root: Path
    core_path: Path
    context_snapshot_path: Path
    context_events_path: Path
    events_path: Path
    artifacts_path: Path
    domains_path: Path
    turns_path: Path
    output_path: Path
    domain_roots: Mapping[str, Path]

    @classmethod
    def create(
        cls,
        root: Path,
        run_id: str | None = None,
        binding_ids: Iterable[str] = (),
    ) -> "ApplicationWorkspace":
        """Create an exclusive ``runs/<run_id>`` tree.

        The caller supplies the binding IDs declared by the application
        profile.  No domain directory is inferred or created from any other
        input.
        """

        resolved_run_id = _generated_run_id() if run_id is None else run_id
        _require_portable_id(resolved_run_id, label="run identifier")
        try:
            declared = tuple(binding_ids)
        except TypeError:
            raise WorkspaceError("binding identifiers must be iterable") from None
        for binding_id in declared:
            _require_portable_id(binding_id, label="binding identifier")
        if len(set(declared)) != len(declared):
            raise WorkspaceError("binding identifiers must be unique")
        declared = tuple(sorted(declared))

        base = _absolute_path(root)
        _reject_symlink_ancestors(base, label="workspace root")
        _reject_symlink(base, label="workspace root")
        if base.exists() and not base.is_dir():
            raise WorkspaceError("workspace root is not a directory")
        try:
            base.mkdir(mode=0o700, parents=True, exist_ok=True)
        except OSError:
            raise WorkspaceError("workspace root could not be created") from None
        _reject_symlink(base, label="workspace root")

        run_root = base / resolved_run_id
        try:
            os.mkdir(run_root, 0o700)
        except FileExistsError:
            raise WorkspaceError("workspace already exists") from None
        except OSError:
            raise WorkspaceError("workspace could not be created") from None
        _reject_symlink(run_root, label="workspace root")

        core = run_root / "core"
        domains = run_root / "domains"
        turns = run_root / "turns"
        output = run_root / "output"
        for directory in (core, domains, turns, output):
            _mkdir(directory)

        domain_roots: dict[str, Path] = {}
        for binding_id in declared:
            domain_root = domains / binding_id
            domain_roots[binding_id] = domain_root
            _mkdir(domain_root)
            for child in ("runtime", "artifacts", "tool-results"):
                _mkdir(domain_root / child)

        context_snapshot = core / "context.json"
        context_events = core / "context-events.jsonl"
        events = core / "events.jsonl"
        artifacts = core / "artifacts.jsonl"
        for file_path in (context_snapshot, context_events, events, artifacts):
            _create_empty_file(file_path)

        return cls(
            run_id=resolved_run_id,
            root=run_root,
            core_path=core,
            context_snapshot_path=context_snapshot,
            context_events_path=context_events,
            events_path=events,
            artifacts_path=artifacts,
            domains_path=domains,
            turns_path=turns,
            output_path=output,
            domain_roots=MappingProxyType(domain_roots),
        )

    @property
    def root_path(self) -> Path:
        """Compatibility spelling for callers that use ``root_path``."""

        return self.root

    @property
    def core_dir(self) -> Path:
        return self.core_path

    @property
    def domains_dir(self) -> Path:
        return self.domains_path

    @property
    def turns_dir(self) -> Path:
        return self.turns_path

    @property
    def output_dir(self) -> Path:
        return self.output_path

    def domain_path(self, binding_id: str) -> Path:
        """Return a declared binding's root, rejecting undeclared IDs."""

        _require_portable_id(binding_id, label="binding identifier")
        try:
            return self.domain_roots[binding_id]
        except KeyError:
            raise WorkspaceError("binding is not declared for this workspace") from None

    def domain_runtime_path(self, binding_id: str) -> Path:
        return self.domain_path(binding_id) / "runtime"

    def domain_artifacts_path(self, binding_id: str) -> Path:
        return self.domain_path(binding_id) / "artifacts"

    def domain_tool_results_path(self, binding_id: str) -> Path:
        return self.domain_path(binding_id) / "tool-results"


def _generated_run_id() -> str:
    instant = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ").lower()
    return f"run-{instant}-{secrets.token_hex(4)}"


def _absolute_path(path: Path) -> Path:
    try:
        candidate = Path(os.path.abspath(os.fspath(path)))
    except (TypeError, ValueError):
        raise WorkspaceError("workspace root is invalid") from None
    if not candidate.parts:
        raise WorkspaceError("workspace root is invalid")
    return candidate


def _require_portable_id(value: object, *, label: str) -> None:
    if not isinstance(value, str) or not PORTABLE_ID_PATTERN.fullmatch(value):
        raise WorkspaceError(f"{label} must be a portable identifier")


def _reject_symlink(path: Path, *, label: str) -> None:
    try:
        if path.is_symlink():
            raise WorkspaceError(f"{label} cannot be a symlink")
        if path.exists() and not path.is_dir():
            raise WorkspaceError(f"{label} is not a directory")
    except OSError:
        raise WorkspaceError(f"{label} cannot be inspected") from None


def _reject_symlink_ancestors(path: Path, *, label: str) -> None:
    """Reject a symlink in every existing component of a root path."""

    current = Path(path.anchor)
    for component in path.parts[1:]:
        current /= component
        try:
            metadata = current.lstat()
        except FileNotFoundError:
            # Components below the first missing component will be created by
            # this function and therefore cannot already contain a symlink.
            break
        except OSError:
            raise WorkspaceError(f"{label} cannot be inspected") from None
        if os.path.islink(current):
            raise WorkspaceError(f"{label} cannot contain a symlink")
        if not stat.S_ISDIR(metadata.st_mode):
            raise WorkspaceError(f"{label} is not a directory")


def _mkdir(path: Path) -> None:
    try:
        os.mkdir(path, 0o700)
    except FileExistsError:
        _reject_symlink(path, label="workspace directory")
        return
    except OSError:
        raise WorkspaceError("workspace directory could not be created") from None
    _reject_symlink(path, label="workspace directory")
    _fsync_directory(path.parent)


def _create_empty_file(path: Path) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    no_follow = getattr(os, "O_NOFOLLOW", 0)
    descriptor: int | None = None
    try:
        descriptor = os.open(path, flags | no_follow, 0o600)
        os.fsync(descriptor)
    except FileExistsError:
        raise WorkspaceError("workspace file already exists") from None
    except OSError:
        raise WorkspaceError("workspace file could not be created") from None
    finally:
        if descriptor is not None:
            os.close(descriptor)
    _fsync_directory(path.parent)


def _fsync_directory(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


__all__ = ["ApplicationWorkspace", "WorkspaceError"]
