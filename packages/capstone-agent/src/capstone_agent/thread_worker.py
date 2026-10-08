"""Lease-aware worker entry points for durable Thread Attempts.

The HTTP process only admits commands.  This module owns the small polling
boundary that claims accepted Attempts, constructs an injected Harness
runtime, and lets :class:`HarnessAttemptRunner` persist the terminal result.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import replace
from typing import TYPE_CHECKING

from .attempt_lease import AttemptLeaseRenewal
from .harness import HarnessAttemptResult, HarnessAttemptRunner, HarnessRuntime, HarnessRuntimeConfigurationError
from .thread_service import AttemptClaim, ThreadExecutionService
from .turn_router import DecisionUnavailable, DefaultTurnRouter, TurnRouter, routing_input_for_claim

if TYPE_CHECKING:
    from .case_service import CaseExecutionService


RuntimeFactory = Callable[[AttemptClaim], HarnessRuntime]
_LOG = logging.getLogger(__name__)


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
        return _run_claimed_attempt(
            service, runtime_factory, claim, lease, lease_seconds, turn_router,
        )


def _run_claimed_attempt(
    service: ThreadExecutionService, runtime_factory: RuntimeFactory,
    claim: AttemptClaim, lease: AttemptLeaseRenewal, lease_seconds: int,
    turn_router: TurnRouter | None,
) -> HarnessAttemptResult:
    router = turn_router if isinstance(turn_router, DefaultTurnRouter) else DefaultTurnRouter(decision_router=turn_router)
    if claim.kind in {"send_auto", "send_ordinary", "send_professional"}:
        try:
            plan = router.plan(routing_input_for_claim(claim))
        except DecisionUnavailable:
            error_code = "ordinary_conversation_disabled"
            service.finish_attempt(claim, phase="failed", payload={"error_code": error_code})
            return HarnessAttemptResult("failed", None, error_code)
        service.append_runtime_event(claim, event_type="turn_plan_created", payload=plan.to_payload())
        service.append_runtime_event(
            claim, event_type="turn_route_fallback" if plan.fallback else "turn_route_selected",
            payload={"route": plan.route, "source": plan.source, "plan_revision": plan.plan_revision,
                     "fallback": plan.fallback},
        )
        claim = replace(claim, turn_plan=plan)
        if plan.route == "professional" and not claim.model_context.enabled_profiles:
            error_code = "capability_required"
            service.finish_attempt(claim, phase="failed", payload={
                "error_code": error_code,
                "message": "未启用适用于当前模型的计算分析工具。请在设置中启用后重新发送计算指令；仍可继续普通对话。",
            })
            return HarnessAttemptResult("failed", None, error_code)
    try:
        lease.check()
        runtime = runtime_factory(claim)
    except HarnessRuntimeConfigurationError:
        error_code = "runtime_configuration_invalid"
        service.finish_attempt(claim, phase="failed", payload={"error_code": error_code})
        return HarnessAttemptResult("failed", None, error_code)
    except Exception:
        error_code = "runtime_unavailable"
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
            except Exception:
                pass
        service.finish_attempt(
            claim, phase="failed", payload={"error_code": error_code},
        )
        return HarnessAttemptResult("failed", None, error_code)
    return HarnessAttemptRunner(
        service, runtime, lease_seconds=lease_seconds, turn_router=router, lease=lease,
    ).run(claim)


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
) -> None:
    """Drain accepted Attempts after wake, or poll without a wake transport.

    Runtime construction is injected so this worker remains neutral about Pi,
    DSH, Domain Packs, and registered Authorities.
    """

    if not worker_id or lease_seconds < 1 or poll_seconds <= 0:
        raise ValueError("thread worker configuration is invalid")
    stop = stop_event or threading.Event()
    idle = False
    try:
        while not stop.is_set():
            if idle and wake_event is not None:
                # Local cache expiry must still run while idle, but no ledger
                # connection is needed until an authenticated wake arrives.
                sweep = getattr(runtime_factory, 'sweep_idle', None)
                if callable(sweep):
                    try:
                        sweep()
                    except Exception:
                        _LOG.warning('Thread idle resource cleanup failed; retrying')
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
                if case_service is not None:
                    case_service.reconcile_active()
            except Exception:
                # A lost claim or unavailable ledger must not kill the polling
                # thread. The ledger fences late writes and expires stale claims.
                _LOG.warning("Thread worker iteration failed; retrying after poll interval")
                stop.wait(poll_seconds)
                continue
            if result is None:
                if wake_event is None:
                    stop.wait(poll_seconds)
                else:
                    idle = True
    finally:
        close = getattr(runtime_factory, 'close', None)
        if callable(close):
            close()


__all__ = ["RuntimeFactory", "run_pending_attempt", "serve_thread_attempts"]
