"""Capstone-aware boundary over replaceable agent runtime clients.

The public Thread protocol never receives native Pi or DSH frames directly.
This module keeps the runtime seam small: a selected runtime emits bounded,
typed events and returns one answer; Harness/Thread persistence can attach
identities and event sequence numbers around that seam.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from .thread_service import AttemptClaim, ThreadExecutionService
from .turn_router import DecisionUnavailable, TurnPlan, TurnRouter, routing_input_for_claim


RuntimeEventSink = Callable[[dict[str, object]], None]
AttemptAdmission = Callable[
    [AttemptClaim, str, tuple[str, ...], tuple[str, ...], tuple[Mapping[str, object], ...]],
    "AdmittedAttemptAnswer",
]


@dataclass(frozen=True, slots=True)
class AdmittedAttemptAnswer:
    """Trusted application decision; native runtime references are not admission."""

    answer: str
    mode: str
    assurance: str
    result_refs: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    diagnostic_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.answer, str) or not self.answer.strip() or len(self.answer) > 64_000:
            raise ValueError("admitted answer is invalid")
        if (self.mode, self.assurance) not in {
            ("authority_backed", "lineage_verified"),
            ("offline_information", "deterministic_information"),
            ("offline_information", "guide_access_verified"),
            ("limited", "limited"),
        }:
            raise ValueError("answer admission assurance is invalid")
        for name in ("result_refs", "evidence_refs"):
            refs = getattr(self, name)
            if not isinstance(refs, tuple) or len(refs) > 128 or any(
                not isinstance(ref, str) or not ref or len(ref) > 512 for ref in refs
            ) or len(set(refs)) != len(refs):
                raise ValueError("admitted references are invalid")
        if not isinstance(self.diagnostic_codes, tuple) or len(self.diagnostic_codes) > 64 or any(
            not isinstance(code, str) or not code or len(code) > 256
            for code in self.diagnostic_codes
        ) or len(set(self.diagnostic_codes)) != len(self.diagnostic_codes):
            raise ValueError("admission diagnostic codes are invalid")
        if self.mode == "authority_backed" and not self.evidence_refs:
            raise ValueError("authority-backed admission requires evidence")
        if self.mode == "offline_information" and (self.result_refs or self.evidence_refs):
            raise ValueError("offline admission must not create run evidence")


class HarnessRuntimeUnavailable(RuntimeError):
    """The requested replaceable runtime is not installed or enabled."""


@dataclass(frozen=True, slots=True)
class HarnessAttemptResult:
    status: str
    answer: str | None
    error_code: str | None
    result_refs: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    admission: Mapping[str, object] | None = None


class PiPromptSession(Protocol):
    def start(self) -> None: ...

    def prompt_and_wait(
        self,
        question: str,
        *,
        on_semantic_event: Callable[[Mapping[str, object]], None],
        correlation_id: str | None,
        on_heartbeat: Callable[[], None],
    ) -> str: ...

    def stop(self) -> None: ...


class HarnessRuntime(Protocol):
    def start(self) -> None: ...

    def prompt(
        self, question: str, *, on_event: RuntimeEventSink,
        correlation_id: str | None = None,
        on_heartbeat: Callable[[], None] | None = None,
    ) -> str: ...

    def stop(self) -> None: ...


_EVENT_TYPES = {
    "text_delta": ("assistant_text_delta", "public"),
    "message_update": ("assistant_message_update", "public"),
    "message_end": ("assistant_message_end", "public"),
    "tool_execution_start": ("tool_started", "public"),
    "tool_execution_end": ("tool_completed", "public"),
    "tool_result": ("tool_completed", "public"),
    "agent_end": ("runtime_completed", "public"),
    "application_turn_completed": ("runtime_completed", "public"),
    "auto_retry_start": ("runtime_retry_started", "diagnostic"),
    "auto_retry_end": ("runtime_retry_completed", "diagnostic"),
    "prompt_ack": ("runtime_prompt_ack", "diagnostic"),
    "response": ("runtime_response", "diagnostic"),
}


def normalize_runtime_event(
    event: Mapping[str, object], *, runtime_mode: str,
) -> dict[str, object]:
    """Map one native runtime event to a bounded Harness event document."""

    native_type = event.get("type")
    if not isinstance(native_type, str) or not native_type:
        native_type = "unknown"
    event_type, visibility = _EVENT_TYPES.get(native_type, ("runtime_event", "diagnostic"))
    payload: dict[str, object]
    if event_type == "assistant_text_delta":
        text = event.get("text")
        payload = {"text": text[:16_384]} if isinstance(text, str) else {}
    elif event_type in {"tool_started", "tool_completed"}:
        payload = _tool_payload(event)
    elif event_type == "runtime_event":
        payload = {"native_type": native_type}
    else:
        payload = _small_runtime_payload(event)
    return {
        "event_type": event_type,
        "runtime_mode": runtime_mode,
        "visibility": visibility,
        "payload": payload,
    }


def _tool_payload(event: Mapping[str, object]) -> dict[str, object]:
    payload: dict[str, object] = {}
    for source, target in (
        ("toolCallId", "tool_call_id"), ("tool_call_id", "tool_call_id"),
        ("toolName", "tool_name"), ("tool_name", "tool_name"),
    ):
        value = event.get(source)
        if isinstance(value, str) and value and target not in payload:
            payload[target] = value[:256]
    details = _tool_details(event)
    ok = event.get("ok", details.get("ok"))
    if isinstance(ok, bool):
        payload["ok"] = ok
    for source, target in (
        ("capability", "capability"),
        ("projector_id", "projector_id"),
        ("result_kind", "result_kind"),
    ):
        value = event.get(source, details.get(source))
        if isinstance(value, str) and value:
            payload[target] = value[:512]
    capability_key = event.get("capability_key", details.get("capability_key"))
    if isinstance(capability_key, Mapping):
        for source, target in (
            ("binding_id", "binding_id"), ("bindingId", "binding_id"),
            ("capability_id", "capability_id"), ("capabilityId", "capability_id"),
        ):
            value = capability_key.get(source)
            if isinstance(value, str) and value and target not in payload:
                payload[target] = value[:256]
    refs = event.get("evidence_refs", details.get("evidence_refs"))
    if isinstance(refs, (list, tuple)):
        bounded = [ref[:512] for ref in refs if isinstance(ref, str) and ref][:128]
        if bounded:
            payload["evidence_refs"] = bounded
    result_refs = event.get("result_refs", details.get("result_refs"))
    if isinstance(result_refs, (list, tuple)):
        bounded_results = [
            ref[:512] for ref in result_refs if isinstance(ref, str) and ref
        ][:128]
        if bounded_results:
            payload["result_refs"] = bounded_results
    result_ref = event.get("result_ref", details.get("result_ref"))
    if isinstance(result_ref, str) and result_ref and "result_refs" not in payload:
        payload["result_refs"] = [result_ref[:512]]
    return payload


def _tool_details(event: Mapping[str, object]) -> Mapping[str, object]:
    result = event.get("result")
    if isinstance(result, Mapping):
        details = result.get("details")
        if isinstance(details, Mapping):
            return details
    details = event.get("details")
    return details if isinstance(details, Mapping) else {}


def _small_runtime_payload(event: Mapping[str, object]) -> dict[str, object]:
    allowed = {
        "command": str, "success": bool, "ok": bool, "attempt": int,
        "maxAttempts": int, "delayMs": int, "stop_status": str,
    }
    return {
        key: value
        for key, expected in allowed.items()
        if isinstance((value := event.get(key)), expected)
    }


class HarnessPiClient:
    """Adapt an injected Pi-compatible session to the Harness event seam."""

    runtime_name = "pi"

    def __init__(
        self,
        session: PiPromptSession,
        *,
        runtime_mode: str = "capstone",
        admission: AttemptAdmission | None = None,
    ) -> None:
        if runtime_mode not in {"capstone", "pi_reference"}:
            raise ValueError("Pi runtime mode is invalid")
        self._session = session
        self.runtime_mode = runtime_mode
        self._admission = admission

    def admit_attempt(
        self,
        claim: AttemptClaim,
        answer: str,
        result_refs: tuple[str, ...],
        evidence_refs: tuple[str, ...],
        tool_events: tuple[Mapping[str, object], ...],
    ) -> AdmittedAttemptAnswer | None:
        if self._admission is None:
            return None
        return self._admission(
            claim, answer, result_refs, evidence_refs, tool_events,
        )

    def start(self) -> None:
        self._session.start()

    def prompt(
        self, question: str, *, on_event: RuntimeEventSink,
        correlation_id: str | None = None,
        on_heartbeat: Callable[[], None] | None = None,
    ) -> str:
        def emit(native: Mapping[str, object]) -> None:
            on_event(normalize_runtime_event(native, runtime_mode=self.runtime_mode))

        return self._session.prompt_and_wait(
            question,
            on_semantic_event=emit,
            correlation_id=correlation_id,
            on_heartbeat=on_heartbeat or (lambda: None),
        )

    def stop(self) -> None:
        self._session.stop()


class HarnessDSHClient:
    """Reserved DSH adapter; no DSH runtime is enabled in this milestone."""

    runtime_name = "dsh"
    runtime_mode = "dsh_reference"

    def start(self) -> None:
        raise HarnessRuntimeUnavailable("DSH Harness runtime is not installed")

    def prompt(
        self, question: str, *, on_event: RuntimeEventSink,
        correlation_id: str | None = None,
        on_heartbeat: Callable[[], None] | None = None,
    ) -> str:
        del question, on_event, correlation_id, on_heartbeat
        raise HarnessRuntimeUnavailable("DSH Harness runtime is not installed")

    def stop(self) -> None:
        return None


class HarnessAttemptRunner:
    """Run one claimed Attempt and commit only a terminal, bounded outcome."""

    def __init__(
        self, service: ThreadExecutionService, runtime: HarnessRuntime,
        *, lease_seconds: int = 30, turn_router: TurnRouter | None = None,
    ) -> None:
        if lease_seconds < 1:
            raise ValueError("attempt worker lease is invalid")
        self._service = service
        self._runtime = runtime
        self._lease_seconds = lease_seconds
        self._turn_router = turn_router
        self._tools_observed = False
        self._result_refs: list[str] = []
        self._evidence_refs: list[str] = []
        self._tool_events: list[Mapping[str, object]] = []

    def run(self, claim: AttemptClaim) -> HarnessAttemptResult:
        self._tools_observed = False
        self._result_refs.clear()
        self._evidence_refs.clear()
        self._tool_events.clear()
        plan: TurnPlan | None = None
        try:
            if self._turn_router is not None and claim.kind in {
                "send_auto", "send_ordinary", "send_professional",
            }:
                try:
                    plan = self._turn_router.plan(routing_input_for_claim(claim))
                except DecisionUnavailable as error:
                    self._finish_failed(claim, "decision_unavailable")
                    return HarnessAttemptResult("failed", None, str(error) or "decision_unavailable")
                self._persist_plan(claim, plan)
            self._runtime.start()
            answer = self._runtime.prompt(
                claim.instruction,
                correlation_id=claim.attempt.attempt_id,
                on_event=lambda event: self._persist_event(claim, event),
                on_heartbeat=lambda: self._renew_lease(claim),
            )
            if self._service.cancel_requested(claim):
                raise _AttemptCancelled
            if not isinstance(answer, str) or not answer.strip() or len(answer) > 64_000:
                raise TypeError("runtime answer is invalid")
            candidate = None
            admit = getattr(self._runtime, "admit_attempt", None)
            if callable(admit):
                try:
                    candidate = admit(
                        claim, answer, tuple(self._result_refs),
                        tuple(self._evidence_refs), tuple(self._tool_events),
                    )
                except Exception:
                    raise _AttemptAdmissionError("answer_admission_failed") from None
            if candidate is not None and not isinstance(candidate, AdmittedAttemptAnswer):
                raise _AttemptAdmissionError("answer_admission_invalid")
            if candidate is not None and (
                not set(candidate.result_refs).issubset(self._result_refs)
                or not set(candidate.evidence_refs).issubset(self._evidence_refs)
            ):
                raise _AttemptAdmissionError("answer_admission_invalid")
            professional_route = plan is not None and plan.route == "professional"
            if candidate is None and (
                professional_route
                or (plan is None and claim.kind not in {"send_auto", "send_ordinary"})
                or self._tools_observed
            ):
                raise _AttemptAdmissionError("answer_admission_unavailable")
            result_refs = () if candidate is None else candidate.result_refs
            evidence_refs = () if candidate is None else candidate.evidence_refs
            admitted_answer = answer if candidate is None else candidate.answer
            admission: dict[str, object] | None = None if candidate is None else {
                "mode": candidate.mode, "assurance": candidate.assurance,
            }
            if candidate is not None and candidate.diagnostic_codes:
                if admission is None:
                    raise _AttemptAdmissionError("answer_admission_invalid")
                admission["diagnostic_codes"] = list(candidate.diagnostic_codes)
            terminal_payload: dict[str, object] = {
                "answer": admitted_answer,
                "result_refs": list(result_refs),
                "evidence_refs": list(evidence_refs),
            }
            if admission is not None:
                terminal_payload["admission"] = admission
            self._service.finish_attempt(
                claim, phase="completed", payload=terminal_payload,
            )
            return HarnessAttemptResult(
                "completed", admitted_answer, None, result_refs, evidence_refs, admission,
            )
        except _AttemptAdmissionError as error:
            self._finish_failed(claim, error.code)
            return HarnessAttemptResult("failed", None, error.code)
        except _AttemptCancelled:
            self._finish_cancelled(claim)
            return HarnessAttemptResult("cancelled", None, "attempt_cancelled")
        except Exception:
            self._finish_failed(claim, "runtime_failed")
            return HarnessAttemptResult("failed", None, "runtime_failed")
        finally:
            try:
                self._runtime.stop()
            except Exception:
                pass

    def _persist_plan(self, claim: AttemptClaim, plan: TurnPlan) -> None:
        self._service.append_runtime_event(
            claim,
            event_type="turn_plan_created",
            payload=plan.to_payload(),
            visibility="public",
        )
        self._service.append_runtime_event(
            claim,
            event_type="turn_route_fallback" if plan.fallback else "turn_route_selected",
            payload={
                "route": plan.route,
                "source": plan.source,
                "plan_revision": plan.plan_revision,
                "fallback": plan.fallback,
            },
            visibility="public" if not plan.fallback else "diagnostic",
        )

    def _persist_event(self, claim: AttemptClaim, event: Mapping[str, object]) -> None:
        event_type = event.get("event_type")
        runtime_mode = event.get("runtime_mode")
        visibility = event.get("visibility", "diagnostic")
        payload = event.get("payload")
        if not isinstance(event_type, str) or not isinstance(runtime_mode, str):
            raise ValueError("runtime event is invalid")
        if not isinstance(payload, Mapping):
            raise ValueError("runtime event payload is invalid")
        if event_type in {"tool_started", "tool_completed"}:
            self._tools_observed = True
        _extend_refs(self._result_refs, payload.get("result_refs"))
        _extend_refs(self._evidence_refs, payload.get("evidence_refs"))
        if event_type == "tool_completed":
            self._tool_events.append(dict(payload))
        self._service.append_runtime_event(
            claim,
            event_type=event_type,
            payload={"runtime_mode": runtime_mode, **dict(payload)},
            visibility=visibility if isinstance(visibility, str) else "diagnostic",
        )

    def _renew_lease(self, claim: AttemptClaim) -> None:
        if not self._service.renew_attempt(claim, self._lease_seconds):
            raise RuntimeError("attempt lease is unavailable")
        if self._service.cancel_requested(claim):
            raise _AttemptCancelled

    def _finish_cancelled(self, claim: AttemptClaim) -> None:
        try:
            self._service.finish_attempt(
                claim, phase="cancelled", payload={"error_code": "attempt_cancelled"},
            )
        except Exception as exc:
            raise RuntimeError("attempt terminal persistence failed") from exc

    def _finish_failed(self, claim: AttemptClaim, error_code: str) -> None:
        try:
            self._service.finish_attempt(
                claim, phase="failed", payload={"error_code": error_code},
            )
        except Exception as exc:
            # The durable service remains the source of truth. If its terminal
            # write failed, do not claim that the Attempt was safely finished.
            raise RuntimeError("attempt terminal persistence failed") from exc


class _AttemptAdmissionError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class _AttemptCancelled(RuntimeError):
    """The user requested cancellation at a safe runtime checkpoint."""


def _extend_refs(target: list[str], value: object) -> None:
    if not isinstance(value, (list, tuple)):
        return
    for reference in value:
        if isinstance(reference, str) and reference and reference not in target:
            target.append(reference[:512])
            if len(target) >= 128:
                return


__all__ = [
    "HarnessAttemptResult", "HarnessAttemptRunner", "HarnessDSHClient", "HarnessPiClient", "HarnessRuntimeUnavailable",
    "PiPromptSession", "normalize_runtime_event",
    "HarnessRuntime",
    "AttemptAdmission",
    "AdmittedAttemptAnswer",
]
