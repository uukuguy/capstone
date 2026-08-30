"""Stable, frozen output models for the trajectory projection boundary."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal
import warnings

from pydantic import Field, model_validator

from capability_agent.trajectory.events import StrictFrozenModel


# ``schema`` is part of the public projection contract, but Pydantic also
# exposes a ``schema`` helper on BaseModel.  Silence only that known naming
# warning; do not hide validation warnings from other projection fields.
warnings.filterwarnings(
    "ignore",
    message=r'Field name "schema" in .* shadows an attribute in parent',
    category=UserWarning,
)


class _FrozenDict(dict[str, Any]):
    """A JSON-compatible dictionary that rejects every in-place mutation."""

    def __init__(self, values: Mapping[str, Any]) -> None:
        dict.__init__(self, values)

    def _immutable(self, *args: object, **kwargs: object) -> None:
        raise TypeError("mapping is immutable")

    __setitem__ = _immutable
    __delitem__ = _immutable
    __ior__ = _immutable  # type: ignore[reportAssignmentType]
    clear = _immutable
    pop = _immutable
    popitem = _immutable  # type: ignore[reportAssignmentType]
    setdefault = _immutable  # type: ignore[reportAssignmentType]
    update = _immutable  # type: ignore[reportAssignmentType]


class _FrozenList(list[Any]):
    """A JSON-compatible list that keeps ordinary list equality semantics."""

    def _immutable(self, *args: object, **kwargs: object) -> None:
        raise TypeError("sequence is immutable")

    __setitem__ = _immutable
    __delitem__ = _immutable
    __iadd__ = _immutable
    __imul__ = _immutable
    append = _immutable
    clear = _immutable
    extend = _immutable
    insert = _immutable
    pop = _immutable
    remove = _immutable
    reverse = _immutable
    sort = _immutable


def _deep_freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _FrozenDict({str(key): _deep_freeze(item) for key, item in value.items()})
    if isinstance(value, list | tuple):
        return tuple(_deep_freeze(item) for item in value)
    return value


def _deep_freeze_json(value: Any) -> Any:
    """Freeze arbitrary JSON while preserving list-shaped equality/encoding."""

    if isinstance(value, Mapping):
        return _FrozenDict(
            {str(key): _deep_freeze_json(item) for key, item in value.items()}
        )
    if isinstance(value, list | tuple):
        return _FrozenList(_deep_freeze_json(item) for item in value)
    return value


class BindingProjectionMetadata(StrictFrozenModel):
    """Controller-recorded identity for one application-local domain binding.

    Projection code treats these values as labels only.  They are copied from
    the run descriptor/manifest and never used to establish simulator truth.
    Keeping the binding identity beside every public projection prevents a
    workbench consumer from inferring an authority from a capability name.
    """

    binding_id: str = Field(min_length=1)
    domain_id: str = Field(min_length=1)
    domain_version: str = Field(min_length=1)
    authority_id: str = Field(min_length=1)
    schema: str = Field(min_length=1)
    presentation: Mapping[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def freeze_presentation(self) -> "BindingProjectionMetadata":
        object.__setattr__(self, "presentation", _deep_freeze(self.presentation))
        return self


class ApplicationProjectionMetadata(StrictFrozenModel):
    """Application and binding identity persisted with a generic run."""

    application_id: str = Field(min_length=1)
    application_version: str = Field(min_length=1)
    bindings: Mapping[str, BindingProjectionMetadata] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_and_freeze_bindings(self) -> "ApplicationProjectionMetadata":
        if any(key != value.binding_id for key, value in self.bindings.items()):
            raise ValueError("application binding metadata keys must match binding_id")
        object.__setattr__(self, "bindings", _deep_freeze(self.bindings))
        return self


class DomainPayloadView(StrictFrozenModel):
    """Opaque, already-validated domain output exposed for inspection only."""

    binding_id: str = Field(min_length=1)
    domain_id: str = Field(min_length=1)
    authority_id: str = Field(min_length=1)
    schema: str = Field(min_length=1)
    payload: Mapping[str, Any] = Field(default_factory=dict)
    interpretation: Literal["opaque"] = "opaque"
    presentation: Mapping[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def freeze_payload(self) -> "DomainPayloadView":
        object.__setattr__(self, "payload", _deep_freeze_json(self.payload))
        object.__setattr__(self, "presentation", _deep_freeze_json(self.presentation))
        return self


NodeSource = Literal["observed", "agent-declared", "derived"]
LifecycleStatus = Literal[
    "running", "completed", "failed", "interrupted", "unavailable"
]


class ProjectionNode(StrictFrozenModel):
    """The provenance fields shared by every projected node."""

    id: str = Field(min_length=1)
    source: NodeSource
    source_sequences: tuple[int, ...] = ()
    rule_id: str | None = Field(default=None, min_length=1)
    status: LifecycleStatus
    unavailable_reason: str | None = None
    # Optional because v0.2/native grid runs predate application identity.
    # ``exclude_if`` keeps their public JSON byte-compatible while allowing
    # generic application runs to carry explicit routing metadata.
    binding_id: str | None = Field(default=None, min_length=1, exclude_if=lambda value: value is None)
    domain_id: str | None = Field(default=None, min_length=1, exclude_if=lambda value: value is None)
    authority_id: str | None = Field(default=None, min_length=1, exclude_if=lambda value: value is None)
    schema: str | None = Field(default=None, min_length=1, exclude_if=lambda value: value is None)

    @model_validator(mode="after")
    def require_source_sequences(self) -> "ProjectionNode":
        if not self.source_sequences:
            raise ValueError("projection node requires source_sequences")
        if any(sequence < 1 for sequence in self.source_sequences):
            raise ValueError("source_sequences must contain positive sequence numbers")
        if self.source == "derived" and self.rule_id is None:
            raise ValueError("derived node requires rule_id")
        if self.source != "derived" and self.rule_id is not None:
            raise ValueError("observed or agent-declared node must not have rule_id")
        return self


class AgentRetry(ProjectionNode):
    attempt: int = Field(ge=1)
    max_attempts: int = Field(ge=1)
    delay_seconds: float | None = Field(default=None, ge=0)
    message: str | None = None

    @model_validator(mode="after")
    def require_valid_attempt(self) -> "AgentRetry":
        if self.attempt > self.max_attempts:
            raise ValueError("attempt must not exceed max_attempts")
        return self


class AssistantResponse(ProjectionNode):
    artifact_ref: str | None = None
    stop_reason: str | None = None
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    ttft_seconds: float | None = Field(default=None, ge=0)
    duration_seconds: float | None = Field(default=None, ge=0)


class ToolCall(ProjectionNode):
    tool_call_id: str = Field(min_length=1)
    capability: str = Field(min_length=1)
    start_sequence: int = Field(ge=1)
    end_sequence: int | None = Field(default=None, ge=1)
    artifact_ref: str | None = None
    ok: bool | None = None
    duration_seconds: float | None = Field(default=None, ge=0)
    result_refs: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()

    @model_validator(mode="after")
    def require_ordered_lifecycle(self) -> "ToolCall":
        if self.end_sequence is not None and self.end_sequence < self.start_sequence:
            raise ValueError("end_sequence must not precede start_sequence")
        return self


class ModelRequest(ProjectionNode):
    request_id: str = Field(min_length=1)
    artifact_ref: str | None = None
    retries: tuple[AgentRetry, ...] = ()
    response: AssistantResponse | None = None
    tools: tuple[ToolCall, ...] = ()


class AgentStep(ProjectionNode):
    step_id: str = Field(min_length=1)
    request: ModelRequest | None = None


class AgentTurn(ProjectionNode):
    turn_id: str = Field(min_length=1)
    ordinal: int | None = Field(default=None, ge=1)
    steps: tuple[AgentStep, ...] = ()


class AgentTrajectory(StrictFrozenModel):
    analysis_id: str = Field(min_length=1)
    turns: tuple[AgentTurn, ...] = ()
    binding: BindingProjectionMetadata | None = Field(
        default=None, exclude_if=lambda value: value is None
    )


class AgentEventRow(StrictFrozenModel):
    """One bounded public row from the nested agent trajectory."""

    id: str = Field(min_length=1)
    parent_id: str | None = Field(default=None, min_length=1)
    turn_id: str = Field(min_length=1)
    kind: str = Field(min_length=1, max_length=50)
    level: int = Field(ge=1)
    source_sequence: int = Field(ge=1)
    start_sequence: int | None = Field(default=None, ge=1)
    end_sequence: int | None = Field(default=None, ge=1)
    related_refs: tuple[str, ...] = ()
    source: NodeSource
    status: LifecycleStatus
    unavailable_reason: str | None = None
    title: str = Field(min_length=1, max_length=500)
    detail: str | None = Field(default=None, max_length=1_000)
    binding_id: str | None = Field(default=None, min_length=1, exclude_if=lambda value: value is None)
    domain_id: str | None = Field(default=None, min_length=1, exclude_if=lambda value: value is None)
    authority_id: str | None = Field(default=None, min_length=1, exclude_if=lambda value: value is None)
    schema: str | None = Field(default=None, min_length=1, exclude_if=lambda value: value is None)

    @model_validator(mode="after")
    def require_exact_tool_lifecycle_relation(self) -> "AgentEventRow":
        if self.kind != "tool":
            if self.start_sequence is not None or self.end_sequence is not None:
                raise ValueError("only tool rows may expose lifecycle sequence fields")
            return self
        if self.start_sequence is None:
            raise ValueError("tool row requires start_sequence")
        if self.end_sequence is not None and self.end_sequence < self.start_sequence:
            raise ValueError("tool row end_sequence must not precede start_sequence")
        relation_sequence = self.end_sequence or self.start_sequence
        if self.source_sequence != relation_sequence:
            raise ValueError("tool row source_sequence must be its recorded lifecycle relation")
        return self


class ExecutionLineage(StrictFrozenModel):
    """Exact bounded identities that justify an execution slice."""

    business_node_ids: tuple[str, ...] = ()
    artifact_refs: tuple[str, ...] = ()
    agent_node_ids: tuple[str, ...] = ()
    turn_ids: tuple[str, ...] = ()
    step_ids: tuple[str, ...] = ()
    request_ids: tuple[str, ...] = ()
    tool_call_ids: tuple[str, ...] = ()
    result_ids: tuple[str, ...] = ()


class ExecutionSlice(StrictFrozenModel):
    analysis_id: str = Field(min_length=1)
    source_sequence: int = Field(ge=1)
    turn: AgentTurn | None = None
    unavailable_reason: str | None = None
    lineage: ExecutionLineage | None = None

    @model_validator(mode="after")
    def require_unavailable_reason_for_missing_turn(self) -> "ExecutionSlice":
        if self.turn is None and not self.unavailable_reason:
            raise ValueError("unavailable_reason is required when turn is null")
        if self.turn is not None and self.unavailable_reason is not None:
            raise ValueError("unavailable_reason must be null when turn is present")
        if self.turn is None and self.lineage is not None:
            raise ValueError("lineage must be null when turn is null")
        if self.turn is not None and self.lineage is None:
            raise ValueError("lineage is required when turn is present")
        return self


class BusinessNode(ProjectionNode):
    kind: str = Field(min_length=1)
    title: str = Field(min_length=1)
    detail: str | None = None
    refs: tuple[str, ...] = ()
    payload: Mapping[str, Any] | None = Field(
        default=None, exclude_if=lambda value: value is None
    )

    @model_validator(mode="before")
    @classmethod
    def reject_unproven_derived_node(cls, value: Any) -> Any:
        if isinstance(value, dict) and value.get("source") == "derived":
            if not value.get("source_sequences") or not value.get("rule_id"):
                raise ValueError("derived node requires source_sequences and rule_id")
        return value

    @model_validator(mode="after")
    def freeze_payload(self) -> "BusinessNode":
        if self.payload is not None:
            object.__setattr__(self, "payload", _deep_freeze_json(self.payload))
        return self


class BusinessProblem(ProjectionNode):
    turn_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    nodes: tuple[BusinessNode, ...] = ()


class BusinessProblemSummary(StrictFrozenModel):
    """Bounded metadata repeated on causal rows for stable page reconstruction."""

    id: str = Field(min_length=1)
    source: NodeSource
    rule_id: str | None = Field(default=None, min_length=1)
    status: LifecycleStatus
    unavailable_reason: str | None = None
    turn_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    first_sequence: int = Field(ge=1)
    last_sequence: int = Field(ge=1)
    node_count: int = Field(ge=1)

    @model_validator(mode="after")
    def require_ordered_range_and_provenance(self) -> "BusinessProblemSummary":
        if self.last_sequence < self.first_sequence:
            raise ValueError("last_sequence must not precede first_sequence")
        if self.source == "derived" and self.rule_id is None:
            raise ValueError("derived problem summary requires rule_id")
        if self.source != "derived" and self.rule_id is not None:
            raise ValueError("observed problem summary must not have rule_id")
        return self


class BusinessCausalRow(StrictFrozenModel):
    """One cursor-addressable source sequence within a business problem."""

    id: str = Field(min_length=1)
    source_sequence: int = Field(ge=1)
    problem: BusinessProblemSummary
    nodes: tuple[BusinessNode, ...] = Field(min_length=1)
    binding_id: str | None = Field(default=None, min_length=1, exclude_if=lambda value: value is None)
    domain_id: str | None = Field(default=None, min_length=1, exclude_if=lambda value: value is None)
    authority_id: str | None = Field(default=None, min_length=1, exclude_if=lambda value: value is None)
    schema: str | None = Field(default=None, min_length=1, exclude_if=lambda value: value is None)
    domain_payload: DomainPayloadView | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    application_id: str | None = Field(
        default=None, min_length=1, exclude_if=lambda value: value is None
    )
    application_version: str | None = Field(
        default=None, min_length=1, exclude_if=lambda value: value is None
    )
    bindings: tuple[BindingProjectionMetadata, ...] = Field(
        default_factory=tuple, exclude_if=lambda value: not value
    )

    @model_validator(mode="after")
    def require_nodes_from_exact_sequence(self) -> "BusinessCausalRow":
        if any(node.source_sequences[0] != self.source_sequence for node in self.nodes):
            raise ValueError("causal row nodes must share their first source sequence")
        return self


class BusinessTrajectory(StrictFrozenModel):
    analysis_id: str = Field(min_length=1)
    problems: tuple[BusinessProblem, ...] = ()
    application: ApplicationProjectionMetadata | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    binding: BindingProjectionMetadata | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    domain_payload: DomainPayloadView | None = Field(
        default=None, exclude_if=lambda value: value is None
    )


class ContextFrame(ProjectionNode):
    source: NodeSource = "derived"
    status: LifecycleStatus = "completed"
    source_sequence: int = Field(ge=1)
    before_revision: int = Field(ge=0)
    after_revision: int = Field(ge=0)
    before_state_hash: str = Field(min_length=1)
    after_state_hash: str = Field(min_length=1)
    before_state: Mapping[str, Any]
    delta: Mapping[str, Any]
    after_state: Mapping[str, Any]
    request_artifact_ref: str | None = None

    @model_validator(mode="after")
    def require_consistent_frame(self) -> "ContextFrame":
        if self.before_revision > self.after_revision:
            raise ValueError("before_revision must not exceed after_revision")
        if self.source_sequences and self.source_sequence not in self.source_sequences:
            raise ValueError("source_sequences must include source_sequence")
        if self.request_artifact_ref is None and not self.unavailable_reason:
            raise ValueError("unavailable_reason is required when request_artifact_ref is null")
        return self

    @model_validator(mode="after")
    def freeze_states(self) -> "ContextFrame":
        object.__setattr__(self, "before_state", _deep_freeze(self.before_state))
        object.__setattr__(self, "delta", _deep_freeze(self.delta))
        object.__setattr__(self, "after_state", _deep_freeze(self.after_state))
        return self


class ContextCheckpoint(StrictFrozenModel):
    source_sequence: int = Field(ge=1)
    context_revision: int = Field(ge=0)
    state_hash: str = Field(min_length=1)
    state: Mapping[str, Any]

    @model_validator(mode="after")
    def freeze_state(self) -> "ContextCheckpoint":
        object.__setattr__(self, "state", _deep_freeze(self.state))
        return self


class ContextTimeline(StrictFrozenModel):
    analysis_id: str = Field(min_length=1)
    frames: tuple[ContextFrame, ...] = ()
    checkpoints: tuple[ContextCheckpoint, ...] = ()
    binding: BindingProjectionMetadata | None = Field(
        default=None, exclude_if=lambda value: value is None
    )

    def at_sequence(self, sequence: int) -> ContextFrame:
        for frame in self.frames:
            if frame.source_sequence == sequence:
                return frame
        raise KeyError(f"no context frame for sequence {sequence}")


class ContextFrameSummary(StrictFrozenModel):
    """Public context metadata that never embeds recorded state documents."""

    id: str = Field(min_length=1)
    source_sequence: int = Field(ge=1)
    before_revision: int = Field(ge=0)
    after_revision: int = Field(ge=0)
    changed: bool
    request_input_available: bool
    request_input_unavailable_reason: str | None = None
    event_kind: str = Field(min_length=1, max_length=100)
    binding_id: str | None = Field(default=None, min_length=1, exclude_if=lambda value: value is None)
    domain_id: str | None = Field(default=None, min_length=1, exclude_if=lambda value: value is None)
    authority_id: str | None = Field(default=None, min_length=1, exclude_if=lambda value: value is None)
    schema: str | None = Field(default=None, min_length=1, exclude_if=lambda value: value is None)

    @model_validator(mode="after")
    def require_request_input_availability_reason(self) -> "ContextFrameSummary":
        if self.request_input_available and self.request_input_unavailable_reason is not None:
            raise ValueError("available request input must not have an unavailable reason")
        if not self.request_input_available and not self.request_input_unavailable_reason:
            raise ValueError("unavailable request input requires a reason")
        return self


class ArtifactIndexRecord(ProjectionNode):
    source: NodeSource = "observed"
    status: LifecycleStatus = "completed"
    reference: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=1)
    verification_status: str = Field(min_length=1)
    producing_sequence: int | None = Field(default=None, ge=1)
    consuming_sequences: tuple[int, ...] = ()
    turn_id: str | None = None
    step_id: str | None = None
    request_id: str | None = None
    tool_call_id: str | None = None
    result_id: str | None = None
    evidence_id: str | None = None
    claim_id: str | None = None


class ArtifactIndex(StrictFrozenModel):
    analysis_id: str = Field(min_length=1)
    records: Mapping[str, ArtifactIndexRecord] = Field(default_factory=dict)
    binding: BindingProjectionMetadata | None = Field(
        default=None, exclude_if=lambda value: value is None
    )

    @model_validator(mode="after")
    def freeze_records(self) -> "ArtifactIndex":
        object.__setattr__(self, "records", _deep_freeze(self.records))
        return self


class ProjectionDiagnostic(ProjectionNode):
    source: NodeSource = "derived"
    status: LifecycleStatus = "unavailable"
    severity: Literal["info", "warning", "error"]
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)


class ProjectedRun(StrictFrozenModel):
    analysis_id: str = Field(min_length=1)
    source_fingerprint: str = Field(min_length=1)
    application: ApplicationProjectionMetadata | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    agent: AgentTrajectory
    business: BusinessTrajectory
    context: ContextTimeline
    artifacts: ArtifactIndex
    diagnostics: tuple[ProjectionDiagnostic, ...] = ()

    @property
    def application_metadata(self) -> ApplicationProjectionMetadata | None:
        """Compatibility spelling for consumers that call it metadata."""

        return self.application

    def binding_metadata(self, binding_id: str | None = None) -> BindingProjectionMetadata | None:
        """Return one explicit binding identity without guessing an authority."""

        if self.application is not None:
            if binding_id is not None:
                return self.application.bindings.get(binding_id)
            if len(self.application.bindings) == 1:
                return next(iter(self.application.bindings.values()))
        for trajectory in (self.agent, self.business, self.context, self.artifacts):
            binding = getattr(trajectory, "binding", None)
            if binding_id is None and binding is not None:
                return binding
            if binding is not None and binding.binding_id == binding_id:
                return binding
        return None


__all__ = [
    "ApplicationProjectionMetadata",
    "AgentEventRow",
    "AgentRetry",
    "AgentStep",
    "AgentTrajectory",
    "AgentTurn",
    "ArtifactIndex",
    "ArtifactIndexRecord",
    "AssistantResponse",
    "BusinessCausalRow",
    "BusinessNode",
    "BusinessProblem",
    "BusinessProblemSummary",
    "BusinessTrajectory",
    "BindingProjectionMetadata",
    "ContextCheckpoint",
    "ContextFrame",
    "ContextFrameSummary",
    "ContextTimeline",
    "DomainPayloadView",
    "ExecutionLineage",
    "ExecutionSlice",
    "LifecycleStatus",
    "ModelRequest",
    "NodeSource",
    "ProjectedRun",
    "ProjectionDiagnostic",
    "ProjectionNode",
    "ToolCall",
]
