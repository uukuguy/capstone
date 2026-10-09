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
from .request_intent import IntentDecision, IntentRequest


class DecisionUnavailable(RuntimeError):
    """A pluggable classifier could not make a trusted decision."""


_ROUTES = frozenset({"ordinary", "professional"})
_MAX_HINT = 160
_MAX_CONTEXT = 1024
_MAX_ROUTING_TEXT = 2_048
@dataclass(frozen=True, slots=True)
class RouterConfig:
    mode: str = "off"
    model: str = "none"
    schema: str = "capstone-routing-decision/1"

    def __post_init__(self) -> None:
        if self.mode not in {"off", "semantic", "heuristic", "jev_active", "jev_shadow"}:
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
    intent_decision: IntentDecision | None = None
    intent_engine: Mapping[str, object] | None = None
    intent_request: IntentRequest | None = field(default=None, repr=False)
    intent_resources: Mapping[str, object] | None = field(default=None, repr=False)

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
        if self.intent_decision is not None:
            payload['intent_decision'] = self.intent_decision.to_document()
            payload['intent_engine'] = dict(self.intent_engine or {})
        if self.intent_resources is not None:
            contexts = list(self.intent_resources.get('business_contexts', {}).values())
            if 'business_context' in self.intent_resources:
                contexts.append(self.intent_resources['business_context'])
            objects = {item['object_id']: {'object_id': item['object_id'], 'display_name': item['display_name'],
                'version': item['version']} for context in contexts for item in context['object_refs']}
            if self.intent_request is not None and self.intent_decision is not None:
                source = self.intent_request.to_document()
                business = [goal for goal in self.intent_decision.execution_goals if goal['operation'] in {'business_read', 'business_execute'}]
                refs = {ref for goal in business for ref in goal['object_refs']}
                if business:
                    refs.add(self.intent_resources.get('current_object_id'))
                for item in source['objects']:
                    if item['object_id'] in refs:
                        objects[item['object_id']] = {'object_id': item['object_id'],
                            'display_name': item.get('display_name', item.get('model_id', item['object_id'])),
                            'version': item.get('model_revision')}
            payload['accepted_context'] = {'objects': list(objects.values())[:16], 'materials': [],
                'full_model_tables': False, 'truncated': len(objects) > 16}
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
    """Support explicit compatibility routes; auto requires an injected node."""

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
                raise DecisionUnavailable('intent_recognizer_unavailable')
            else:
                try:
                    nested = self._decision_router.plan(routing_input)
                    intent = TurnIntent(nested.route, nested.source, nested.confidence)
                except Exception:
                    raise DecisionUnavailable('intent_recognition_failed') from None
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
