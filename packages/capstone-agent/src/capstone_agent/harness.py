"""Capstone-aware boundary over replaceable agent runtime clients.

The public Thread protocol never receives native Pi or DSH frames directly.
This module keeps the runtime seam small: a selected runtime emits bounded,
typed events and returns one answer; Harness/Thread persistence can attach
identities and event sequence numbers around that seam.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import json
from typing import Protocol, cast

from .attempt_lease import AttemptLeaseRenewal
from .progress import project_tool_failure
from .thread_service import AttemptClaim, ThreadExecutionService
from .thread_network import (
    ThreadNetworkProjectionProvider,
    ThreadNetworkRuntimeObserver,
    NetworkProjectionUnavailable,
    normalize_thread_network_projection,
)
from .turn_router import DecisionUnavailable, DefaultTurnRouter, TurnPlan, TurnRouter, routing_input_for_claim


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
    result_projections: tuple[Mapping[str, object], ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.answer, str) or not self.answer.strip() or len(self.answer) > 64_000:
            raise ValueError("admitted answer is invalid")
        if (self.mode, self.assurance) not in {
            ("authority_backed", "lineage_verified"),
            ("offline_information", "deterministic_information"),
            ("offline_information", "guide_access_verified"),
            ("offline_information", "general_knowledge"),
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
        if (
            not isinstance(self.result_projections, tuple)
            or len(self.result_projections) > 12
            or any(not isinstance(item, Mapping) for item in self.result_projections)
        ):
            raise ValueError("admitted result projections are invalid")
        try:
            encoded_projections = json.dumps(
                [dict(item) for item in self.result_projections],
                ensure_ascii=False, allow_nan=False, sort_keys=True,
            ).encode("utf-8")
        except (TypeError, ValueError):
            raise ValueError("admitted result projections are not JSON") from None
        if len(encoded_projections) > 64 * 1024:
            raise ValueError("admitted result projections are too large")
        if self.mode == "authority_backed" and not self.evidence_refs:
            raise ValueError("authority-backed admission requires evidence")
        if self.mode == "offline_information" and (self.result_refs or self.evidence_refs):
            raise ValueError("offline admission must not create run evidence")


class HarnessRuntimeUnavailable(RuntimeError):
    """The requested replaceable runtime is not installed or enabled."""


class HarnessRuntimeConfigurationError(RuntimeError):
    """Application runtime settings are invalid; prepared model resources remain valid."""


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


RuntimeFactory = Callable[[AttemptClaim], HarnessRuntime]


class HarnessRuntimeRegistry:
    """Application-owned registry for exact Harness runtime factories."""

    def __init__(
        self, factories: Mapping[str, RuntimeFactory] | None = None,
    ) -> None:
        self._factories: dict[str, RuntimeFactory] = {}
        if factories is not None:
            if not isinstance(factories, Mapping):
                raise TypeError("runtime factories must be a mapping")
            for runtime_name, factory in factories.items():
                self.register(runtime_name, factory)

    def register(self, runtime_name: str, factory: RuntimeFactory) -> None:
        if not isinstance(runtime_name, str) or not runtime_name.strip():
            raise ValueError("runtime name is invalid")
        if not callable(factory):
            raise TypeError("runtime factory is invalid")
        if runtime_name in self._factories:
            raise ValueError(f"duplicate runtime: {runtime_name}")
        self._factories[runtime_name] = factory

    def resolve(self, runtime_name: str) -> RuntimeFactory:
        if not isinstance(runtime_name, str) or not runtime_name.strip():
            raise ValueError("runtime name is invalid")
        try:
            return self._factories[runtime_name]
        except KeyError:
            raise KeyError(f"runtime is not registered: {runtime_name}") from None


_EVENT_TYPES = {
    "text_delta": ("assistant_process_delta", "diagnostic"),
    "assistant_process_delta": ("assistant_process_delta", "diagnostic"),
    "message_update": ("assistant_process_update", "diagnostic"),
    "message_end": ("assistant_process_end", "diagnostic"),
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
    if event_type == "assistant_process_delta":
        text = event.get("text")
        payload = {"text": text[:16_384]} if isinstance(text, str) else {}
    elif event_type in {"tool_started", "tool_completed"}:
        payload = _tool_payload(event)
    elif event_type == "runtime_event":
        payload = {"native_type": native_type}
    else:
        payload = _small_runtime_payload(event)
    sequence = event.get("trace_sequence")
    correlation = event.get("trace_correlation_id")
    if type(sequence) is int and sequence > 0 and isinstance(correlation, str) and 0 < len(correlation) <= 128:
        payload["trace_sequence"] = sequence
        payload["trace_correlation_id"] = correlation
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
    if ok is False:
        failure = project_tool_failure(event.get("error", details.get("error")))
        if failure:
            payload["failure"] = failure
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
    # Native Pi tools retain authority output in details.result. Preserve only
    # bounded references and identity, never the raw authority document.
    result = details.get("result")
    if ok is True and isinstance(result, Mapping):
        nested_refs = result.get("result_refs", ())
        raw_references = payload.get("result_refs")
        references = [ref for ref in raw_references if isinstance(ref, str)] if isinstance(raw_references, list) else []
        if isinstance(nested_refs, (list, tuple)):
            references.extend(ref for ref in nested_refs if isinstance(ref, str) and ref)
        if isinstance(result.get("result_ref"), str):
            references.append(result["result_ref"])
        if references:
            payload["result_refs"] = list(dict.fromkeys(ref[:512] for ref in references))[:128]
        for identity in (event, details, result):
            for source, target in (
                ("context_ref", "context_ref"), ("model_ref", "model_ref"),
                ("revision_ref", "model_revision"), ("model_revision", "model_revision"),
                ("model_id", "model_id"), ("model", "model_id"),
            ):
                if source not in identity:
                    continue
                value = identity[source]
                if not isinstance(value, str) or not 0 < len(value) <= 512:
                    raise ValueError("tool model identity is invalid")
                if target in payload and payload[target] != value:
                    raise ValueError("tool model identity is conflicting")
                payload[target] = value
    return payload


def _tool_details(event: Mapping[str, object]) -> Mapping[str, object]:
    if event.get("event") == "tool_result" and isinstance(event.get("capability"), str):
        # RPC canonicalization has already unwrapped native tool details.
        return event
    result = event.get("result")
    if isinstance(result, Mapping):
        details = result.get("details")
        if isinstance(details, Mapping):
            return details
    if event.get("type") == "tool_result" and isinstance(event.get("capability"), str):
        return event
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
        network_projection_provider: ThreadNetworkProjectionProvider | None = None,
        on_stop: Callable[[], None] | None = None,
    ) -> None:
        if runtime_mode not in {"capstone", "pi_reference"}:
            raise ValueError("Pi runtime mode is invalid")
        self._session = session
        self._on_stop = on_stop
        self.runtime_mode = runtime_mode
        self._admission = admission
        if network_projection_provider is not None and not isinstance(
            network_projection_provider, ThreadNetworkProjectionProvider,
        ):
            raise TypeError("network projection provider is invalid")
        self._network_projection_provider = network_projection_provider
        self.network_projection_failure_code = "projection_unavailable"

    @property
    def network_projection_enabled(self) -> bool:
        return self._network_projection_provider is not None

    def network_projection(
        self,
        claim: AttemptClaim,
        result_refs: tuple[str, ...],
        evidence_refs: tuple[str, ...],
        tool_events: tuple[Mapping[str, object], ...],
    ) -> dict[str, object] | None:
        provider = self._network_projection_provider
        self.network_projection_failure_code = "projection_unavailable"
        if provider is None:
            return None
        try:
            value = provider.project(claim, result_refs, evidence_refs, tool_events)
        except NetworkProjectionUnavailable as error:
            self.network_projection_failure_code = error.code
            return None
        except Exception:
            self.network_projection_failure_code = "projection_source_unavailable"
            return None
        normalized = normalize_thread_network_projection(
            value, claim, (*result_refs, *evidence_refs),
        )
        if normalized is None:
            self.network_projection_failure_code = "projection_invalid"
        return normalized

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

    def recover_after_failure(
        self, feedback: Mapping[str, object], *, on_event: RuntimeEventSink,
        correlation_id: str, on_heartbeat: Callable[[], None],
    ) -> str:
        recover = getattr(self._session, "recover_after_failure", None)
        if not callable(recover):
            raise HarnessRuntimeUnavailable("runtime recovery is unavailable")

        def emit(native: Mapping[str, object]) -> None:
            if isinstance(self._network_projection_provider, ThreadNetworkRuntimeObserver):
                self._network_projection_provider.observe_runtime_event(native)
            on_event(normalize_runtime_event(native, runtime_mode=self.runtime_mode))

        answer = recover(feedback, on_semantic_event=emit,
                         correlation_id=correlation_id, on_heartbeat=on_heartbeat)
        if not isinstance(answer, str):
            raise TypeError("recovery answer is invalid")
        return answer

    @property
    def recovery_available(self) -> bool:
        return callable(getattr(self._session, "recover_after_failure", None))

    def prompt(
        self, question: str, *, on_event: RuntimeEventSink,
        correlation_id: str | None = None,
        on_heartbeat: Callable[[], None] | None = None,
    ) -> str:
        def emit(native: Mapping[str, object]) -> None:
            if isinstance(self._network_projection_provider, ThreadNetworkRuntimeObserver):
                self._network_projection_provider.observe_runtime_event(native)
            on_event(normalize_runtime_event(native, runtime_mode=self.runtime_mode))

        return self._session.prompt_and_wait(
            question,
            on_semantic_event=emit,
            correlation_id=correlation_id,
            on_heartbeat=on_heartbeat or (lambda: None),
        )

    def stop(self) -> None:
        callback, self._on_stop = self._on_stop, None
        try:
            self._session.stop()
        finally:
            if callback is not None:
                callback()


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


class CapstoneHarness:
    """Public Harness facade for running one claimed Attempt."""

    @staticmethod
    def run_attempt(
        service: ThreadExecutionService,
        claim: AttemptClaim,
        runtime: HarnessRuntime,
    ) -> HarnessAttemptResult:
        return HarnessAttemptRunner(service, runtime).run(claim)


class HarnessAttemptRunner:
    """Run one claimed Attempt and commit only a terminal, bounded outcome."""

    def __init__(
        self, service: ThreadExecutionService, runtime: HarnessRuntime,
        *, lease_seconds: int = 30, turn_router: TurnRouter | None = None,
        lease: AttemptLeaseRenewal | None = None,
    ) -> None:
        if lease_seconds < 1:
            raise ValueError("attempt worker lease is invalid")
        self._service = service
        self._runtime = runtime
        self._lease_seconds = lease_seconds
        self._lease = lease
        self._turn_router = turn_router if isinstance(turn_router, DefaultTurnRouter) else DefaultTurnRouter(decision_router=turn_router)
        self._tools_observed = False
        self._result_refs: list[str] = []
        self._evidence_refs: list[str] = []
        self._tool_events: list[Mapping[str, object]] = []

    def run(self, claim: AttemptClaim) -> HarnessAttemptResult:
        if self._lease is not None:
            return self._run(claim, self._lease)
        with AttemptLeaseRenewal(self._service, claim, self._lease_seconds) as lease:
            return self._run(claim, lease)

    def _run(self, claim: AttemptClaim, lease: AttemptLeaseRenewal) -> HarnessAttemptResult:
        self._tools_observed = False
        self._result_refs.clear()
        self._evidence_refs.clear()
        self._tool_events.clear()
        plan: TurnPlan | None = claim.turn_plan
        recovery_attempted = False
        terminal_commit_started = False

        def persist(event: Mapping[str, object]) -> None:
            lease.check()
            self._persist_event(claim, event)

        def heartbeat() -> None:
            lease.check()
            self._renew_lease(claim)

        try:
            lease.check()
            if plan is None and claim.kind in {
                "send_auto", "send_ordinary", "send_professional",
            }:
                try:
                    plan = self._turn_router.plan(routing_input_for_claim(claim))
                except DecisionUnavailable as error:
                    error_code = "llm_route_unavailable" if str(error) == "llm_route_unavailable" else "ordinary_conversation_disabled"
                    self._finish_failed(claim, error_code)
                    return HarnessAttemptResult("failed", None, error_code)
                self._persist_plan(claim, plan)
            self._runtime.start()
            lease.check()
            self._renew_lease(claim)
            answer = self._runtime.prompt(
                claim.instruction,
                correlation_id=claim.attempt.attempt_id,
                on_event=persist,
                on_heartbeat=heartbeat,
            )
            if self._service.cancel_requested(claim):
                raise _AttemptCancelled
            lease.check()
            if not isinstance(answer, str) or not answer.strip() or len(answer) > 64_000:
                raise TypeError("runtime answer is invalid")
            candidate = None
            for correction in range(2):
                try:
                    candidate = self._admit_answer(claim, plan, answer)
                    break
                except _AttemptAdmissionError as error:
                    self._record_validation_failure(claim, answer, lease.check, error.code)
                    recover = getattr(self._runtime, "recover_after_failure", None)
                    if correction or not callable(recover) or not getattr(self._runtime, "recovery_available", True):
                        raise
                    heartbeat()
                    recovery_attempted = True
                    try:
                        answer = recover(
                            {"stage": "answer_check", "code": error.code,
                             "status": "failed", "task_terminal": False,
                             "products_retained": True},
                            on_event=persist, correlation_id=claim.attempt.attempt_id,
                            on_heartbeat=heartbeat,
                        )
                    except _AttemptCancelled:
                        raise
                    except Exception:
                        raise _AttemptAdmissionError("answer_recovery_unavailable") from None
                    heartbeat()
                    if not isinstance(answer, str) or not answer.strip() or len(answer) > 64_000:
                        raise _AttemptAdmissionError("answer_admission_invalid")
            result_refs = () if candidate is None else candidate.result_refs
            evidence_refs = () if candidate is None else candidate.evidence_refs
            result_projections = () if candidate is None else candidate.result_projections
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
            if result_projections:
                terminal_payload["result_projections"] = [dict(item) for item in result_projections]
            if plan is not None and plan.shadow_decision is not None:
                shadow_payload: dict[str, object] = {"status": "pending"}
                if plan.shadow_decision.done():
                    try:
                        shadow = plan.shadow_decision.result()
                        shadow_payload = {"status": "completed", "route": shadow.route, "source": shadow.source}
                    except Exception:
                        shadow_payload = {"status": "unavailable"}
                self._service.append_runtime_event(claim, event_type="turn_router_shadow", payload=shadow_payload, visibility="diagnostic")
            if admission is not None:
                terminal_payload["admission"] = admission
            network_projection = getattr(self._runtime, "network_projection", None)
            if getattr(self._runtime, "network_projection_enabled", False) and callable(
                network_projection
            ):
                lease.check()
                project_network = cast(
                    Callable[
                        [AttemptClaim, tuple[str, ...], tuple[str, ...], tuple[Mapping[str, object], ...]],
                        Mapping[str, object] | None,
                    ],
                    network_projection,
                )
                projection = project_network(
                    claim, result_refs, evidence_refs, tuple(self._tool_events),
                )
                if projection is None:
                    self._service.append_runtime_event(
                        claim,
                        event_type="network_layer_unavailable",
                        payload={"ordinal": 1, "code": getattr(self._runtime, "network_projection_failure_code", "projection_unavailable")},
                        visibility="public",
                    )
                else:
                    self._service.append_runtime_event(
                        claim,
                        event_type="network_diagram",
                        payload={"diagram": projection["diagram"]},
                        visibility="public",
                    )
                    self._service.append_runtime_event(
                        claim,
                        event_type="network_layer",
                        payload={
                            "ordinal": projection["ordinal"],
                            "layer": projection["layer"],
                        },
                        visibility="public",
                    )
            lease.check()
            terminal_commit_started = True
            self._service.finish_attempt(
                claim, phase="completed", payload=terminal_payload,
            )
            return HarnessAttemptResult(
                "completed", admitted_answer, None, result_refs, evidence_refs, admission,
            )
        except _AttemptAdmissionError as error:
            lease.check()
            return self._deliver_failure(claim, error.code, "answer_check", recovery_attempted, lease.check)
        except _AttemptCancelled:
            self._finish_cancelled(claim)
            return HarnessAttemptResult("cancelled", None, "attempt_cancelled")
        except Exception:
            if terminal_commit_started:
                # The write may have committed. Never replace an uncertain
                # successful terminal write with a second, failed outcome.
                raise
            lease.check()
            return self._deliver_failure(claim, "runtime_failed", "execution", recovery_attempted, lease.check)
        finally:
            try:
                self._runtime.stop()
            except Exception:
                pass

    def _admit_answer(
        self, claim: AttemptClaim, plan: TurnPlan | None, answer: str,
    ) -> AdmittedAttemptAnswer | None:
        candidate = None
        admit = getattr(self._runtime, "admit_attempt", None)
        if callable(admit):
            try:
                candidate = admit(claim, answer, tuple(self._result_refs),
                                  tuple(self._evidence_refs), tuple(self._tool_events))
            except Exception:
                raise _AttemptAdmissionError("answer_admission_failed") from None
        if candidate is not None and not isinstance(candidate, AdmittedAttemptAnswer):
            raise _AttemptAdmissionError("answer_admission_invalid")
        if candidate is not None and (
            not set(candidate.result_refs).issubset(self._result_refs)
            or not set(candidate.evidence_refs).issubset(self._evidence_refs)
        ):
            raise _AttemptAdmissionError("answer_admission_invalid")
        observation_admitted = candidate is not None and (
            candidate.mode == "offline_information"
            and candidate.assurance == "deterministic_information"
            and "current_model_observation_verified" in candidate.diagnostic_codes
        )
        if plan is not None and plan.route == "professional" and (
            candidate is None
            or (candidate.mode not in {"authority_backed", "limited"} and not observation_admitted)
            or (candidate.mode == "authority_backed" and not candidate.evidence_refs)
        ):
            raise _AttemptAdmissionError("capability_required")
        professional_route = plan is not None and plan.route == "professional"
        if candidate is None and (
            professional_route
            or (plan is None and claim.kind not in {"send_auto", "send_ordinary"})
            or self._tools_observed
        ):
            raise _AttemptAdmissionError("answer_admission_unavailable")
        return candidate

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
            visibility="public",
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
        self._service.append_runtime_event(
            claim,
            event_type=event_type,
            payload={"runtime_mode": runtime_mode, **dict(payload)},
            visibility=visibility if isinstance(visibility, str) else "diagnostic",
        )
        if event_type in {"tool_started", "tool_completed"}:
            self._tools_observed = True
        _extend_refs(self._result_refs, payload.get("result_refs"))
        _extend_refs(self._evidence_refs, payload.get("evidence_refs"))
        if event_type == "tool_completed":
            self._tool_events.append(dict(payload))

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

    def _deliver_failure(
        self, claim: AttemptClaim, code: str, stage: str, recovery_attempted: bool,
        check_lease: Callable[[], None],
    ) -> HarnessAttemptResult:
        # This text describes execution state only. Numerical findings still
        # require the application's normal authority and evidence admission.
        answer = (
            "本次任务未能完成。正式回答未通过核验，尚不能据此作出结论。"
            if stage == "answer_check" else
            "本次任务未能完成。执行中断，尚不能给出完整结论。"
        )
        if recovery_attempted:
            answer += "已尝试纠正回答，但未能形成通过核验的最终结论。"
        answer += "已记录的执行过程仍保留。"
        candidate = self._admit_partial_results(claim, answer, check_lease)
        results = () if candidate is None else candidate.result_refs
        evidence = () if candidate is None else candidate.evidence_refs
        admission = None if candidate is None else {
            "mode": candidate.mode, "assurance": candidate.assurance,
        }
        if candidate is not None:
            answer += "已核验的计算结果和证据已保留；它们不代表整个任务已完成。"
        payload: dict[str, object] = {
            "answer": answer, "error_code": code,
            "result_refs": list(results), "evidence_refs": list(evidence),
            "outcome": {"status": "partial" if candidate else "blocked",
                        "stage": stage,
                        "recovery": "attempted" if recovery_attempted else "unavailable"},
        }
        if admission is not None:
            payload["admission"] = admission
        if candidate is not None and candidate.result_projections:
            payload["result_projections"] = [dict(item) for item in candidate.result_projections]
        check_lease()
        self._service.finish_attempt(claim, phase="failed", payload=payload)
        return HarnessAttemptResult("failed", answer, code, results, evidence, admission)

    def _record_validation_failure(
        self, claim: AttemptClaim, answer: str, check_lease: Callable[[], None],
        code: str = "answer_admission_failed",
    ) -> None:
        # Preserve the rejected product separately from the formal answer.
        # No raw exception text enters the public stream or model feedback.
        for index, offset in enumerate(range(0, len(answer), 8_000)):
            check_lease()
            self._service.append_runtime_event(
                claim, event_type="unverified_answer_recorded", visibility="diagnostic",
                payload={"status": "not_admitted", "chunk_index": index,
                         "text": answer[offset:offset + 8_000]},
            )
        check_lease()
        self._service.append_runtime_event(
            claim, event_type="validation_observation", visibility="public",
            payload={"status": "failed", "stage": "answer_check",
                     "code": code, "task_terminal": False,
                     "products_retained": True,
                     "message": "回答核验未通过，原始内容和执行记录已保留，交由智能体继续处理。",
                     "observed_result_refs": list(self._result_refs),
                     "observed_evidence_refs": list(self._evidence_refs)},
        )

    def _admit_partial_results(
        self, claim: AttemptClaim, answer: str, check_lease: Callable[[], None],
    ) -> AdmittedAttemptAnswer | None:
        admit = getattr(self._runtime, "admit_attempt", None)
        if not self._result_refs or not self._evidence_refs or not callable(admit):
            return None

        def checked_group(results: tuple[str, ...], evidence: tuple[str, ...]) -> AdmittedAttemptAnswer | None:
            check_lease()
            try:
                checked = admit(claim, answer, results, evidence, tuple(self._tool_events))
                if (isinstance(checked, AdmittedAttemptAnswer)
                    and checked.mode == "authority_backed"
                    and checked.result_refs and checked.evidence_refs
                    and set(checked.result_refs).issubset(results)
                    and set(checked.evidence_refs).issubset(evidence)):
                    return checked
            except Exception:
                pass
            return None

        candidate = checked_group(tuple(self._result_refs), tuple(self._evidence_refs))
        if candidate is not None:
            return candidate
        # Tool receipts define candidate groups, never their validity. Bound
        # recovery work and retain full history for groups not admitted here.
        seen: set[tuple[tuple[str, ...], tuple[str, ...]]] = set()
        retained_results: list[str] = []
        retained_evidence: list[str] = []
        for event in reversed(self._tool_events):
            if event.get("ok") is not True:
                continue
            group_results: list[str] = []
            group_evidence: list[str] = []
            _extend_refs(group_results, event.get("result_refs"))
            _extend_refs(group_evidence, event.get("evidence_refs"))
            group = (tuple(group_results), tuple(group_evidence))
            if not group_results or not group_evidence or group in seen:
                continue
            seen.add(group)
            candidate = checked_group(*group)
            if candidate is not None:
                _extend_refs(retained_results, candidate.result_refs)
                _extend_refs(retained_evidence, candidate.evidence_refs)
            if len(seen) >= 16:
                break
        if not retained_results or not retained_evidence:
            return None
        # Re-admit the combined references: separately valid groups need not
        # share a compatible model revision or answer policy.
        return checked_group(tuple(retained_results), tuple(retained_evidence))


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
    "CapstoneHarness", "HarnessAttemptResult", "HarnessAttemptRunner",
    "HarnessDSHClient", "HarnessPiClient", "HarnessRuntimeRegistry",
    "HarnessRuntimeUnavailable",
    "HarnessRuntimeConfigurationError",
    "PiPromptSession", "normalize_runtime_event",
    "HarnessRuntime", "RuntimeFactory",
    "AttemptAdmission",
    "AdmittedAttemptAnswer",
]
