"""Typed, provider-free checks for real Thread application projections."""

from __future__ import annotations

import json
import time
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from capstone_agent.thread_protocol import EventEnvelope, EventPage, ThreadSnapshot

from .catalog import ThreadCatalog
from .http_runner import ThreadResyncRequired
from .m5_contract import M5CheckResult


ROOT = Path(__file__).resolve().parents[2]
PANDAPOWER_CASE = ROOT / "validation" / "application" / "pandapower-scripted-task.json"
PYPSA_CASES = ROOT / "validation" / "pypsa-cases" / "cases.json"


class MatrixSession(Protocol):
    def create(self, model_id: str | None = None) -> ThreadSnapshot: ...
    def catalog(self) -> ThreadCatalog: ...
    def snapshot(self) -> ThreadSnapshot: ...
    def command(
        self, kind: str, payload: dict[str, Any], *,
        expected_event_seq: int | None = None,
        command_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> Any: ...
    def events(self, *, after: int = 0) -> EventPage: ...


def _event_payload(event: EventEnvelope) -> Mapping[str, Any]:
    return event.payload


def validate_attempt_projection(
    events: tuple[EventEnvelope, ...], *, attempt_id: str, route: str,
    implementation_family: str, authority_backed: bool,
    expected_thread_id: str | None = None, expected_run_id: str | None = None,
    expected_model_context_id: str | None = None,
) -> M5CheckResult:
    """Check one terminal Attempt without trusting model-authored text."""

    scoped = tuple(event for event in events if event.attempt_id == attempt_id)
    selected = [event for event in scoped if event.event_type in {"turn_route_selected", "turn_route_fallback"}]
    terminal = next((event for event in reversed(scoped) if event.event_type == "attempt_completed"), None)
    tools = [event for event in scoped if event.event_type == "tool_completed"]
    if not selected or _event_payload(selected[-1]).get("route") != route:
        return M5CheckResult("attempt.route", "failed", {"reason": "missing route selection", "attempt_id": attempt_id})
    if terminal is None:
        return M5CheckResult("attempt.terminal", "failed", {"reason": "missing attempt_completed", "attempt_id": attempt_id})
    payload = _event_payload(terminal)
    for event in scoped:
        if expected_thread_id is not None and event.thread_id != expected_thread_id:
            return M5CheckResult("attempt.identity", "failed", {"reason": "event thread identity mismatch", "attempt_id": attempt_id})
        if expected_run_id is not None and event.run_id != expected_run_id:
            return M5CheckResult("attempt.identity", "failed", {"reason": "event run identity mismatch", "attempt_id": attempt_id})
        if expected_model_context_id is not None and event.model_context_id != expected_model_context_id:
            return M5CheckResult("attempt.identity", "failed", {"reason": "event model context mismatch", "attempt_id": attempt_id})
    answer = payload.get("answer")
    refs = payload.get("result_refs")
    evidence = payload.get("evidence_refs")
    admission = payload.get("admission")
    if not isinstance(answer, str) or not answer.strip():
        return M5CheckResult("attempt.answer", "failed", {"reason": "empty answer", "attempt_id": attempt_id})
    if not isinstance(refs, list) or not all(isinstance(ref, str) and ref for ref in refs):
        return M5CheckResult("attempt.result_refs", "failed", {"reason": "invalid result refs", "attempt_id": attempt_id})
    if not isinstance(evidence, list) or not all(isinstance(ref, str) and ref for ref in evidence):
        return M5CheckResult("attempt.evidence_refs", "failed", {"reason": "invalid evidence refs", "attempt_id": attempt_id})
    if authority_backed and (not tools or not refs or not evidence or not isinstance(admission, dict) or admission.get("mode") != "authority_backed"):
        return M5CheckResult("attempt.admission", "failed", {
            "reason": "authority-backed attempt lacks tool, result, evidence, or admission", "attempt_id": attempt_id,
        })
    if not authority_backed and (refs or evidence):
        return M5CheckResult("attempt.offline_refs", "failed", {"reason": "ordinary answer emitted simulator refs", "attempt_id": attempt_id})
    observed_results = {
        ref for tool in tools for ref in _event_payload(tool).get("result_refs", [])
        if isinstance(ref, str) and ref
    }
    observed_evidence = {
        ref for tool in tools for ref in _event_payload(tool).get("evidence_refs", [])
        if isinstance(ref, str) and ref
    }
    if authority_backed and (
        not set(refs).issubset(observed_results)
        or not set(evidence).issubset(observed_evidence)
    ):
        return M5CheckResult("attempt.references", "failed", {"reason": "terminal references were not observed in current Attempt tools", "attempt_id": attempt_id})
    for tool in tools:
        tool_payload = _event_payload(tool)
        if not isinstance(tool_payload.get("binding_id"), str) or not tool_payload["binding_id"] or not isinstance(tool_payload.get("capability_id"), str) or not tool_payload["capability_id"]:
            return M5CheckResult("attempt.tool_source", "failed", {"reason": "tool source is not explicit", "attempt_id": attempt_id})
    started = next((event for event in scoped if event.event_type == "attempt_started"), None)
    if started is None:
        return M5CheckResult("attempt.duration", "failed", {"reason": "missing attempt_started", "attempt_id": attempt_id})
    try:
        duration_ms = int((datetime.fromisoformat(terminal.occurred_at.replace("Z", "+00:00")) - datetime.fromisoformat(started.occurred_at.replace("Z", "+00:00"))).total_seconds() * 1000)
    except ValueError:
        return M5CheckResult("attempt.duration", "failed", {"reason": "invalid event timestamps", "attempt_id": attempt_id})
    if duration_ms < 0:
        return M5CheckResult("attempt.duration", "failed", {"reason": "negative duration", "attempt_id": attempt_id})
    return M5CheckResult("attempt", "passed", {
        "attempt_id": attempt_id, "implementation_family": implementation_family,
        "tool_count": len(tools), "result_ref_count": len(refs), "evidence_ref_count": len(evidence), "duration_ms": duration_ms,
    })


def validate_ordinary_projection(events: tuple[EventEnvelope, ...], *, attempt_id: str) -> M5CheckResult:
    return validate_attempt_projection(
        events, attempt_id=attempt_id, route="ordinary", implementation_family="ordinary", authority_backed=False,
    )


def _registered_questions(application_id: str) -> tuple[tuple[str, str], ...]:
    if application_id == "pandapower-static-analysis":
        document = json.loads(PANDAPOWER_CASE.read_text(encoding="utf-8"))
        return tuple((item["id"], item["text"]) for item in document["questions"])
    if application_id == "pypsa-business-cases":
        document = json.loads(PYPSA_CASES.read_text(encoding="utf-8"))
        case = next(item for item in document["cases"] if item["status"] == "runnable")
        return ((case["id"], case["question"]),)
    raise ValueError(f"unsupported M5 application: {application_id}")


def _wait_attempt(session: MatrixSession, attempt_id: str, cursor: int, timeout_seconds: float) -> tuple[ThreadSnapshot, tuple[EventEnvelope, ...]]:
    deadline = time.monotonic() + timeout_seconds
    collected: list[EventEnvelope] = []
    while time.monotonic() < deadline:
        page = session.events(after=cursor)
        collected.extend(page.events)
        cursor = page.next_event_seq
        if any(event.attempt_id == attempt_id and event.event_type in {"attempt_completed", "attempt_failed", "attempt_cancelled", "attempt_interrupted"} for event in collected):
            return session.snapshot(), tuple(collected)
        time.sleep(0.05)
    raise TimeoutError(f"attempt {attempt_id} did not reach a terminal event")


def run_application_matrix(application_id: str, session: MatrixSession, *, timeout_seconds: float = 30.0) -> tuple[M5CheckResult, ...]:
    """Run only registered questions against a live provider-free application."""

    results: list[M5CheckResult] = []
    try:
        snapshot = session.create()
        catalog = session.catalog()
        family = snapshot.active_model_context.implementation_family
        family_models = [model for model in catalog.models if model.implementation_family == family]
        family_profiles = [profile for profile in catalog.profiles if family in profile.implementation_families]
        if not family_models or not family_profiles:
            results.append(M5CheckResult(
                "catalog", "failed",
                {"reason": "catalog does not expose the active implementation family", "implementation_family": family},
            ))
        else:
            results.append(M5CheckResult(
                "catalog", "passed",
                {"implementation_family": family, "model_count": len(family_models), "profile_count": len(family_profiles)},
            ))
        questions = _registered_questions(application_id)
        for question_id, text in questions:
            cursor = snapshot.last_event_seq
            receipt = session.command("send_professional", {"text": text}, expected_event_seq=cursor)
            target = getattr(receipt, "target", None)
            attempt_id = target.get("attempt_id") if isinstance(target, dict) else None
            if not isinstance(attempt_id, str):
                results.append(M5CheckResult(f"{question_id}.acceptance", "failed", {"reason": "receipt has no attempt target"}))
                continue
            snapshot, events = _wait_attempt(session, attempt_id, receipt.accepted_event_seq or cursor, timeout_seconds)
            results.append(validate_attempt_projection(
                events, attempt_id=attempt_id, route="professional",
                implementation_family=snapshot.active_model_context.implementation_family,
                authority_backed=True,
                expected_thread_id=snapshot.thread_id,
                expected_run_id=snapshot.run.run_id,
                expected_model_context_id=snapshot.active_model_context.id,
            ))
        snapshot = session.snapshot()
        cursor = snapshot.last_event_seq
        receipt = session.command("send_auto", {"text": "你好，请简单介绍你能做什么。"}, expected_event_seq=cursor)
        target = getattr(receipt, "target", None)
        attempt_id = target.get("attempt_id") if isinstance(target, dict) else None
        if isinstance(attempt_id, str):
            _, events = _wait_attempt(session, attempt_id, receipt.accepted_event_seq or cursor, timeout_seconds)
            results.append(validate_ordinary_projection(events, attempt_id=attempt_id))
        else:
            results.append(M5CheckResult("ordinary.acceptance", "failed", {"reason": "receipt has no attempt target"}))
        return tuple(results)
    except ThreadResyncRequired as error:
        return (M5CheckResult("matrix.recovery", "failed", {"reason": "resync required during matrix", "base_event_seq": error.snapshot.base_event_seq}),)
    except Exception as error:
        return (M5CheckResult("matrix.execution", "failed", {"reason": type(error).__name__}),)


__all__ = ["run_application_matrix", "validate_attempt_projection", "validate_ordinary_projection"]
