"""Lease-aware worker entry points for durable Thread Attempts.

The HTTP process only admits commands.  This module owns the small polling
boundary that claims accepted Attempts, constructs an injected Harness
runtime, and lets :class:`HarnessAttemptRunner` persist the terminal result.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import replace
from typing import TYPE_CHECKING

from .attempt_lease import AttemptLeaseRenewal
from .harness import HarnessAttemptResult, HarnessAttemptRunner, HarnessRuntime, HarnessRuntimeConfigurationError
from .thread_service import AttemptClaim, ThreadExecutionService
from .turn_router import DecisionUnavailable, DefaultTurnRouter, TurnPlan, TurnRouter, routing_input_for_claim
from .request_intent import NodeControl
from .task_record_reader import SelectedTaskRecordReader

if TYPE_CHECKING:
    from .case_service import CaseExecutionService


RuntimeFactory = Callable[[AttemptClaim], HarnessRuntime]
_LOG = logging.getLogger(__name__)
# One decision call. Completed understandings on this deployment finish well
# inside this limit; a call that is still thinking at the limit has no decision.
_INTENT_RECOGNITION_SECONDS = 120


def run_pending_attempt(
    service: ThreadExecutionService,
    runtime_factory: RuntimeFactory,
    *,
    worker_id: str,
    lease_seconds: int = 30,
    turn_router: TurnRouter | None = None,
    case_service: "CaseExecutionService | None" = None,
    implementation_family: str | None = None,
) -> HarnessAttemptResult | None:
    """Run at most one accepted Attempt and return ``None`` when idle."""

    service.interrupt_expired_attempts()
    claim = service.claim_attempt(worker_id, lease_seconds, implementation_family)
    if claim is None:
        return None
    with AttemptLeaseRenewal(service, claim, lease_seconds) as lease:
        origin = os.environ.get('CAPSTONE_THINKING_PREVIEW_ORIGIN')
        writer = None
        if origin:
            from .thinking_preview import ThinkingWriter, http_publisher
            writer = ThinkingWriter(service, claim, http_publisher(
                origin, os.environ.get('CAPSTONE_OPERATOR_TOKEN', ''), claim))
        try:
            return _run_claimed_attempt(
                writer or service, runtime_factory, claim, lease, lease_seconds, turn_router,
            )
        except Exception:
            if writer is not None and writer.error is not None:
                # Use the original synchronous service: the failed writer cannot
                # acknowledge a terminal result through its own flush barrier.
                service.finish_attempt(claim, phase='failed', payload={
                    'error_code': 'thinking_persistence_failed'})
            raise
        finally:
            if writer is not None:
                writer.close()


def _run_claimed_attempt(
    service: ThreadExecutionService, runtime_factory: RuntimeFactory,
    claim: AttemptClaim, lease: AttemptLeaseRenewal, lease_seconds: int,
    turn_router: TurnRouter | None,
) -> HarnessAttemptResult:
    if service.cancel_requested(claim):
        service.finish_attempt(claim, phase='cancelled', payload={})
        return HarnessAttemptResult('cancelled', None, None)
    previous = claim.previous_instruction
    manifests = (claim.submission or {}).get('_resource_manifests', ())
    if manifests:
        from .continuation_resources import resource_reader_for
        claim = replace(claim, resource_reader=resource_reader_for(service, claim))
    if previous is not None:
        claim = replace(claim, selected_task_reader=SelectedTaskRecordReader(
            service, claim.thread_id, previous.attempt_id))
    router = turn_router if isinstance(turn_router, DefaultTurnRouter) else DefaultTurnRouter(decision_router=turn_router)
    if claim.kind in {"send_auto", "send_ordinary", "send_professional"}:
        def check_intent() -> None:
            lease.check()
            if service.cancel_requested(claim):
                raise InterruptedError('intent cancelled')
        try:
            semantic = getattr(runtime_factory, 'plan_intent', None)
            if callable(semantic):
                if not router.ordinary_conversation_enabled:
                    raise DecisionUnavailable('ordinary_conversation_disabled')
                service.append_runtime_event(claim, event_type='intent_started',
                                             payload={'stage': 'understanding'})
                service.append_runtime_event(claim, event_type='runtime_action', payload={
                    'phase': 'started', 'response_intent': '理解当前指令'})
                def notice(event: Mapping[str, object]) -> None:
                    text = event.get('text') if event.get('type') == 'assistant_thinking_delta' else None
                    if not isinstance(text, str) or not text:
                        return
                    thinking = getattr(service, 'append_thinking', None)
                    if callable(thinking):
                        thinking(claim, {'text': text[:4096]})
                    else:
                        service.append_runtime_event(
                            claim, event_type='assistant_thinking_delta', payload={'text': text[:4096]})
                control = NodeControl(check_intent, time.monotonic() + _INTENT_RECOGNITION_SECONDS, notice=notice)
                if getattr(runtime_factory, 'supports_frozen_intent_decision', False):
                    plan = semantic(claim, control, service.freeze_attempt_input,
                                    freeze_decision=service.freeze_attempt_decision)
                else:
                    # Existing custom planners retain their three-argument seam.
                    plan = semantic(claim, control, service.freeze_attempt_input)
            else:
                plan = router.plan(routing_input_for_claim(claim))
            if not isinstance(plan, TurnPlan):
                raise ValueError('intent node returned an invalid plan')
            service.append_runtime_event(claim, event_type='runtime_action', payload={
                'phase': 'response_completed', 'response_intent': '理解当前指令'})
        except InterruptedError:
            service.finish_attempt(claim, phase='cancelled', payload={})
            return HarnessAttemptResult('cancelled', None, None)
        except Exception as error:
            error_code = ('intent_deadline_exceeded'
                          if isinstance(error, TimeoutError) and str(error) == 'intent recognition deadline expired'
                          else 'runtime_configuration_invalid' if isinstance(error, HarnessRuntimeConfigurationError)
                          else 'ordinary_conversation_disabled'
                          if isinstance(error, DecisionUnavailable) and str(error) == 'ordinary_conversation_disabled'
                          else 'llm_route_unavailable'
                          if isinstance(error, DecisionUnavailable) and str(error) == 'llm_route_unavailable'
                          else 'intent_recognition_failed')
            payload = {'error_code': error_code}
            if error_code == 'intent_recognition_failed':
                payload['message'] = '本次请求暂时未能处理，请重试。会话和模型选择已保留。'
            lease.check()
            return _preparation_failure(service, claim, error_code, error=error)
        service.append_runtime_event(claim, event_type="turn_plan_created", payload=plan.to_payload())
        service.append_runtime_event(
            claim, event_type="turn_route_fallback" if plan.fallback else "turn_route_selected",
            payload={"route": plan.route, "source": plan.source, "plan_revision": plan.plan_revision,
                     "fallback": plan.fallback},
        )
        claim = replace(claim, turn_plan=plan)
        resources = plan.intent_resources
        family = resources.get('domain_dispatch_family') if isinstance(resources, Mapping) else None
        if isinstance(family, str) and family:
            release = getattr(service, 'release_attempt_for_domain', None)
            if not callable(release):
                return _preparation_failure(
                    service, claim, 'runtime_configuration_invalid',
                    error=HarnessRuntimeConfigurationError('domain execution handoff is unavailable'))
            try:
                lease.check()
                release(claim, family)
            except Exception as error:
                return _preparation_failure(service, claim, 'runtime_configuration_invalid', error=error)
            _wake_released_family(family)
            return HarnessAttemptResult('released', None, None)
        if plan.route == "professional" and claim.model_context is not None and not claim.model_context.enabled_profiles:
            error_code = "capability_required"
            service.finish_attempt(claim, phase="failed", payload={
                "error_code": error_code,
                "message": "未启用适用于当前模型的计算分析工具。请在设置中启用后重新发送计算指令；仍可继续普通对话。",
            })
            return HarnessAttemptResult("failed", None, error_code)
    runtime = None
    try:
        lease.check()
        runtime = runtime_factory(claim)
        bind_artifact_store = getattr(runtime, 'bind_artifact_store', None)
        if callable(bind_artifact_store):
            bind_artifact_store(getattr(service, '_material_objects', None))
        bind_guard = getattr(runtime, "bind_attempt_guard", None)
        if callable(bind_guard):
            def active() -> bool:
                lease.check()
                return not service.cancel_requested(claim)
            def terminal_phase(attempt_id: str) -> str | None:
                cursor = 0
                while True:
                    lease.check()
                    page = service.read_attempt_records(claim.thread_id, attempt_id, after=cursor, limit=128)
                    for event in page["events"]:
                        if event["event_type"] in {"attempt_completed", "attempt_failed", "attempt_cancelled", "attempt_interrupted"}:
                            return event["event_type"].removeprefix("attempt_")
                    if not page["has_more"]:
                        return None
                    if page["next_after"] <= cursor:
                        raise RuntimeError("attempt record cursor did not advance")
                    cursor = page["next_after"]
            bind_guard(active, terminal_phase)
    except HarnessRuntimeConfigurationError as error:
        _close_prepared_runtime(runtime)
        error_code = "runtime_configuration_invalid"
        lease.check()
        return _preparation_failure(service, claim, error_code, error=error)
    except Exception as error:
        _close_prepared_runtime(runtime)
        lease.check()
        error_code = "runtime_unavailable"
        rollback_error = None
        if getattr(runtime_factory, "rollback_selection_on_failure", False):
            error_code = "capability_context_preparation_failed"
            try:
                rollback = getattr(
                    service, "rollback_context_if_preparation_failed", None,
                )
                if callable(rollback):
                    rollback(claim, error_code=error_code)
                else:
                    service.rollback_selection_if_preparation_failed(
                        claim, error_code=error_code,
                    )
            except Exception as secondary:
                rollback_error = secondary
        return _preparation_failure(service, claim, error_code, error=error, rollback_error=rollback_error)
    return HarnessAttemptRunner(
        service, runtime, lease_seconds=lease_seconds, turn_router=router, lease=lease,
    ).run(claim)


def _close_prepared_runtime(runtime: HarnessRuntime | None) -> None:
    if runtime is not None:
        try:
            runtime.stop()
        except Exception as error:
            from .native_failure_origin import native_failure_origin
            _LOG.warning("Prepared runtime cleanup failed; exception_type=%s; origin=%s",
                         type(error).__name__, native_failure_origin(error))


def _preparation_failure(service: ThreadExecutionService, claim: AttemptClaim, code: str,
                         *, error: Exception | None = None, rollback_error: Exception | None = None) -> HarnessAttemptResult:
    from .execution_stages import ExecutionStages, preparation_seconds
    from .native_failure_origin import native_failure_origin
    stages = ExecutionStages(preparation_seconds=preparation_seconds(claim.started_at))
    answer = (f"理解当前指令超时。{_INTENT_RECOGNITION_SECONDS} 秒内没有形成可执行的决策，因此没有开始后续执行。此前已完成的回答和记录仍保留。"
              if code == 'intent_deadline_exceeded'
              else "本次任务未能开始执行。运行准备未完成，因此没有生成新的计算结论。此前已完成的回答和记录仍保留。")
    service.finish_attempt(claim, phase="failed", payload={
        "answer": answer, "error_code": code, "result_refs": [], "evidence_refs": [],
        "outcome": {"status": "blocked", "stage": "preparation", "recovery": "unavailable"},
        "task_steps": stages.finish(failed=True),
        **({'failure_origin': native_failure_origin(error)} if error is not None else {}),
        **({'recovery_failure': {'operation': 'rollback_selection',
            'failure_origin': native_failure_origin(rollback_error)}} if rollback_error is not None else {}),
    })
    return HarnessAttemptResult("failed", answer, code)


def _wake_released_family(family: str) -> None:
    """The receiving worker sleeps until an HTTP wake. Release must send one."""
    origins = os.environ.get('CAPSTONE_FAMILY_HEALTH_URLS', '')
    token = os.environ.get('CAPSTONE_OPERATOR_TOKEN', '')
    if not origins or not token:
        return
    from .worker_wake import configured_family_wake
    try:
        configured_family_wake(os.environ.get('CAPSTONE_WORKER_WAKE_URL'), origins, token)(family)
    except (OSError, TimeoutError, ValueError):
        _LOG.warning('Domain handoff wake failed for family %s', family)


def serve_thread_attempts(
    service: ThreadExecutionService,
    runtime_factory: RuntimeFactory,
    *,
    worker_id: str = "capstone-thread-worker",
    lease_seconds: int = 30,
    poll_seconds: float = 0.25,
    stop_event: threading.Event | None = None,
    wake_event: threading.Event | None = None,
    turn_router: TurnRouter | None = None,
    case_service: "CaseExecutionService | None" = None,
    implementation_family: str | None = None,
    max_concurrent_attempts: int = 1,
) -> None:
    """Drain accepted Attempts after wake, or poll without a wake transport.

    Runtime construction is injected so this worker remains neutral about Pi,
    DSH, Domain Packs, and registered Authorities.
    """

    if not worker_id or lease_seconds < 1 or poll_seconds <= 0:
        raise ValueError("thread worker configuration is invalid")
    if type(max_concurrent_attempts) is not int or max_concurrent_attempts < 1:
        raise ValueError('thread worker capacity must be a positive integer')
    stop = stop_event or threading.Event()
    def has_pending() -> bool:
        reader = getattr(service, 'has_pending_attempts', None)
        return bool(reader(implementation_family)) if callable(reader) else False
    idle = False
    try:
        if max_concurrent_attempts > 1:
            from .thread_worker_capacity import serve_attempt_slots
            serve_attempt_slots(
                lambda: run_pending_attempt(
                    service, runtime_factory, worker_id=worker_id,
                    lease_seconds=lease_seconds, turn_router=turn_router,
                    case_service=case_service, implementation_family=implementation_family),
                capacity=max_concurrent_attempts, stop=stop, wake=wake_event,
                poll_seconds=poll_seconds, sweep=getattr(runtime_factory, 'sweep_idle', None),
                reconcile=case_service.reconcile_active if case_service is not None else None,
                pending=has_pending,
            )
            return
        while not stop.is_set():
            if idle and wake_event is not None:
                # Local cache expiry must still run while idle, but no ledger
                # connection is needed until an authenticated wake arrives.
                sweep = getattr(runtime_factory, 'sweep_idle', None)
                if callable(sweep):
                    try:
                        sweep()
                    except Exception as error:
                        from .native_failure_origin import native_failure_origin
                        _LOG.warning('Thread idle resource cleanup failed; exception_type=%s; origin=%s; retrying',
                                     type(error).__name__, native_failure_origin(error))
                        stop.wait(1)
                        continue
                if not wake_event.wait(timeout=1):
                    continue
                if stop.is_set():
                    break
            if wake_event is not None:
                # Clear before scanning so a wake during IO remains pending.
                wake_event.clear()
            idle = False
            try:
                sweep = getattr(runtime_factory, 'sweep_idle', None)
                if callable(sweep):
                    sweep()
                if case_service is not None:
                    case_service.reconcile_active()
                result = run_pending_attempt(
                    service, runtime_factory, worker_id=worker_id,
                    lease_seconds=lease_seconds,
                    turn_router=turn_router,
                    case_service=case_service,
                    implementation_family=implementation_family,
                )
                retry_pending = result is None and has_pending()
                if case_service is not None:
                    case_service.reconcile_active()
            except Exception as error:
                # A lost claim or unavailable ledger must not kill the polling
                # thread. The ledger fences late writes and expires stale claims.
                from .native_failure_origin import native_failure_origin
                _LOG.warning("Thread worker iteration failed; origin=%s; retrying after poll interval",
                             native_failure_origin(error))
                stop.wait(poll_seconds)
                continue
            if result is None:
                if wake_event is None or retry_pending:
                    stop.wait(poll_seconds)
                else:
                    idle = True
    finally:
        close = getattr(runtime_factory, 'close', None)
        if callable(close):
            from .runtime_cleanup import run_runtime_cleanup
            run_runtime_cleanup(close, operation='worker_factory_close')


__all__ = ["RuntimeFactory", "run_pending_attempt", "serve_thread_attempts"]
