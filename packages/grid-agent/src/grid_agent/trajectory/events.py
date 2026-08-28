"""Compatibility exports for the neutral trajectory event protocol."""

from datetime import datetime
from typing import Any

from pydantic import model_validator

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
    RunEvent as NeutralRunEvent,
    RunScope,
    StrictFrozenModel,
    ToolPayload,
    TurnStartedPayload,
    TurnTerminalPayload,
    build_event as _build_event,
)
from grid_agent.trajectory.schema_policy import (
    GRID_EVENT_PRODUCER,
    GRID_EVENT_SCHEMA_VERSION,
    require_grid_event_producer,
)


LEGACY_EVENT_PRODUCER = GRID_EVENT_PRODUCER
LEGACY_EVENT_SCHEMA_VERSION = GRID_EVENT_SCHEMA_VERSION


class RunEvent(NeutralRunEvent):
    @model_validator(mode="after")
    def require_grid_identity(self) -> "RunEvent":
        if self.schema_version != LEGACY_EVENT_SCHEMA_VERSION:
            raise ValueError(
                f"grid event schema must be {LEGACY_EVENT_SCHEMA_VERSION}"
            )
        require_grid_event_producer(self.source.producer)
        return self

    @classmethod
    def __get_pydantic_json_schema__(
        cls,
        core_schema: Any,
        handler: Any,
    ) -> dict[str, Any]:
        schema = handler(core_schema)
        schema["properties"]["schema_version"] = {
            "const": LEGACY_EVENT_SCHEMA_VERSION,
            "title": "Schema Version",
            "type": "string",
        }
        return schema


def build_event(
    draft: EventDraft,
    *,
    analysis_id: str,
    sequence: int,
    timestamp: datetime,
    previous_event_hash: str,
    schema_version: str = LEGACY_EVENT_SCHEMA_VERSION,
) -> RunEvent:
    """Build a legacy grid event while preserving the neutral kernel API."""
    if schema_version != LEGACY_EVENT_SCHEMA_VERSION:
        raise ValueError(f"grid event schema must be {LEGACY_EVENT_SCHEMA_VERSION}")
    if draft.source.producer == DEFAULT_EVENT_PRODUCER:
        draft = draft.model_copy(
            update={
                "source": draft.source.model_copy(
                    update={"producer": LEGACY_EVENT_PRODUCER}
                )
            }
        )
    neutral_event = _build_event(
        draft,
        analysis_id=analysis_id,
        sequence=sequence,
        timestamp=timestamp,
        previous_event_hash=previous_event_hash,
        schema_version=schema_version,
    )
    return RunEvent.model_validate(neutral_event.model_dump(mode="json"))


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
