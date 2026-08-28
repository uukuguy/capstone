import fcntl
import os
import stat
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

from grid_agent.contracts import validate_question_id


class RunWorkspaceLeaseError(RuntimeError):
    """The operator-visible run id is already owned by another live process."""


class RunWorkspaceExistsError(RuntimeError):
    """A completed or abandoned invocation already owns this run id."""


class RunWorkspacePathError(RuntimeError):
    """The requested workspace path is not a trusted regular directory."""


def _open_directory(path: Path, *, label: str) -> int:
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    try:
        return os.open(path, flags)
    except OSError as exc:
        raise RunWorkspacePathError(f"{label} is not a trusted directory: {path}") from exc


def _verify_named_directory_binding(
    parent_fd: int,
    name: str,
    descriptor: int,
    *,
    label: str,
) -> None:
    opened = os.fstat(descriptor)
    try:
        named = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except OSError as exc:
        raise RunWorkspacePathError(
            f"{label} named binding changed while it was opened: {name}"
        ) from exc
    if (
        not stat.S_ISDIR(opened.st_mode)
        or not stat.S_ISDIR(named.st_mode)
        or (opened.st_dev, opened.st_ino) != (named.st_dev, named.st_ino)
    ):
        raise RunWorkspacePathError(
            f"{label} named binding changed while it was opened: {name}"
        )


def _open_or_create_directory_at(
    parent_fd: int,
    name: str,
    *,
    label: str,
) -> int:
    try:
        os.mkdir(name, mode=0o700, dir_fd=parent_fd)
    except FileExistsError:
        pass
    except OSError as exc:
        raise RunWorkspacePathError(
            f"{label} cannot be created safely: {name}"
        ) from exc
    try:
        descriptor = os.open(
            name,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
            dir_fd=parent_fd,
        )
    except OSError as exc:
        raise RunWorkspacePathError(
            f"{label} is not a trusted directory: {name}"
        ) from exc
    try:
        _verify_named_directory_binding(
            parent_fd,
            name,
            descriptor,
            label=label,
        )
        os.fchmod(descriptor, 0o700)
    except Exception:
        os.close(descriptor)
        raise
    return descriptor


def _open_run_lease_directory(project_root: Path) -> int:
    project_fd = _open_directory(project_root, label="project root")
    internal_fd: int | None = None
    lease_directory_fd: int | None = None
    try:
        internal_fd = _open_or_create_directory_at(
            project_fd,
            ".grid-agent",
            label="internal state directory",
        )
        lease_directory_fd = _open_or_create_directory_at(
            internal_fd,
            "run-leases",
            label="run lease directory",
        )
        _verify_named_directory_binding(
            project_fd,
            ".grid-agent",
            internal_fd,
            label="internal state directory",
        )
        _verify_named_directory_binding(
            internal_fd,
            "run-leases",
            lease_directory_fd,
            label="run lease directory",
        )
        return lease_directory_fd
    except Exception:
        if lease_directory_fd is not None:
            os.close(lease_directory_fd)
        raise
    finally:
        if internal_fd is not None:
            os.close(internal_fd)
        os.close(project_fd)


def _existing_workspace_error(root_fd: int, run_id: str) -> RuntimeError:
    try:
        existing = os.stat(run_id, dir_fd=root_fd, follow_symlinks=False)
    except OSError:
        return RunWorkspacePathError(
            f"run workspace cannot be inspected safely: {run_id}"
        )
    if stat.S_ISDIR(existing.st_mode):
        return RunWorkspaceExistsError(f"run workspace already exists: {run_id}")
    return RunWorkspacePathError(f"run workspace is not a trusted directory: {run_id}")


@dataclass(frozen=True, slots=True)
class RunWorkspace:
    run_id: str
    root_path: Path
    input_path: Path
    run_path: Path
    events_path: Path
    answer_path: Path
    pi_path: Path
    evidence_path: Path
    tool_results_path: Path
    bin_path: Path
    _lease_stream: BinaryIO = field(repr=False, compare=False)

    @classmethod
    def create(cls, root: Path, run_id: str | None = None) -> "RunWorkspace":
        resolved_run_id = validate_question_id(run_id or f"run-{uuid4().hex}")
        root_path = root / resolved_run_id
        lease_directory_fd = _open_run_lease_directory(root.parent)
        lease_name = sha256(resolved_run_id.encode("utf-8")).hexdigest() + ".lock"
        try:
            lease_fd = os.open(
                lease_name,
                os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC,
                0o600,
                dir_fd=lease_directory_fd,
            )
        finally:
            os.close(lease_directory_fd)
        lease_stream = os.fdopen(lease_fd, "a+b")
        try:
            fcntl.flock(
                lease_stream.fileno(),
                fcntl.LOCK_EX | fcntl.LOCK_NB,
            )
        except BlockingIOError:
            lease_stream.close()
            raise RunWorkspaceLeaseError(
                f"run workspace is already active: {resolved_run_id}"
            ) from None

        try:
            root.mkdir(parents=True, exist_ok=True, mode=0o700)
            root_fd = _open_directory(root, label="runs root")
            try:
                try:
                    os.mkdir(resolved_run_id, mode=0o700, dir_fd=root_fd)
                except FileExistsError:
                    raise _existing_workspace_error(root_fd, resolved_run_id)
                run_fd = os.open(
                    resolved_run_id,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                    dir_fd=root_fd,
                )
                try:
                    for name in ("tool-results", "evidence", "pi", "bin"):
                        os.mkdir(name, mode=0o700, dir_fd=run_fd)
                finally:
                    os.close(run_fd)
            finally:
                os.close(root_fd)
        except Exception:
            fcntl.flock(lease_stream.fileno(), fcntl.LOCK_UN)
            lease_stream.close()
            raise
        tool_results_path = root_path / "tool-results"
        pi_path = root_path / "pi"
        evidence_path = root_path / "evidence"
        bin_path = root_path / "bin"

        return cls(
            run_id=resolved_run_id,
            root_path=root_path,
            input_path=root_path / "input.json",
            run_path=root_path / "run.json",
            events_path=root_path / "events.jsonl",
            answer_path=root_path / "answer.json",
            pi_path=pi_path,
            evidence_path=evidence_path,
            tool_results_path=tool_results_path,
            bin_path=bin_path,
            _lease_stream=lease_stream,
        )

    def close(self) -> None:
        if self._lease_stream.closed:
            return
        try:
            fcntl.flock(self._lease_stream.fileno(), fcntl.LOCK_UN)
        finally:
            self._lease_stream.close()
