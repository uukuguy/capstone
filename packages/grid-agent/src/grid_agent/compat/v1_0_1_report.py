"""Pandapower presentation adapter for the generic application runner."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from hashlib import sha256

from capability_agent.application.workspace import ApplicationWorkspace
from grid_agent.analysis.models import AnalysisContext, DomainState, InputRecord, RuntimeRecord, TurnRecord
from grid_agent.analysis.report import render_analysis_report
from grid_agent.analysis.workspace import AnalysisWorkspace
from grid_agent.compat.v1_0_1_submission import write_submission_checkpoint


class PandapowerApplicationReportShell:
    """Reuse the v1.0.1 reader report for generic application run records."""

    def __init__(self) -> None:
        self._submission_checkpoint_unavailable = False

    def prepare(
        self,
        *,
        questions: Iterable[str],
        workspace: ApplicationWorkspace,
    ) -> None:
        self._submission_checkpoint_unavailable = False
        self._refresh_submission_checkpoint(
            workspace=workspace,
            questions=questions,
            answers=(),
        )

    def render(
        self,
        *,
        questions: Iterable[str] = (),
        answers: Iterable[str] = (),
        context: object | None = None,
        core: Mapping[str, object] | None = None,
        workspace: ApplicationWorkspace | None = None,
        runtime: Mapping[str, object] | None = None,
        assurances: Iterable[str] = (),
        **_: object,
    ) -> str:
        question_values = tuple(_text_values(questions, "questions"))
        answer_values = tuple(_text_values(answers, "answers"))
        if workspace is None:
            raise RuntimeError("pandapower application report requires a workspace")
        self._refresh_submission_checkpoint(
            workspace=workspace,
            questions=question_values,
            answers=answer_values,
        )
        report_workspace = _analysis_workspace(workspace)
        report_context = _analysis_context(
            questions=question_values,
            answers=answer_values,
            context=context,
            core=core,
            workspace=report_workspace,
        )
        report = render_analysis_report(
            context=report_context,
            workspace=report_workspace,
            environment=_environment(context, runtime),
        )
        if self._submission_checkpoint_unavailable:
            report += "\n## Submission checkpoint diagnostic\n\n- Submission checkpoint unavailable; report processing continued.\n"
        assurance_values = tuple(_text_values(assurances, "assurances"))
        if assurance_values:
            report += "\n## Guarantee scope\n\n" + "\n".join(
                f"- {value}" for value in assurance_values
            ) + "\n"
        return report

    def _refresh_submission_checkpoint(
        self,
        *,
        workspace: ApplicationWorkspace,
        questions: Iterable[str],
        answers: Iterable[str],
    ) -> None:
        """Project the optional submission view without affecting the run."""
        try:
            write_submission_checkpoint(
                workspace=workspace,
                questions=questions,
                answers=answers,
            )
        except OSError:
            self._submission_checkpoint_unavailable = True


def _analysis_context(
    *,
    questions: tuple[str, ...],
    answers: tuple[str, ...],
    context: object | None,
    core: Mapping[str, object] | None,
    workspace: AnalysisWorkspace,
) -> AnalysisContext:
    generic_core = getattr(context, "core", None)
    turns = getattr(generic_core, "turns", ())
    input_payload = getattr(generic_core, "input", {})
    runtime_payload = getattr(generic_core, "runtime", {})
    run_id = str(getattr(context, "run_id", (core or {}).get("run_id", "run")))
    status = str(getattr(context, "status", "running"))
    if status not in {"initializing", "running", "completed", "failed"}:
        status = "running"
    report_turns = [
        _turn_record(index, question, answers, turns, run_id)
        for index, question in enumerate(questions, start=1)
        if index <= len(answers)
    ]
    return AnalysisContext(
        analysis_id=run_id,
        revision=int(getattr(context, "revision", len(report_turns))),
        state_hash=str(getattr(context, "state_hash", "")),
        status=status,
        input=InputRecord(
            copied_path=_text_mapping_value(input_payload, "copied_path", "input/questions.txt"),
            source_path=_text_mapping_value(input_payload, "source_path", "application request"),
            sha256=_sha256("\n".join(questions)),
            instruction_count=len(questions),
        ),
        runtime=RuntimeRecord(
            provider=_text_mapping_value(runtime_payload, "provider", "configured-provider"),
            model=_text_mapping_value(runtime_payload, "model", "configured-model"),
            grid_capability_protocol="grid-capability/1.0",
            pandapower_version=_text_mapping_value(runtime_payload, "pandapower_version", "3.4.0"),
        ),
        turns=report_turns,
        domain_state=_domain_state(context),
    )


def _turn_record(
    ordinal: int,
    question: str,
    answers: tuple[str, ...],
    generic_turns: object,
    run_id: str,
) -> TurnRecord:
    value = generic_turns[ordinal - 1] if isinstance(generic_turns, tuple | list) and len(generic_turns) >= ordinal else {}
    if not isinstance(value, Mapping):
        value = {}
    turn_id = _text_mapping_value(value, "turn_id", f"{run_id}-t{ordinal:03d}")
    answer_path = _text_mapping_value(value, "answer_path", f"turns/{turn_id}/answer.json")
    return TurnRecord(
        turn_id=turn_id,
        ordinal=ordinal,
        instruction=question,
        instruction_sha256=_text_mapping_value(value, "instruction_sha256", _sha256(question)),
        nonce_sha256=_text_mapping_value(value, "nonce_sha256", _sha256(turn_id)),
        status="success",
        answer_path=answer_path,
        answer_sha256=_text_mapping_value(value, "answer_sha256", _sha256(answers[ordinal - 1])),
        duration_seconds=_number_mapping_value(value, "duration_seconds"),
        consumed_refs=_string_values(value.get("result_refs", ())),
        produced_refs=_string_values(value.get("evidence_refs", ())),
    )


def _analysis_workspace(workspace: ApplicationWorkspace) -> AnalysisWorkspace:
    """Present generic artifact locations through the legacy report contract."""
    root = workspace.root
    return AnalysisWorkspace(
        analysis_id=workspace.run_id,
        root_path=root,
        manifest_path=root / "manifest.json",
        copied_instructions_path=root / "input" / "questions.txt",
        answers_path=workspace.output_path / "answers.jsonl",
        report_path=workspace.output_path / "report.md",
        context_snapshot_path=workspace.context_snapshot_path,
        context_events_path=workspace.context_events_path,
        trace_path=workspace.events_path,
        events_path=workspace.events_path,
        requests_path=workspace.core_path / "requests",
        projections_path=workspace.core_path / "projections",
        agent_projection_path=workspace.core_path / "agent-trajectory.json",
        business_projection_path=workspace.core_path / "business-trajectory.json",
        context_timeline_path=workspace.core_path / "context-timeline.json",
        artifact_index_path=workspace.artifacts_path,
        turns_path=workspace.turns_path,
        evidence_path=workspace.domains_path / "grid" / "artifacts",
        results_path=workspace.domains_path / "grid" / "tool-results",
        tool_results_path=workspace.domains_path / "grid" / "tool-results",
        bin_path=workspace.domains_path / "grid" / "runtime",
        pi_path=workspace.domains_path / "grid" / "runtime",
        active_turn_path=workspace.turns_path / "active-turn.json",
        active_answer_draft_path=workspace.turns_path / "active-answer-draft.json",
        context_view_path=workspace.context_snapshot_path,
        trajectory_capture_state_path=workspace.core_path / "trajectory-capture-state.json",
    )


def _domain_state(context: object | None) -> DomainState:
    domains = getattr(context, "domains", {})
    envelope = domains.get("grid") if isinstance(domains, Mapping) else None
    state = getattr(envelope, "state", {})
    if not isinstance(state, Mapping):
        return DomainState()
    body = {key: value for key, value in state.items() if key not in {"state_schema", "state_revision"}}
    try:
        return DomainState.model_validate(body)
    except Exception:
        return DomainState()


def _environment(
    context: object | None, runtime: Mapping[str, object] | None
) -> dict[str, str]:
    context_runtime = getattr(getattr(context, "core", None), "runtime", {})
    values = {
        key: value
        for key, value in context_runtime.items()
        if isinstance(key, str) and isinstance(value, str)
    } if isinstance(context_runtime, Mapping) else {}
    if isinstance(runtime, Mapping):
        values.update(
            {
                key: value
                for key, value in runtime.items()
                if isinstance(key, str) and isinstance(value, str)
            }
        )
    return values


def _text_values(values: Iterable[str], label: str) -> list[str]:
    result = list(values)
    if any(not isinstance(value, str) for value in result):
        raise TypeError(f"report {label} must contain text")
    return result


def _text_mapping_value(value: object, key: str, default: str) -> str:
    return str(value.get(key, default)) if isinstance(value, Mapping) and isinstance(value.get(key, default), str) else default


def _number_mapping_value(value: Mapping[str, object], key: str) -> float | None:
    candidate = value.get(key)
    return float(candidate) if isinstance(candidate, int | float) else None


def _string_values(values: object) -> list[str]:
    return [value for value in values if isinstance(value, str)] if isinstance(values, tuple | list) else []


def _sha256(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


__all__ = ["PandapowerApplicationReportShell"]
