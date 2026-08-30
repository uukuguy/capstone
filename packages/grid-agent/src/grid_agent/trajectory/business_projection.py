"""Pure business-facing projection with explicit event provenance."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Mapping, Sequence
from typing import Any, Literal

from grid_agent.trajectory.projection_models import (
    ApplicationProjectionMetadata,
    BusinessCausalRow,
    BusinessNode,
    BusinessProblem,
    BusinessProblemSummary,
    BusinessTrajectory,
    BindingProjectionMetadata,
    DomainPayloadView,
)
from capability_agent.trajectory.replay import ReplayEventLike
from pandapower_domain.presentation import (
    ArtifactResolver,
    PandapowerProjectionIntegrityError as ProjectionIntegrityError,
    is_verified_result_capability,
    require_verified_simulator_artifacts,
    semantic_tool_title as _pandapower_semantic_tool_title,
)


RULE_TOOL_ACTION = "tool-action/v1"
RULE_CONTEXT_CHANGE = "context-state-delta/v1"
RULE_VERIFIED_RESULT = "verified-simulator-result/v1"

def semantic_tool_title(capability: str) -> str:
    """Return the registered semantic title, preserving unknown identifiers verbatim."""
    return _pandapower_semantic_tool_title(capability)


def _payload(event: ReplayEventLike) -> dict[str, Any]:
    return dict(event.payload)


def _source(event: ReplayEventLike) -> Literal["observed", "agent-declared"]:
    return "agent-declared" if event.source.kind == "agent-declared" else "observed"


def _problem_for(
    problems: OrderedDict[str, list[BusinessNode]], event: ReplayEventLike
) -> list[BusinessNode] | None:
    turn_id = event.scope.turn_id
    if turn_id is None:
        return None
    return problems.setdefault(turn_id, [])


def _verified_result_node(
    event: ReplayEventLike, artifacts: ArtifactResolver
) -> BusinessNode:
    references = (*event.refs.produced, *event.refs.evidence)
    require_verified_simulator_artifacts(references, artifacts)
    return BusinessNode(
        id=f"business:{event.analysis_id}:{event.sequence}:result",
        source="observed",
        source_sequences=(event.sequence,),
        status="completed",
        kind="verified-result",
        title=semantic_tool_title(str(_payload(event)["capability"])),
        refs=tuple(references),
        rule_id=None,
    )


def _is_verified_result_capability(capability: str) -> bool:
    """Return whether a completed tool can establish a simulator result fact."""
    return is_verified_result_capability(capability)


def _accepted_submissions(
    events: Sequence[ReplayEventLike],
) -> dict[tuple[str | None, str], int]:
    return {
        (event.scope.turn_id, str(_payload(event)["submission_id"])): event.sequence
        for event in events
        if event.event_type == "answer.submitted"
    }


def project_business(
    events: Sequence[ReplayEventLike],
    artifacts: ArtifactResolver,
    *,
    application: ApplicationProjectionMetadata | None = None,
    binding: BindingProjectionMetadata | None = None,
    domain_payload: DomainPayloadView | None = None,
) -> BusinessTrajectory:
    """Project only explicit lifecycle/declaration records; answer prose is ignored."""
    problems: OrderedDict[str, list[BusinessNode]] = OrderedDict()
    analysis_id = events[0].analysis_id if events else "empty-analysis"
    accepted_submissions = _accepted_submissions(events)
    for event in events:
        nodes = _problem_for(problems, event)
        if nodes is None:
            continue
        payload = _payload(event)
        if event.event_type == "business.decision.declared":
            nodes.append(
                BusinessNode(
                    id=f"business:{event.analysis_id}:{event.sequence}:decision",
                    source="agent-declared",
                    source_sequences=(event.sequence,),
                    status="completed",
                    kind="decision",
                    title=str(payload["decision"]),
                    detail=str(payload["next_action"]),
                )
            )
        elif event.event_type == "business.claim.declared" and (
            submission_sequence := accepted_submissions.get(
                (event.scope.turn_id, str(payload["submission_id"]))
            )
        ) is not None:
            nodes.append(
                BusinessNode(
                    id=f"business:{event.analysis_id}:{event.sequence}:claim",
                    source="agent-declared",
                    source_sequences=(event.sequence, submission_sequence),
                    status="completed",
                    kind="claim",
                    title=str(payload["statement"]),
                    refs=tuple(
                        (
                            *payload.get("result_refs", ()),
                            *payload.get("evidence_refs", ()),
                        )
                    ),
                )
            )
        elif event.event_type in {"context.projected", "context.injected"}:
            nodes.append(
                BusinessNode(
                    id=f"business:{event.analysis_id}:{event.sequence}:context",
                    source="derived",
                    source_sequences=(event.sequence,),
                    rule_id=RULE_CONTEXT_CHANGE,
                    status="completed",
                    kind="context-change",
                    title="Context state changed",
                    refs=tuple(event.refs.produced),
                )
            )
        elif event.event_type in {"tool.completed", "tool.failed"}:
            capability = str(payload["capability"])
            status = (
                "completed"
                if event.event_type == "tool.completed"
                and payload.get("ok") is not False
                else "failed"
            )
            nodes.append(
                BusinessNode(
                    id=f"business:{event.analysis_id}:{event.sequence}:tool",
                    source="observed",
                    source_sequences=(event.sequence,),
                    status=status,
                    kind="tool-action",
                    title=semantic_tool_title(capability),
                    refs=tuple((*event.refs.produced, *event.refs.evidence)),
                )
            )
            if (
                status == "completed"
                and _is_verified_result_capability(capability)
                and (event.refs.produced or event.refs.evidence)
            ):
                nodes.append(_verified_result_node(event, artifacts))
        elif event.event_type in {
            "turn.failed",
            "step.failed",
            "model.response.failed",
            "answer.rejected",
        }:
            nodes.append(
                BusinessNode(
                    id=f"business:{event.analysis_id}:{event.sequence}:failure",
                    source=_source(event),
                    source_sequences=(event.sequence,),
                    status="failed",
                    kind="failure",
                    title=str(payload.get("message", event.event_type)),
                )
            )
        elif event.event_type == "audit.diagnostic.recorded":
            nodes.append(
                BusinessNode(
                    id=f"business:{event.analysis_id}:{event.sequence}:audit",
                    source="observed",
                    source_sequences=(event.sequence,),
                    status="completed",
                    kind="audit-finding",
                    title=str(payload["message"]),
                )
            )

    return BusinessTrajectory(
        analysis_id=analysis_id,
        problems=tuple(
            BusinessProblem(
                id=f"business:{analysis_id}:{turn_id}",
                source="derived",
                source_sequences=tuple(node.source_sequences[0] for node in nodes),
                rule_id="problem-grouping/v1",
                status="completed",
                turn_id=turn_id,
                title=turn_id,
                nodes=tuple(nodes),
            )
            for turn_id, nodes in problems.items()
            if nodes
        ),
        application=application,
        binding=binding,
        domain_payload=domain_payload,
    )


def project_domain_payload(
    *,
    analysis_id: str,
    binding_id: str,
    domain_id: str,
    authority_id: str,
    schema: str,
    payload: Mapping[str, Any],
    presentation: Mapping[str, Any] | None = None,
) -> DomainPayloadView:
    """Wrap a validated domain output without interpreting its business shape.

    Unknown domains are intentionally represented as opaque structured data.
    This helper does not validate or promote the payload to evidence; the
    selected Domain Pack and Kernel have already performed those duties.
    ``analysis_id`` is accepted to keep the projection call site symmetric
    with the grid projector and is deliberately not copied into the payload.
    """

    del analysis_id
    if not isinstance(payload, Mapping):
        raise TypeError("domain payload must be a mapping")
    return DomainPayloadView(
        binding_id=binding_id,
        domain_id=domain_id,
        authority_id=authority_id,
        schema=schema,
        payload=dict(payload),
        presentation={} if presentation is None else dict(presentation),
    )


def business_causal_rows(trajectory: BusinessTrajectory) -> tuple[BusinessCausalRow, ...]:
    """Flatten problem nodes into bounded, sequence-addressable API records."""
    rows: list[BusinessCausalRow] = []
    binding = trajectory.binding
    application = trajectory.application
    binding_fields = (
        {
            "binding_id": binding.binding_id,
            "domain_id": binding.domain_id,
            "authority_id": binding.authority_id,
            "schema": binding.schema,
        }
        if binding is not None
        else {}
    )
    application_fields = (
        {
            "application_id": application.application_id,
            "application_version": application.application_version,
            "bindings": tuple(application.bindings.values()),
        }
        if application is not None
        else {}
    )
    for problem in trajectory.problems:
        by_sequence: OrderedDict[int, list[BusinessNode]] = OrderedDict()
        for node in problem.nodes:
            by_sequence.setdefault(node.source_sequences[0], []).append(node)
        if not by_sequence:
            continue
        sequences = tuple(by_sequence)
        summary = BusinessProblemSummary(
            id=problem.id,
            source=problem.source,
            rule_id=problem.rule_id,
            status=problem.status,
            unavailable_reason=problem.unavailable_reason,
            turn_id=problem.turn_id,
            title=problem.title,
            first_sequence=min(sequences),
            last_sequence=max(sequences),
            node_count=len(problem.nodes),
        )
        rows.extend(
            BusinessCausalRow(
                id=f"{problem.id}:sequence:{sequence}",
                source_sequence=sequence,
                problem=summary,
                nodes=tuple(
                    node.model_copy(update=binding_fields) if binding_fields else node
                    for node in nodes
                ),
                **binding_fields,
                **application_fields,
            )
            for sequence, nodes in by_sequence.items()
        )

    # A domain output may be valid even when the Domain Pack has no semantic
    # business projector yet.  Keep it inspectable in the existing paged API,
    # but mark the row as a projection-only envelope rather than inventing a
    # domain event or interpreting the payload as a grid fact.
    if trajectory.domain_payload is not None:
        payload = trajectory.domain_payload
        payload_problem_id = f"domain-payload:{trajectory.analysis_id}:{payload.binding_id}"
        payload_problem = BusinessProblem(
            id=payload_problem_id,
            source="derived",
            source_sequences=(1,),
            rule_id="opaque-domain-payload/v1",
            status="completed",
            turn_id=f"binding:{payload.binding_id}",
            title=(
                str(payload.presentation.get("business_title"))
                if isinstance(payload.presentation.get("business_title"), str)
                and str(payload.presentation.get("business_title")).strip()
                else f"{payload.domain_id} payload"
            ),
            nodes=(
                BusinessNode(
                    id=f"{payload_problem_id}:view",
                    source="derived",
                    source_sequences=(1,),
                    rule_id="opaque-domain-payload/v1",
                    status="completed",
                    kind="domain-payload",
                    title="Opaque domain payload",
                    payload=payload.payload,
                ),
            )
        )
        payload_binding_fields = {
            "binding_id": payload.binding_id,
            "domain_id": payload.domain_id,
            "authority_id": payload.authority_id,
            "schema": payload.schema,
        }
        payload_nodes = tuple(
            node.model_copy(update=payload_binding_fields)
            for node in payload_problem.nodes
        )
        rows.append(
            BusinessCausalRow(
                id=f"{payload_problem_id}:sequence:1",
                source_sequence=1,
                problem=BusinessProblemSummary(
                    id=payload_problem.id,
                    source=payload_problem.source,
                    rule_id=payload_problem.rule_id,
                    status=payload_problem.status,
                    unavailable_reason=payload_problem.unavailable_reason,
                    turn_id=payload_problem.turn_id,
                    title=payload_problem.title,
                    first_sequence=1,
                    last_sequence=1,
                    node_count=1,
                ),
                nodes=payload_nodes,
                domain_payload=payload,
                **(
                    {
                        "binding_id": payload.binding_id,
                        "domain_id": payload.domain_id,
                        "authority_id": payload.authority_id,
                        "schema": payload.schema,
                    }
                ),
                **application_fields,
            )
        )
    return tuple(rows)


__all__ = [
    "ArtifactResolver",
    "ProjectionIntegrityError",
    "RULE_CONTEXT_CHANGE",
    "RULE_TOOL_ACTION",
    "RULE_VERIFIED_RESULT",
    "business_causal_rows",
    "project_domain_payload",
    "project_business",
    "semantic_tool_title",
]
