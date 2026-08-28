"""Compatibility exports for the neutral trajectory event protocol."""

from datetime import datetime

from capability_agent.trajectory.events import (
    DEFAULT_EVENT_PRODUCER,
    ZERO_PREDECESSOR_HASH,
    AnalysisTerminalPayload,
    AnswerPayload,
    Causation,
    ClaimPayload,
    ContextBoundary,
    ContextPayload,
    DecisionPayload,
    DiagnosticPayload,
    EmptyPayload,
    ErrorPayload,
    EventDraft,
    EventRefs,
    EventSource,
    EventType,
    ModelRequestPayload,
    ModelResponsePayload,
    PAYLOAD_MODELS,
    RetryPayload,
    RunEvent,
    RunScope,
    StrictFrozenModel,
    ToolPayload,
    TurnStartedPayload,
    TurnTerminalPayload,
    build_event as _build_event,
)


LEGACY_EVENT_PRODUCER = "grid-agent"
LEGACY_EVENT_SCHEMA_VERSION = "grid-run-event/1.0"


def build_event(
    draft: EventDraft,
    *,
    analysis_id: str,
    sequence: int,
    timestamp: datetime,
    previous_event_hash: str,
) -> RunEvent:
    """Build a legacy grid event while preserving the neutral kernel API."""
    if draft.source.producer == DEFAULT_EVENT_PRODUCER:
        draft = draft.model_copy(
            update={
                "source": draft.source.model_copy(
                    update={"producer": LEGACY_EVENT_PRODUCER}
                )
            }
        )
    return _build_event(
        draft,
        analysis_id=analysis_id,
        sequence=sequence,
        timestamp=timestamp,
        previous_event_hash=previous_event_hash,
        schema_version=LEGACY_EVENT_SCHEMA_VERSION,
    )


__all__ = [
    "ZERO_PREDECESSOR_HASH",
    "DEFAULT_EVENT_PRODUCER",
    "LEGACY_EVENT_PRODUCER",
    "LEGACY_EVENT_SCHEMA_VERSION",
    "StrictFrozenModel",
    "EmptyPayload",
    "AnalysisTerminalPayload",
    "ErrorPayload",
    "TurnStartedPayload",
    "TurnTerminalPayload",
    "ModelRequestPayload",
    "ModelResponsePayload",
    "RetryPayload",
    "ToolPayload",
    "DecisionPayload",
    "ClaimPayload",
    "ContextPayload",
    "AnswerPayload",
    "DiagnosticPayload",
    "PAYLOAD_MODELS",
    "EventType",
    "RunScope",
    "Causation",
    "EventSource",
    "ContextBoundary",
    "EventRefs",
    "EventDraft",
    "RunEvent",
    "build_event",
]
