import fcntl
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4


class RunWorkspaceLeaseError(RuntimeError):
    """The operator-visible run id is already owned by another live process."""


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
        resolved_run_id = run_id or f"run-{uuid4().hex}"
        root_path = root / resolved_run_id
        lease_directory = root.parent / ".grid-agent/run-leases"
        lease_directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        lease_directory.chmod(0o700)
        lease_name = sha256(resolved_run_id.encode("utf-8")).hexdigest() + ".lock"
        lease_stream = (lease_directory / lease_name).open("a+b")
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
            root_path.mkdir(parents=True, exist_ok=True)
        except Exception:
            fcntl.flock(lease_stream.fileno(), fcntl.LOCK_UN)
            lease_stream.close()
            raise
        tool_results_path = root_path / "tool-results"
        pi_path = root_path / "pi"
        evidence_path = root_path / "evidence"
        bin_path = root_path / "bin"

        for path in (tool_results_path, evidence_path, pi_path, bin_path):
            path.mkdir(parents=True, exist_ok=True)

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
