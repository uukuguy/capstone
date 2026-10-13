"""Bounded, domain-neutral research records; never Authority facts."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

RecordId = Annotated[str, Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")]
Text = Annotated[str, Field(min_length=1, max_length=2000)]
Reference = Annotated[str, Field(min_length=1, max_length=256)]


class ResearchRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, hide_input_in_errors=True)

    @field_validator("*", mode="before")
    @classmethod
    def accept_json_arrays(cls, value):
        return tuple(value) if isinstance(value, list) else value


class ResearchClaim(ResearchRecord):
    claim_id: RecordId
    statement: Text
    status: Literal["pending", "supported", "refuted"] = "pending"
    refs: tuple[Reference, ...] = Field(default=(), max_length=32)

    @model_validator(mode="after")
    def require_sources(self):
        if self.status != "pending" and not self.refs:
            raise ValueError("supported or refuted claims require source references")
        return self


class ResearchNote(ResearchRecord):
    note_id: RecordId
    text: Text
    refs: tuple[Reference, ...] = Field(default=(), max_length=32)


class TaskProgress(ResearchRecord):
    """Explicit reader-facing work record, never an Authority claim."""
    kind: Literal["goal", "observation", "adjustment", "limitation"]
    text: Annotated[str, Field(min_length=1, max_length=1000)]
    refs: tuple[Reference, ...] = Field(default=(), max_length=32)
    step_id: RecordId | None = None
    phase: Literal["started", "updated", "completed"] | None = None

    @model_validator(mode="after")
    def require_step_phase(self):
        if (self.step_id is None) != (self.phase is None):
            raise ValueError("step_id and phase must be provided together")
        return self


def task_progress_tool_schema() -> dict[str, Any]:
    return TaskProgress.model_json_schema()


class ResearchChanges(ResearchRecord):
    goal: Annotated[str, Field(min_length=1, max_length=4000)] | None = None
    condition_refs: tuple[Reference, ...] | None = Field(default=None, max_length=32)
    claims: tuple[ResearchClaim, ...] | None = Field(default=None, max_length=64)
    open_questions: tuple[Text, ...] | None = Field(default=None, max_length=32)
    notes: tuple[ResearchNote, ...] | None = Field(default=None, max_length=64)

    @model_validator(mode="after")
    def validate_changes(self):
        if not self.model_fields_set or any(getattr(self, key) is None for key in self.model_fields_set):
            raise ValueError("research changes must contain non-null fields")
        for field, identity in (("claims", "claim_id"), ("notes", "note_id")):
            records = getattr(self, field) or ()
            ids = [getattr(item, identity) for item in records]
            if len(ids) != len(set(ids)):
                raise ValueError("research records contain duplicate identities")
        return self

    def references(self) -> tuple[str, ...]:
        refs = list(self.condition_refs or ())
        for item in (*(self.claims or ()), *(self.notes or ())):
            refs.extend(item.refs)
        return tuple(dict.fromkeys(refs))


class ResearchUpdate(ResearchRecord):
    request_id: RecordId
    expected_revision: int = Field(ge=0)
    changes: ResearchChanges


class ResearchRead(ResearchRecord):
    section: Literal["overview", "claims", "notes", "questions", "receipt"] = "overview"
    request_id: RecordId | None = None
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=8, ge=1, le=8)

    @model_validator(mode="after")
    def require_receipt_identity(self):
        if (self.section == "receipt") != (self.request_id is not None):
            raise ValueError("request_id is required only for receipt lookup")
        return self


def research_depth_tool_schema() -> dict[str, Any]:
    """Bound reasoning resource control without provider or model selection."""
    return {"type": "object", "additionalProperties": False, "required": ["level"],
            "properties": {"level": {"type": "string", "enum": ["off", "high"]}}}


def research_tool_schemas() -> tuple[dict[str, Any], dict[str, Any]]:
    """Publish one contract source while keeping request identity host-owned."""
    update = ResearchUpdate.model_json_schema()
    update["properties"].pop("request_id")
    update["required"].remove("request_id")
    return ResearchRead.model_json_schema(), update


class ResearchState(ResearchRecord):
    research_id: RecordId
    revision: int = Field(ge=1)
    goal: Annotated[str, Field(min_length=1, max_length=4000)]
    condition_refs: tuple[Reference, ...] = Field(default=(), max_length=32)
    claims: tuple[ResearchClaim, ...] = Field(default=(), max_length=64)
    open_questions: tuple[Text, ...] = Field(default=(), max_length=32)
    notes: tuple[ResearchNote, ...] = Field(default=(), max_length=64)


class ResearchReceipt(ResearchRecord):
    research_id: RecordId
    request_id: RecordId
    research_revision: int = Field(ge=1)
    event_sequence: int = Field(ge=1)
