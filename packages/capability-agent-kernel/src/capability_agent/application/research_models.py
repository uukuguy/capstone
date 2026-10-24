"""Bounded, domain-neutral research records; never Authority facts."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator
from capability_agent.runtime.capacity import runtime_limits as resolve_limits, check_capacity, runtime_limit_mode

RecordId = Annotated[str, Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")]
Text = Annotated[str, Field(min_length=1)]
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
    refs: tuple[Reference, ...] = ()

    @model_validator(mode="after")
    def require_sources(self):
        if self.status != "pending" and not self.refs:
            raise ValueError("supported or refuted claims require source references")
        return self


class ResearchNote(ResearchRecord):
    note_id: RecordId
    text: Text
    refs: tuple[Reference, ...] = ()


class TaskProgress(ResearchRecord):
    """Explicit reader-facing work record, never an Authority claim."""
    kind: Literal["goal", "observation", "adjustment", "limitation"]
    text: Annotated[str, Field(min_length=1)]
    refs: tuple[Reference, ...] = ()
    purpose: Annotated[str, Field(min_length=1, description="Concise purpose of the current execution action, in the user's language. State the intended work, not the whole task or an unverified outcome. Record it alongside dependent tool calls.")] | None = None
    step_id: RecordId | None = None
    phase: Literal["started", "updated", "completed"] | None = None

    @model_validator(mode="after")
    def require_step_phase(self, info: ValidationInfo):
        limits=resolve_limits((info.context or {}).get('runtime_limits'))
        _check_research_capacity(self.model_dump(exclude={'text'}), limits)
        check_capacity(limits,'research_progress_chars',len(self.text),unit='characters',phase='research_progress')
        if (self.step_id is None) != (self.phase is None):
            raise ValueError("step_id and phase must be provided together")
        return self


def task_progress_tool_schema(runtime_limits=None) -> dict[str, Any]:
    return _capacity_schema(TaskProgress.model_json_schema(), resolve_limits(runtime_limits))


class ResearchChanges(ResearchRecord):
    goal: Annotated[str, Field(min_length=1)] | None = None
    condition_refs: tuple[Reference, ...] | None = None
    claims: tuple[ResearchClaim, ...] | None = None
    open_questions: tuple[Text, ...] | None = None
    notes: tuple[ResearchNote, ...] | None = None

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

    @model_validator(mode='after')
    def validate_capacity(self, info: ValidationInfo):
        # Durable replay validates structure and identities, not a later
        # application's potentially smaller admission quota.
        if not (info.context or {}).get('skip_runtime_capacity'):
            _check_research_capacity(self.changes.model_dump(), resolve_limits((info.context or {}).get('runtime_limits')))
        return self


class ResearchRead(ResearchRecord):
    section: Literal["overview", "claims", "notes", "questions", "receipt"] = "overview"
    request_id: RecordId | None = None
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=8, ge=1)

    @model_validator(mode='before')
    @classmethod
    def select_default_page(cls,value,info:ValidationInfo):
        if isinstance(value,dict) and 'limit' not in value:
            value={**value,'limit':min(8,resolve_limits((info.context or {}).get('runtime_limits'))['research_page_records'])}
        return value

    @model_validator(mode="after")
    def require_receipt_identity(self, info: ValidationInfo):
        check_capacity(resolve_limits((info.context or {}).get('runtime_limits')), 'research_page_records', self.limit,
                       unit='records', phase='research_read')
        if (self.section == "receipt") != (self.request_id is not None):
            raise ValueError("request_id is required only for receipt lookup")
        return self


def research_depth_tool_schema() -> dict[str, Any]:
    """Bound reasoning resource control without provider or model selection."""
    return {"type": "object", "additionalProperties": False, "required": ["level"],
            "properties": {"level": {"type": "string", "enum": ["off", "high"]}}}


def research_tool_schemas(runtime_limits=None) -> tuple[dict[str, Any], dict[str, Any]]:
    """Publish one contract source while keeping request identity host-owned."""
    update = ResearchUpdate.model_json_schema()
    update["properties"].pop("request_id")
    update["required"].remove("request_id")
    limits = resolve_limits(runtime_limits)
    return _capacity_schema(ResearchRead.model_json_schema(), limits), _capacity_schema(update, limits)


class ResearchState(ResearchRecord):
    research_id: RecordId
    revision: int = Field(ge=1)
    goal: Annotated[str, Field(min_length=1)]
    condition_refs: tuple[Reference, ...] = ()
    claims: tuple[ResearchClaim, ...] = ()
    open_questions: tuple[Text, ...] = ()
    notes: tuple[ResearchNote, ...] = ()


class ResearchReceipt(ResearchRecord):
    research_id: RecordId
    request_id: RecordId
    research_revision: int = Field(ge=1)
    event_sequence: int = Field(ge=1)


_COLLECTION_LIMITS = {'claims': 'research_claim_count', 'notes': 'research_note_count',
    'open_questions': 'research_question_count', 'condition_refs': 'context_references', 'refs': 'context_references'}
_TEXT_LIMITS = {'goal': 'research_goal_chars', 'statement': 'research_text_chars',
    'text': 'research_text_chars', 'purpose': 'research_progress_chars'}


def precheck_research_capacity(value, runtime_limits=None, *, kind='update'):
    """Call before Pydantic so debug capacity errors cannot become validation errors."""
    limits=resolve_limits(runtime_limits)
    if not isinstance(value,dict):
        return
    if kind == 'read':
        amount=value.get('limit')
        if type(amount) is int:
            check_capacity(limits,'research_page_records',amount,unit='records',phase='research_read')
    elif kind == 'progress':
        if isinstance(value.get('text'),str):
            check_capacity(limits,'research_progress_chars',len(value['text']),unit='characters',phase='research_progress')
        _check_research_capacity({key:item for key,item in value.items() if key!='text'},limits)
    elif kind == 'update':
        _check_research_capacity(value.get('changes',{}),limits)
    else:
        raise ValueError('unknown research capacity operation')


def _check_research_capacity(value, limits):
    if not isinstance(value, dict):
        return
    for name, child in value.items():
        if name in _COLLECTION_LIMITS and isinstance(child, (tuple, list)):
            check_capacity(limits, _COLLECTION_LIMITS[name], len(child), unit='items', phase='research_update')
        if name in _TEXT_LIMITS and isinstance(child, str):
            check_capacity(limits, _TEXT_LIMITS[name], len(child), unit='characters', phase='research_update')
        if name == 'open_questions' and isinstance(child, (tuple, list)):
            for question in child:
                if isinstance(question,str):
                    check_capacity(limits, 'research_text_chars', len(question), unit='characters', phase='research_update')
        if isinstance(child, dict):
            _check_research_capacity(child, limits)
        elif isinstance(child, (tuple, list)):
            for item in child:
                _check_research_capacity(item, limits)


def _capacity_schema(schema, limits):
    debug=runtime_limit_mode()=='debug'
    def apply(node):
        if isinstance(node, dict):
            for name, field in node.get('properties', {}).items():
                variants = field.get('anyOf', [field])
                for variant in variants:
                    if variant.get('type') == 'array' and name in _COLLECTION_LIMITS:
                        if not debug:
                            variant['maxItems'] = limits[_COLLECTION_LIMITS[name]]
                        if name == 'open_questions':
                            if not debug:
                                variant['items']['maxLength'] = limits['research_text_chars']
                    if variant.get('type') == 'string' and name in _TEXT_LIMITS:
                        if not debug:
                            variant['maxLength'] = limits[_TEXT_LIMITS[name]]
                    if name == 'limit' and variant.get('type') == 'integer':
                        if not debug:
                            variant['maximum'] = limits['research_page_records']
                        variant['default'] = min(8,limits['research_page_records'])
            for child in node.values():
                apply(child)
        elif isinstance(node, list):
            for child in node:
                apply(child)
    apply(schema)
    if schema.get('title') == 'TaskProgress' and not debug:
        schema['properties']['text']['maxLength'] = limits['research_progress_chars']
    return schema
