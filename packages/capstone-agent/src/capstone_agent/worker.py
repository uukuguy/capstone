"""Application-neutral worker loop over the existing Kernel runner."""

from __future__ import annotations

import json
import os
import sys
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import BinaryIO, Protocol

from capability_agent.application.runner import ApplicationRequest

from capstone_agent.protocol import MAX_FRAME_BYTES, Frame, ProtocolError
from capstone_agent.progress import render_progress, summarize_answer
from capstone_agent.network_view import normalize_network_view
from capstone_agent.network_diagram import normalize_network_projection


class _IncrementalApplication(Protocol):
    def run_stream(self, request: ApplicationRequest, instructions: Iterable[str]) -> object: ...


@dataclass(frozen=True, slots=True)
class PreparedWorker:
    application: _IncrementalApplication
    run_id: str
    evidence_reader: Callable[[str], object | None]
    network_reader: Callable[[int], Mapping[str, object] | None] | None = None


def read_verified_reference(prepared: object, reference: str) -> object | None:
    """Return one authority-verified, bounded document from this run."""

    bindings = getattr(prepared, "bindings", None)
    if not isinstance(bindings, Mapping):
        return None
    method_name = (
        "verify_evidence" if reference.startswith(("evidence:", "pypsa-evidence:"))
        else "verify_result" if reference.startswith(("result:", "pypsa-result:"))
        else None
    )
    if method_name is None:
        return None
    for binding in bindings.values():
        authority = getattr(getattr(binding, "runtime", None), "authority", None)
        verify = getattr(authority, method_name, None)
        if not callable(verify):
            continue
        try:
            verified = verify(reference)
        except Exception:
            continue
        if getattr(verified, "reference", None) != reference:
            continue
        document = getattr(verified, "document", None)
        try:
            encoded = json.dumps(document, ensure_ascii=False, allow_nan=False).encode("utf-8")
        except (TypeError, ValueError):
            return None
        if len(encoded) > 65_536:
            return {"reference": reference, "status": "bounded",
                    "size_bytes": len(encoded)}
        return document
    return None


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
    last_diagram_ref: str | None = None
    turn_started_at: dict[int, float] = {}
    step_link_enabled = os.environ.get("CAPSTONE_ENABLE_NETWORK_STEP_LINK", "true").strip().lower() not in {
        "0", "false", "no", "off",
    }

    def emit(kind: str, payload: dict[str, object]) -> None:
        nonlocal sequence
        encoded = Frame(opening.session_id, sequence + 1, kind, payload).to_line()
        sequence += 1
        target.write(encoded)
        target.flush()

    def observe(event: Mapping[str, object]) -> None:
        nonlocal last_diagram_ref
        if event.get("type") == "application_turn_completed":
            result_refs = event.get("result_refs", [])
            evidence_refs = event.get("evidence_refs", [])
            if isinstance(result_refs, list) and isinstance(evidence_refs, list):
                admitted.update(ref for ref in (*result_refs, *evidence_refs) if isinstance(ref, str))
            ordinal = event.get("ordinal")
            model_summary = event.get("answer_summary")
            answer_summary = (
                model_summary.strip()
                if isinstance(model_summary, str) and model_summary.strip()
                else summarize_answer(
                    event.get("answer_output"),
                    has_references=bool(result_refs or evidence_refs),
                )
            )
            answer_payload: dict[str, object] = {
                "ordinal": event.get("ordinal"),
                "turn_id": event.get("turn_id"),
                "answer_output": event.get("answer_output"),
                "answer_summary": answer_summary,
                "answer_ref": event.get("answer_ref"),
                "result_refs": result_refs,
                "evidence_refs": evidence_refs,
            }
            if type(ordinal) is int:
                started_at = turn_started_at.pop(ordinal, None)
                if started_at is not None:
                    answer_payload["duration_ms"] = max(
                        0, round((time.monotonic() - started_at) * 1000),
                    )
            emit("answer_committed", answer_payload)
            if step_link_enabled and prepared.network_reader is not None and type(ordinal) is int:
                try:
                    projection = prepared.network_reader(ordinal)
                    if projection is not None:
                        if projection.get("schema") == "capstone-network-view/2.0":
                            view = normalize_network_projection(
                                projection, admitted_refs=tuple(
                                    ref for ref in result_refs if isinstance(ref, str)
                                ) if isinstance(result_refs, list) else (),
                            )
                            diagram = view["diagram"]
                            if diagram["ref"] != last_diagram_ref:
                                emit("network_diagram", {"diagram": diagram})
                                last_diagram_ref = diagram["ref"]
                            emit("network_layer", {"ordinal": ordinal, "layer": view["layer"]})
                        else:
                            view = normalize_network_view(projection)
                            emit("network_view", {"ordinal": ordinal, "view": view})
                    else:
                        emit("network_view_unavailable", {"ordinal": ordinal})
                except Exception as exc:
                    print(
                        f"Network view unavailable for committed turn: "
                        f"{type(exc).__name__}: {exc}",
                        file=sys.stderr,
                    )
                    emit("network_view_unavailable", {"ordinal": ordinal})
            elif step_link_enabled and type(ordinal) is int:
                emit("network_view_unavailable", {"ordinal": ordinal})
        else:
            message = render_progress(event)
            if message:
                emit("progress", {
                    "event": str(event.get("type", "progress")),
                    "message": message,
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
            next_ordinal = 0
            while frame := next_frame():
                if frame.kind == "turn":
                    instruction = frame.payload.get("instruction")
                    if not isinstance(instruction, str) or not instruction.strip():
                        raise ProtocolError("turn instruction is invalid")
                    next_ordinal += 1
                    turn_started_at[next_ordinal] = time.monotonic()
                    yield instruction
                elif frame.kind == "evidence":
                    read_evidence(frame)
                elif frame.kind == "close":
                    return
                else:
                    raise ProtocolError("worker control message is invalid")
            raise ProtocolError("worker session closed before finalization")

        response_mode = (
            "answer_bundle"
            if opening.payload.get("mode") == "provider"
            else "text"
        )
        outcome = prepared.application.run_stream(
            ApplicationRequest(
                application_id,
                (),
                prepared.run_id,
                response_mode=response_mode,
            ),
            instructions(),
        )
        if getattr(outcome, "status", None) != "completed":
            raise RuntimeError("application did not complete")
        rendered = getattr(outcome, "rendered", None)
        if isinstance(rendered, str):
            rendered = json.loads(rendered)
        report_path = getattr(outcome, "report_path", None)
        completed = {"run_id": prepared.run_id, "result": rendered}
        if report_path is not None:
            completed["report_path"] = str(report_path)
        emit("completed", completed)
        while frame := next_frame():
            if frame.kind != "evidence":
                raise ProtocolError("completed worker accepts only evidence reads")
            read_evidence(frame)
    except Exception:
        try:
            emit("failed", {"code": "application_worker_failed"})
        except Exception:
            pass
