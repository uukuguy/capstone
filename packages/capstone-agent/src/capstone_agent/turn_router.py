"""Application-owned, auditable routing for one Thread Turn.

The router decides which conversation lane should be attempted.  It never
decides whether a tool result or evidence may be admitted; that remains the
Harness/Domain Pack boundary.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from concurrent.futures import Future
from dataclasses import dataclass, field, replace
import json
import re
from threading import Thread
from typing import Protocol

from .thread_service import AttemptClaim


class DecisionUnavailable(RuntimeError):
    """A pluggable classifier could not make a trusted decision."""


_ROUTES = frozenset({"ordinary", "professional"})
_MAX_HINT = 160
_MAX_CONTEXT = 1024
_MAX_ROUTING_TEXT = 2_048
_DOMAIN_HINTS = (
    "电网", "潮流", "线路", "母线", "变压器", "拓扑", "约束", "越限",
    "n-1", "pandapower", "pypsa", "负载率", "短路", "孤岛", "收敛",
)
_MODEL_CATALOG_SUBJECTS = ("模型", "models", "networks", "model catalog", "模型目录")
_MODEL_CATALOG_REQUESTS = (
    "有哪些", "有什么", "哪些", "列出", "列一下", "目录", "清单",
    "which", "what", "list", "available", "supported", "catalog",
)
_CALCULATION_HINTS = (
    *(_hint for _hint in _DOMAIN_HINTS if _hint not in {"电网", "pandapower", "pypsa"}),
    "运行", "执行", "计算", "求解", "调度", "优化", "损耗", "电压", "功率",
    "容量", "成本", "发电", "储能", "负荷", "修改", "创建", "打开", "载入",
    "run", "execute", "calculate", "solve", "dispatch", "optimi", "loss",
    "voltage", "power flow", "overload", "line", "bus", "capacity", "cost",
    "generator", "storage", "load", "modify", "create", "open",
)


def _heuristic_route(instruction: str) -> str:
    text = instruction.lower()
    # Availability is answered from the application's bounded registered catalog.
    # A mixed catalog/calculation request still needs the professional lane.
    catalog_query = (
        any(subject in text for subject in _MODEL_CATALOG_SUBJECTS)
        and any(request in text for request in _MODEL_CATALOG_REQUESTS)
    )
    if catalog_query:
        return "professional" if any(hint in text for hint in _CALCULATION_HINTS) else "ordinary"
    return "professional" if any(hint in text for hint in _DOMAIN_HINTS) else "ordinary"


@dataclass(frozen=True, slots=True)
class RouterConfig:
    mode: str = "off"
    model: str = "none"
    schema: str = "capstone-routing-decision/1"

    def __post_init__(self) -> None:
        if self.mode not in {"off", "heuristic", "jev_active", "jev_shadow"}:
            raise ValueError("router mode is invalid")
        if any(not isinstance(value, str) or not value or len(value) > 128
               for value in (self.model, self.schema)):
            raise ValueError("router identity is invalid")

    def to_document(self) -> dict[str, object]:
        return {"mode": self.mode, "model": self.model, "schema": self.schema}


def _validate_context(context: Mapping[str, object]) -> None:
    allowed = {"model_id", "model_revision", "model_context_id", "implementation_family", "selection_revision", "enabled_profiles"}
    if not isinstance(context, Mapping) or set(context) - allowed:
        raise ValueError("routing context fields are invalid")
    try:
        encoded = json.dumps(dict(context), allow_nan=False, sort_keys=True)
    except (TypeError, ValueError):
        raise ValueError("routing context is not JSON") from None
    if len(encoded.encode("utf-8")) > 16_384:
        raise ValueError("routing context is too large")


@dataclass(frozen=True, slots=True)
class TurnIntent:
    route: str
    source: str
    confidence: str | None = None

    def __post_init__(self) -> None:
        if self.route not in _ROUTES:
            raise ValueError("turn route is invalid")
        if not self.source or len(self.source) > 64:
            raise ValueError("turn decision source is invalid")
        if self.confidence is not None and len(self.confidence) > 32:
            raise ValueError("turn decision confidence is invalid")


@dataclass(frozen=True, slots=True)
class RoutingInput:
    """Sanitized router input; runtime objects and raw transcripts never enter it."""

    turn_id: str
    attempt_id: str
    instruction: str
    command_kind: str
    context_snapshot: Mapping[str, object]

    def __post_init__(self) -> None:
        if not self.turn_id or not self.attempt_id:
            raise ValueError("routing identity is invalid")
        if not self.instruction or len(self.instruction) > 16_384:
            raise ValueError("routing instruction is invalid")
        if self.command_kind not in {"send_auto", "send_ordinary", "send_professional"}:
            raise ValueError("routing command kind is invalid")
        _validate_context(self.context_snapshot)


@dataclass(frozen=True, slots=True)
class TurnPlan:
    turn_id: str
    attempt_id: str
    route: str
    source: str
    plan_revision: str
    capability_hint: str | None
    context_snapshot: Mapping[str, object]
    confidence: str | None = None
    fallback: bool = False
    router_config: RouterConfig = RouterConfig()
    fallback_reason: str | None = None
    shadow_decision: Future[TurnPlan] | None = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not self.turn_id or not self.attempt_id or not self.plan_revision:
            raise ValueError("turn plan identity is invalid")
        if self.route not in _ROUTES:
            raise ValueError("turn plan route is invalid")
        if self.capability_hint is not None and len(self.capability_hint) > _MAX_HINT:
            raise ValueError("turn plan capability hint is too long")
        if self.confidence is not None and len(self.confidence) > 32:
            raise ValueError("turn plan confidence is invalid")
        _validate_context(self.context_snapshot)
        if not isinstance(self.router_config, RouterConfig):
            raise ValueError("turn plan router config is invalid")

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "turn_id": self.turn_id,
            "attempt_id": self.attempt_id,
            "route": self.route,
            "source": self.source,
            "plan_revision": self.plan_revision,
            "context_snapshot": dict(self.context_snapshot),
            "fallback": self.fallback,
            "router_config": self.router_config.to_document(),
        }
        if self.capability_hint is not None:
            payload["capability_hint"] = self.capability_hint
        if self.confidence is not None:
            payload["confidence"] = self.confidence
        if self.fallback_reason is not None:
            payload["fallback_reason"] = self.fallback_reason
        return payload


class TurnRouter(Protocol):
    def plan(self, routing_input: RoutingInput) -> TurnPlan: ...


def _context_snapshot(claim: AttemptClaim) -> dict[str, object]:
    context = claim.model_context
    profiles = [
        {"profile_id": profile_id, "profile_version": version}
        for profile_id, version in context.enabled_profiles[:16]
    ]
    return {
        "model_id": context.model_id,
        "model_revision": context.model_revision,
        "model_context_id": context.id,
        "implementation_family": context.implementation_family,
        "selection_revision": context.selection_revision,
        "enabled_profiles": profiles,
    }


def routing_input_for_claim(claim: AttemptClaim) -> RoutingInput:
    return RoutingInput(
        turn_id=claim.attempt.turn_id,
        attempt_id=claim.attempt.attempt_id,
        instruction=_sanitize_instruction(claim.instruction),
        command_kind=claim.kind,
        context_snapshot=_context_snapshot(claim),
    )


def _sanitize_instruction(instruction: str) -> str:
    """Keep classifier input useful while excluding common secret/path forms."""

    text = " ".join(instruction.split())[:_MAX_ROUTING_TEXT]
    text = re.sub(r"(?i)(api[_-]?key|token|password|secret)\s*[:=]\s*\S+", r"\1=[redacted]", text)
    text = re.sub(r"(?<!\w)/(?:[^\s/]+/)+[^\s]+", "[path]", text)
    return text


class DefaultTurnRouter:
    """Route explicit commands and auto commands with a safe policy fallback."""

    def __init__(
        self,
        *,
        decision_router: TurnRouter | None = None,
        ordinary_conversation_enabled: bool = True,
        config: RouterConfig | None = None,
    ) -> None:
        if decision_router is self:
            raise ValueError("turn router cannot wrap itself")
        self._decision_router = decision_router
        self.ordinary_conversation_enabled = ordinary_conversation_enabled
        self.config = config or RouterConfig(mode="jev_active" if decision_router else "off")

    def _shadow(self, routing_input: RoutingInput) -> Future[TurnPlan]:
        future: Future[TurnPlan] = Future()

        def decide() -> None:
            try:
                if self._decision_router is None:
                    raise DecisionUnavailable("shadow_router_unavailable")
                future.set_result(self._decision_router.plan(routing_input))
            except Exception:
                future.set_exception(DecisionUnavailable("shadow_decision_unavailable"))

        Thread(target=decide, name="capstone-router-shadow", daemon=True).start()
        return future

    def plan(self, routing_input: RoutingInput | AttemptClaim) -> TurnPlan:
        if isinstance(routing_input, AttemptClaim):
            routing_input = routing_input_for_claim(routing_input)
        if routing_input.command_kind == "send_professional":
            intent = TurnIntent("professional", "explicit")
        elif routing_input.command_kind == "send_ordinary":
            intent = TurnIntent("ordinary", "explicit")
        elif routing_input.command_kind == "send_auto":
            if self._decision_router is None or self.config.mode in {"off", "heuristic", "jev_shadow"}:
                intent = TurnIntent(
                    _heuristic_route(routing_input.instruction), "heuristic", "bounded_heuristic",
                )
            else:
                try:
                    nested = self._decision_router.plan(routing_input)
                    intent = TurnIntent(nested.route, nested.source, nested.confidence)
                except Exception:
                    intent = TurnIntent(
                        _heuristic_route(routing_input.instruction),
                        "decision_unavailable",
                    )
                    return self._make(routing_input, intent, fallback=True)
        else:
            raise DecisionUnavailable("unsupported_turn_kind")
        if intent.route == "ordinary" and not self.ordinary_conversation_enabled:
            raise DecisionUnavailable("ordinary_conversation_disabled")
        plan = self._make(routing_input, intent)
        if self.config.mode == "jev_shadow" and routing_input.command_kind == "send_auto":
            plan = replace(plan, shadow_decision=self._shadow(routing_input))
        return plan

    def _make(self, routing_input: RoutingInput, intent: TurnIntent, *, fallback: bool = False) -> TurnPlan:
        if intent.route == "ordinary" and not self.ordinary_conversation_enabled:
            raise DecisionUnavailable("ordinary_conversation_disabled")
        return TurnPlan(
            turn_id=routing_input.turn_id,
            attempt_id=routing_input.attempt_id,
            route=intent.route,
            source=intent.source,
            plan_revision="turn-plan-v1",
            capability_hint=("domain_analysis" if intent.route == "professional" else "general_conversation"),
            context_snapshot=routing_input.context_snapshot,
            confidence=intent.confidence,
            fallback=fallback,
            router_config=self.config,
            fallback_reason="decision_unavailable" if fallback else None,
        )


class FakeDecisionRouter:
    """Deterministic fixture router used by tests and local demonstrations."""

    def __init__(self, decision: str | Callable[[str], str]) -> None:
        self._decision = decision

    def plan(self, routing_input: RoutingInput) -> TurnPlan:
        value = self._decision(routing_input.instruction) if callable(self._decision) else self._decision
        if value not in _ROUTES:
            raise DecisionUnavailable("fake_decision_invalid")
        return TurnPlan(
            turn_id=routing_input.turn_id,
            attempt_id=routing_input.attempt_id,
            route=value,
            source="fake",
            plan_revision="turn-plan-v1",
            capability_hint=None,
            context_snapshot=routing_input.context_snapshot,
        )


class JevDecisionRouter:
    """Optional low-latency Jev adapter without a hard dependency on Jev."""

    def __init__(self, classifier: Callable[[str], str], *, enabled: bool = False) -> None:
        if not callable(classifier):
            raise TypeError("Jev classifier must be callable")
        self.enabled = enabled
        self._classifier = classifier

    def plan(self, routing_input: RoutingInput) -> TurnPlan:
        if not self.enabled:
            raise DecisionUnavailable("jev_disabled")
        try:
            route = self._classifier(routing_input.instruction)
        except Exception as error:
            raise DecisionUnavailable("jev_unavailable") from error
        if route not in _ROUTES:
            raise DecisionUnavailable("jev_decision_invalid")
        return TurnPlan(
            turn_id=routing_input.turn_id,
            attempt_id=routing_input.attempt_id,
            route=route,
            source="jev",
            plan_revision="turn-plan-v1",
            capability_hint="domain_analysis" if route == "professional" else "general_conversation",
            context_snapshot=routing_input.context_snapshot,
        )


__all__ = [
    "DecisionUnavailable", "DefaultTurnRouter", "FakeDecisionRouter", "JevDecisionRouter",
    "RoutingInput", "TurnIntent", "TurnPlan", "TurnRouter", "routing_input_for_claim",
    "RouterConfig",
]
