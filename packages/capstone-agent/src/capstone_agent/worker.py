"""Application-neutral worker loop over the existing Kernel runner."""

from __future__ import annotations

import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import BinaryIO, Protocol

from capability_agent.application.runner import ApplicationRequest

from capstone_agent.protocol import MAX_FRAME_BYTES, Frame, ProtocolError


class _IncrementalApplication(Protocol):
    def run_stream(self, request: ApplicationRequest, instructions: object) -> object: ...


@dataclass(frozen=True, slots=True)
class PreparedWorker:
    application: _IncrementalApplication
    run_id: str
    evidence_reader: Callable[[str], object | None]


def serve_application(
    factory: Callable[[Mapping[str, object], Callable[[Mapping[str, object]], None]], PreparedWorker],
    *, input_stream: BinaryIO | None = None, output_stream: BinaryIO | None = None,
) -> None:
    """Run one selected application and keep its admitted evidence readable."""

    source = input_stream or sys.stdin.buffer
    target = output_stream or sys.stdout.buffer
    raw_open = source.readline(MAX_FRAME_BYTES + 1)
    opening = Frame.from_line(raw_open, expected_sequence=1)
    if opening.kind != "open":
        raise ProtocolError("worker must open a registered application first")
    application_id = opening.payload.get("application_id")
    if not isinstance(application_id, str) or not application_id:
        raise ProtocolError("application ID is invalid")
    sequence = 0
    expected_input = 2
    admitted: set[str] = set()

    def emit(kind: str, payload: dict[str, object]) -> None:
        nonlocal sequence
        sequence += 1
        target.write(Frame(opening.session_id, sequence, kind, payload).to_line())
        target.flush()

    def observe(event: Mapping[str, object]) -> None:
        if event.get("type") == "application_turn_completed":
            result_refs = event.get("result_refs", [])
            evidence_refs = event.get("evidence_refs", [])
            if isinstance(result_refs, list) and isinstance(evidence_refs, list):
                admitted.update(ref for ref in (*result_refs, *evidence_refs) if isinstance(ref, str))
            emit("answer_committed", {
                "ordinal": event.get("ordinal"),
                "turn_id": event.get("turn_id"),
                "answer_output": event.get("answer_output"),
                "answer_ref": event.get("answer_ref"),
                "result_refs": result_refs,
                "evidence_refs": evidence_refs,
            })
        else:
            emit("progress", {
                "event": str(event.get("type", "progress")),
                "message": str(event.get("message", "")),
            })

    def next_frame() -> Frame | None:
        nonlocal expected_input
        raw = source.readline(MAX_FRAME_BYTES + 1)
        if not raw:
            return None
        frame = Frame.from_line(raw, expected_sequence=expected_input)
        expected_input += 1
        if frame.session_id != opening.session_id:
            raise ProtocolError("worker session identity changed")
        return frame

    try:
        prepared = factory(opening.payload, observe)
        if not isinstance(prepared.run_id, str) or not prepared.run_id:
            raise ValueError("prepared run ID is invalid")
        emit("ready", {"run_id": prepared.run_id})

        def read_evidence(frame: Frame) -> None:
            reference = frame.payload.get("ref")
            value = (
                prepared.evidence_reader(reference)
                if isinstance(reference, str) and reference in admitted
                else None
            )
            emit("evidence_result", {"ref": reference, "value": value})

        def instructions():
            while frame := next_frame():
                if frame.kind == "turn":
                    instruction = frame.payload.get("instruction")
                    if not isinstance(instruction, str) or not instruction.strip():
                        raise ProtocolError("turn instruction is invalid")
                    yield instruction
                elif frame.kind == "evidence":
                    read_evidence(frame)
                elif frame.kind == "close":
                    return
                else:
                    raise ProtocolError("worker control message is invalid")
            raise ProtocolError("worker session closed before finalization")

        outcome = prepared.application.run_stream(
            ApplicationRequest(application_id, (), prepared.run_id),
            instructions(),
        )
        if getattr(outcome, "status", None) != "completed":
            raise RuntimeError("application did not complete")
        emit("completed", {"run_id": prepared.run_id, "result": getattr(outcome, "rendered", None)})
        while frame := next_frame():
            if frame.kind != "evidence":
                raise ProtocolError("completed worker accepts only evidence reads")
            read_evidence(frame)
    except Exception:
        try:
            emit("failed", {"code": "application_worker_failed"})
        except Exception:
            pass
