"""Application-owned, auditable routing for one Thread Turn.

The router decides which conversation lane should be attempted.  It never
decides whether a tool result or evidence may be admitted; that remains the
Harness/Domain Pack boundary.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Protocol

from .thread_service import AttemptClaim


class DecisionUnavailable(RuntimeError):
    """A pluggable classifier could not make a trusted decision."""


_ROUTES = frozenset({"ordinary", "professional"})
_MAX_HINT = 160
_MAX_CONTEXT = 1024
_DOMAIN_HINTS = (
    "电网", "潮流", "线路", "母线", "变压器", "拓扑", "约束", "越限",
    "n-1", "pandapower", "pypsa", "负载率", "短路", "孤岛", "收敛",
)


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
class TurnPlan:
    turn_id: str
    attempt_id: str
    route: str
    source: str
    plan_revision: str
    capability_hint: str | None
    context_snapshot: Mapping[str, object]
    fallback: bool = False

    def __post_init__(self) -> None:
        if not self.turn_id or not self.attempt_id or not self.plan_revision:
            raise ValueError("turn plan identity is invalid")
        if self.route not in _ROUTES:
            raise ValueError("turn plan route is invalid")
        if self.capability_hint is not None and len(self.capability_hint) > _MAX_HINT:
            raise ValueError("turn plan capability hint is too long")
        if len(str(dict(self.context_snapshot))) > _MAX_CONTEXT:
            raise ValueError("turn plan context snapshot is too large")

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "turn_id": self.turn_id,
            "attempt_id": self.attempt_id,
            "route": self.route,
            "source": self.source,
            "plan_revision": self.plan_revision,
            "context_snapshot": dict(self.context_snapshot),
            "fallback": self.fallback,
        }
        if self.capability_hint is not None:
            payload["capability_hint"] = self.capability_hint
        return payload


class TurnRouter(Protocol):
    def plan(self, claim: AttemptClaim) -> TurnPlan: ...


def _context_snapshot(claim: AttemptClaim) -> dict[str, object]:
    context = claim.model_context
    profiles = [
        {"profile_id": profile_id, "profile_version": version}
        for profile_id, version in context.enabled_profiles[:16]
    ]
    return {
        "model_id": context.model_id,
        "implementation_family": context.implementation_family,
        "selection_revision": context.selection_revision,
        "enabled_profiles": profiles,
    }


def _hint(claim: AttemptClaim) -> str | None:
    if claim.kind == "send_professional":
        return "domain_analysis"
    if claim.kind == "send_ordinary":
        return "general_conversation"
    return None


class DefaultTurnRouter:
    """Route explicit commands and auto commands with a safe policy fallback."""

    def __init__(
        self,
        *,
        decision_router: TurnRouter | None = None,
        ordinary_conversation_enabled: bool = True,
    ) -> None:
        if decision_router is self:
            raise ValueError("turn router cannot wrap itself")
        self._decision_router = decision_router
        self.ordinary_conversation_enabled = ordinary_conversation_enabled

    def plan(self, claim: AttemptClaim) -> TurnPlan:
        if claim.kind == "send_professional":
            intent = TurnIntent("professional", "explicit")
        elif claim.kind == "send_ordinary":
            intent = TurnIntent("ordinary", "explicit")
        elif claim.kind == "send_auto":
            if self._decision_router is None:
                intent = TurnIntent(
                    "professional" if any(
                        hint in claim.instruction.lower() for hint in _DOMAIN_HINTS
                    ) else "ordinary",
                    "heuristic",
                )
            else:
                try:
                    nested = self._decision_router.plan(claim)
                    intent = TurnIntent(nested.route, "classifier")
                except (DecisionUnavailable, ValueError, TypeError):
                    intent = TurnIntent("ordinary", "decision_unavailable")
                    return self._make(claim, intent, fallback=True)
        else:
            raise DecisionUnavailable("unsupported_turn_kind")
        if intent.route == "ordinary" and not self.ordinary_conversation_enabled:
            raise DecisionUnavailable("ordinary_conversation_disabled")
        return self._make(claim, intent)

    def _make(self, claim: AttemptClaim, intent: TurnIntent, *, fallback: bool = False) -> TurnPlan:
        if intent.route == "ordinary" and not self.ordinary_conversation_enabled:
            raise DecisionUnavailable("ordinary_conversation_disabled")
        return TurnPlan(
            turn_id=claim.attempt.turn_id,
            attempt_id=claim.attempt.attempt_id,
            route=intent.route,
            source=intent.source,
            plan_revision="turn-plan-v1",
            capability_hint=_hint(claim),
            context_snapshot=_context_snapshot(claim),
            fallback=fallback,
        )


class FakeDecisionRouter:
    """Deterministic fixture router used by tests and local demonstrations."""

    def __init__(self, decision: str | Callable[[str], str]) -> None:
        self._decision = decision

    def plan(self, claim: AttemptClaim) -> TurnPlan:
        value = self._decision(claim.instruction) if callable(self._decision) else self._decision
        if value not in _ROUTES:
            raise DecisionUnavailable("fake_decision_invalid")
        return TurnPlan(
            turn_id=claim.attempt.turn_id,
            attempt_id=claim.attempt.attempt_id,
            route=value,
            source="fake",
            plan_revision="turn-plan-v1",
            capability_hint=None,
            context_snapshot=_context_snapshot(claim),
        )


class JevDecisionRouter:
    """Optional low-latency Jev adapter without a hard dependency on Jev."""

    def __init__(self, classifier: Callable[[str], str], *, enabled: bool = False) -> None:
        if not callable(classifier):
            raise TypeError("Jev classifier must be callable")
        self.enabled = enabled
        self._classifier = classifier

    def plan(self, claim: AttemptClaim) -> TurnPlan:
        if not self.enabled:
            raise DecisionUnavailable("jev_disabled")
        try:
            route = self._classifier(claim.instruction[:16_384])
        except Exception as error:
            raise DecisionUnavailable("jev_unavailable") from error
        if route not in _ROUTES:
            raise DecisionUnavailable("jev_decision_invalid")
        return TurnPlan(
            turn_id=claim.attempt.turn_id,
            attempt_id=claim.attempt.attempt_id,
            route=route,
            source="jev",
            plan_revision="turn-plan-v1",
            capability_hint="domain_analysis" if route == "professional" else "general_conversation",
            context_snapshot=_context_snapshot(claim),
        )


__all__ = [
    "DecisionUnavailable", "DefaultTurnRouter", "FakeDecisionRouter", "JevDecisionRouter",
    "TurnIntent", "TurnPlan", "TurnRouter",
]
