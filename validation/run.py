#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import cast

from pydantic import JsonValue, ValidationError

from capability_agent.application import (
    ActiveTurnHandle,
    ApplicationContextStore,
    ApplicationInvocationProjector,
    ApplicationProfile,
    ApplicationOutcome,
    CredentialScope,
    ApplicationWorkspace,
    DomainRegistry,
    FinalizedTurn,
    PreparedApplication,
    PreparedBinding,
    TurnController,
    prepare_application,
)
from capability_agent.application.composition import CredentialBroker
from capability_agent.application.context_models import PORTABLE_ID_PATTERN
from capability_agent.application.errors import AnswerCommitError
from capability_agent.domain.provisioning import CredentialLease
from capability_agent.tools.catalog import (
    BoundDomainCatalog,
    BoundToolDocument,
    CompositeToolCatalog,
    CoreToolCatalog,
)
from capability_agent.trajectory.answers import AnswerClaim
from grid_agent.application.composition import build_generic_application, run_generic_application
from grid_agent.application.registry import ApplicationRegistry
from grid_agent.application.workspace import RunWorkspace
from grid_agent.contracts import AnswerEnvelope
from grid_agent.knowledge.offline import answer_diagnostic, answer_information, plan_diagnostic
from grid_agent.simulator.client import GridctlClient, SimulatorCapabilityError
from grid_agent.simulator.locator import GridctlLocator
from grid_agent.validation.cases import ValidationCase, load_cases
from grid_agent.validation.corpus import AnswerCorpus, AnswerCorpusError, evaluate_corpus_trace, load_answer_corpus
from grid_agent.validation.oracles import ORACLES, ToolResultEvent
from pandapower_domain.provisioning import PandapowerRuntimeProvisioner


_OPERATION_CAPABILITIES = {
    "element.resolve": "model.element.get",
    "powerflow.run_ac": "analysis.powerflow.ac.run",
}
SemanticEventCallback = Callable[[Mapping[str, object], int | None], None]


@dataclass(frozen=True)
class ApplicationExecution:
    """Inspectable result of one provider-free generic application run."""

    case: Mapping[str, object]
    outcome: ApplicationOutcome
    workspace: ApplicationWorkspace
    store: ApplicationContextStore
    transport: "ScriptedApplicationTransport"
    controller: "AuditingTurnController"
    prepared: PreparedApplication


class ScriptedApplicationTransport:
    """Deterministic model transport that calls only the prepared endpoint.

    The transport is deliberately a model-side test double.  It receives a
    prepared binding and dispatches the case's semantic capability plan to the
    binding executor; no simulator implementation or expected answer is
    imported here.
    """

    def __init__(
        self,
        case: Mapping[str, object],
        *,
        prepared: PreparedApplication,
        catalog: CompositeToolCatalog,
    ) -> None:
        self.case = case
        self.run_id = str(case["run_id"])
        self._binding: PreparedBinding = prepared.bindings["grid"]
        self._tool_by_capability: dict[str, BoundToolDocument] = {
            tool.key.capability_id: tool for tool in catalog.domain_tools
        }
        runtime = self._binding.runtime
        self._projector_by_capability: dict[str, tuple[str, str | None]] = {}
        for document in runtime.capability_documents:
            capability = document.get("id")
            effect = document.get("context_effect")
            if not isinstance(capability, str) or not isinstance(effect, Mapping):
                continue
            projector = effect.get("projector")
            result_kind = effect.get("result_kind")
            if isinstance(projector, str) and projector:
                self._projector_by_capability[capability] = (
                    projector,
                    result_kind if isinstance(result_kind, str) else None,
                )
        self._question_index = 0
        self._context_ref: str | None = None
        self._result_ref: str | None = None
        self._asset_ref: str | None = None
        self._current_result_refs: tuple[str, ...] = ()
        self._current_evidence_refs: tuple[str, ...] = ()
        self.all_result_refs: list[str] = []
        self.all_evidence_refs: list[str] = []
        self.calls: list[dict[str, object]] = []
        self.semantic_events: list[Mapping[str, object]] = []
        self.started = False
        self.stopped = False

    @property
    def current_result_refs(self) -> tuple[str, ...]:
        return self._current_result_refs

    @property
    def current_evidence_refs(self) -> tuple[str, ...]:
        return self._current_evidence_refs

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True

    def prompt_and_wait(
        self,
        question: str,
        *,
        on_semantic_event: SemanticEventCallback | None = None,
        correlation_id: str | None = None,
        on_heartbeat: Callable[[], None] | None = None,
    ) -> str:
        questions = self.case.get("questions")
        if not isinstance(questions, list) or self._question_index >= len(questions):
            raise RuntimeError("scripted application received an unexpected question")
        scripted = questions[self._question_index]
        if not isinstance(scripted, Mapping) or scripted.get("text") != question:
            raise RuntimeError("scripted application question order changed")
        if not isinstance(correlation_id, str) or not correlation_id:
            raise RuntimeError("scripted application turn identity is missing")

        if on_heartbeat is not None:
            on_heartbeat()

        self._current_result_refs = ()
        self._current_evidence_refs = ()
        steps = scripted.get("steps")
        if not isinstance(steps, list):
            raise RuntimeError("scripted application question has invalid semantic steps")
        for step in steps:
            if not isinstance(step, Mapping):
                raise RuntimeError("scripted application step is invalid")
            capability = step.get("capability")
            arguments = step.get("arguments", {})
            if not isinstance(capability, str) or not capability:
                raise RuntimeError("scripted application capability is invalid")
            if not isinstance(arguments, Mapping):
                raise RuntimeError("scripted application arguments are invalid")
            resolved_arguments = _resolve_scripted_arguments(
                arguments,
                context_ref=self._context_ref,
                result_ref=self._result_ref,
                asset_ref=self._asset_ref,
            )
            self._invoke(
                capability,
                resolved_arguments,
                turn_id=correlation_id,
                on_semantic_event=on_semantic_event,
            )
        self._question_index += 1
        return (
            "scripted semantic execution completed for question "
            f"{self._question_index}: {question}"
        )

    def _invoke(
        self,
        capability: str,
        arguments: dict[str, object],
        *,
        turn_id: str,
        on_semantic_event: SemanticEventCallback | None,
    ) -> dict[str, object]:
        try:
            tool = self._tool_by_capability[capability]
        except KeyError as exc:
            raise RuntimeError(f"scripted capability is not published: {capability}") from exc
        projector_info = self._projector_by_capability.get(capability)
        if projector_info is None:
            raise RuntimeError(f"scripted capability has no projector contract: {capability}")
        call_id = f"{self.run_id}-call-{len(self.calls) + 1:03d}"
        key = {
            "binding_id": tool.key.binding_id,
            "capability_id": tool.key.capability_id,
        }
        start = {
            "type": "tool_execution_start",
            "call_id": call_id,
            "tool_name": tool.name,
            "capability": capability,
            "capability_key": key,
            "arguments": arguments,
            "run_id": self.run_id,
            "turn_id": turn_id,
        }
        self.semantic_events.append(start)
        _emit_scripted_event(on_semantic_event, start, len(self.semantic_events))

        endpoint = getattr(self._binding, "endpoint", None)
        executor = getattr(endpoint, "executor", None)
        invoke = getattr(executor, "invoke", None)
        if not callable(invoke):
            raise RuntimeError("prepared binding endpoint does not expose invoke")
        result = invoke(capability, dict(arguments))
        if not isinstance(result, Mapping):
            raise RuntimeError("simulator capability returned a non-object")
        normalized = dict(result)
        # context.open intentionally returns semantic_sha256 rather than a
        # second revision field.  The revision is the same simulator-issued
        # content digest and is added only to the transport event consumed by
        # the generic projector.
        if capability == "context.open" and "revision_ref" not in normalized:
            semantic_sha = normalized.get("semantic_sha256")
            if not isinstance(semantic_sha, str) or not semantic_sha:
                raise RuntimeError("context.open did not return a semantic digest")
            normalized["revision_ref"] = f"revision:sha256:{semantic_sha}"
        result_refs = _digest_refs(normalized, "result:sha256:")
        evidence_refs = _digest_refs(normalized, "evidence:sha256:")
        projector_id, result_kind = projector_info
        completed: dict[str, object] = {
            "type": "tool_result",
            "call_id": call_id,
            "tool_name": tool.name,
            "capability": capability,
            "capability_key": key,
            "ok": True,
            "result": normalized,
            "result_refs": list(result_refs),
            "evidence_refs": list(evidence_refs),
            "projector_id": projector_id,
            "run_id": self.run_id,
            "turn_id": turn_id,
        }
        if result_kind is not None:
            completed["result_kind"] = result_kind
        self.semantic_events.append(completed)
        _emit_scripted_event(on_semantic_event, completed, len(self.semantic_events))

        self.calls.append(
            {
                "capability": capability,
                "arguments": dict(arguments),
                "result": normalized,
                "result_refs": result_refs,
                "evidence_refs": evidence_refs,
            }
        )
        self._current_result_refs = _ordered_unique(
            (*self._current_result_refs, *result_refs)
        )
        self._current_evidence_refs = _ordered_unique(
            (*self._current_evidence_refs, *evidence_refs)
        )
        self.all_result_refs = list(_ordered_unique((*self.all_result_refs, *result_refs)))
        self.all_evidence_refs = list(
            _ordered_unique((*self.all_evidence_refs, *evidence_refs))
        )
        context_ref = normalized.get("context_ref")
        if isinstance(context_ref, str):
            self._context_ref = context_ref
        result_ref = normalized.get("result_ref")
        if isinstance(result_ref, str):
            self._result_ref = result_ref
        asset_ref = _preferred_asset_ref(normalized)
        if asset_ref is not None:
            self._asset_ref = asset_ref
        return normalized


class AuditingTurnController(TurnController):
    """Pass scripted current-turn refs through the real answer audit."""

    def __init__(
        self,
        *,
        transport: ScriptedApplicationTransport,
        store: ApplicationContextStore,
        workspace: ApplicationWorkspace,
        bindings: Mapping[str, object],
    ) -> None:
        super().__init__(store=store, workspace=workspace, bindings=bindings)
        self.transport = transport
        self.finalized_turns: list[FinalizedTurn] = []

    def submit(
        self,
        handle: ActiveTurnHandle,
        *,
        answer_output: str,
        referenced_bindings: Iterable[str] = (),
        result_refs: Iterable[str] = (),
        evidence_refs: Iterable[str] = (),
        claims: Iterable[AnswerClaim | Mapping[str, object]] = (),
        duration_seconds: float,
        submission_id: str | None = None,
    ) -> FinalizedTurn:
        del referenced_bindings, result_refs, evidence_refs, claims, submission_id
        result_refs = self.transport.current_result_refs
        evidence_refs = self.transport.current_evidence_refs
        references = (*result_refs, *evidence_refs)
        selected_bindings: tuple[str, ...] = ()
        claims: tuple[dict[str, object], ...] = ()
        if references:
            category = "evidence" if evidence_refs else "numerical_result"
            claims = (
                {
                    "statement": answer_output,
                    "category": category,
                    "result_refs": result_refs,
                    "evidence_refs": evidence_refs,
                },
            )
            selected_bindings = ("grid",)
        finalized = super().submit(
            handle,
            answer_output=answer_output,
            referenced_bindings=selected_bindings,
            result_refs=result_refs,
            evidence_refs=evidence_refs,
            claims=claims,
            duration_seconds=duration_seconds,
        )
        self.finalized_turns.append(finalized)
        return finalized


def _remove_generated_application_run(runs_root: Path, run_id: str) -> None:
    """Remove exactly one validated generated run directory, if present."""

    candidate = _validated_generated_run_path(runs_root, run_id)
    try:
        metadata = candidate.lstat()
    except FileNotFoundError:
        return
    except OSError as exc:
        raise ValueError("generated application run path cannot be inspected") from exc
    if stat.S_ISLNK(metadata.st_mode):
        raise ValueError("generated application run path must not be a symlink")
    if not stat.S_ISDIR(metadata.st_mode):
        raise ValueError("generated application run path must be a directory")
    shutil.rmtree(candidate)


def _validated_generated_run_path(runs_root: Path, run_id: str) -> Path:
    """Resolve and contain a generated run path before any destructive action."""

    if not isinstance(runs_root, Path):
        raise ValueError("runs root must be a path")
    if not isinstance(run_id, str) or not PORTABLE_ID_PATTERN.fullmatch(run_id):
        raise ValueError("application run identifier must be a portable identifier")
    try:
        root = Path(os.path.abspath(os.fspath(runs_root)))
    except (TypeError, ValueError, OSError) as exc:
        raise ValueError("runs root is invalid") from exc
    _reject_cleanup_symlink_ancestors(root, label="runs root")
    candidate = root / run_id
    _reject_cleanup_symlink_ancestors(candidate, label="generated application run")
    try:
        resolved_root = root.resolve(strict=False)
        resolved_candidate = candidate.resolve(strict=False)
        if resolved_candidate.parent != resolved_root:
            raise ValueError("generated application run path escapes runs root")
    except ValueError:
        raise
    except OSError as exc:
        raise ValueError("generated application run path cannot be resolved") from exc
    return candidate


def _reject_cleanup_symlink_ancestors(path: Path, *, label: str) -> None:
    """Reject symlinks and non-directory ancestors, including missing roots."""

    current = path
    while True:
        try:
            metadata = current.lstat()
        except FileNotFoundError:
            parent = current.parent
            if parent == current:
                return
            current = parent
            continue
        except OSError as exc:
            raise ValueError(f"{label} cannot be inspected") from exc
        if stat.S_ISLNK(metadata.st_mode):
            raise ValueError(f"{label} must not contain a symlink")
        if not stat.S_ISDIR(metadata.st_mode):
            raise ValueError(f"{label} must be a directory")
        parent = current.parent
        if parent == current:
            return
        current = parent


def _with_pandapower_timeout(
    profile: ApplicationProfile,
    timeout_seconds: float,
) -> ApplicationProfile:
    """Clone the first-domain profile with the validation timeout threaded through."""

    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    bindings = []
    for binding in profile.domains:
        provisioner = binding.profile.provisioner
        if not isinstance(provisioner, PandapowerRuntimeProvisioner):
            raise ValueError("pandapower application provisioner is unavailable")
        configured = PandapowerRuntimeProvisioner(
            executable=provisioner.executable,
            repository_root=provisioner.repository_root,
            environ=provisioner.environ,
            timeout_seconds=timeout_seconds,
            max_output_bytes=provisioner.max_output_bytes,
        )
        bindings.append(
            replace(
                binding,
                profile=replace(binding.profile, provisioner=configured),
            )
        )
    return replace(profile, domains=tuple(bindings))


def execute_application_case(
    case: Path | Mapping[str, object],
    *,
    runs_root: Path,
    timeout_seconds: float = 60.0,
) -> ApplicationExecution:
    """Run one JSON scripted case through the generic application entry point."""

    document = _load_application_document(case)
    application_id = str(document["application_id"])
    run_id = str(document["run_id"])
    _remove_generated_application_run(runs_root, run_id)

    from grid_agent.application.profile import build_pandapower_application_profile

    profile = _with_pandapower_timeout(
        build_pandapower_application_profile(),
        timeout_seconds,
    )
    if profile.manifest.application_id != application_id:
        raise ValueError("application case targets an unregistered application")
    registry = ApplicationRegistry()
    registry.register(
        profile.manifest.application_id,
        profile.manifest.version,
        lambda profile=profile: profile,
    )
    domain_registry = DomainRegistry()
    for binding in profile.domains:
        manifest = binding.profile.manifest
        domain_registry.register(
            manifest.domain_id,
            manifest.version,
            lambda profile=binding.profile: profile,
        )

    workspace = ApplicationWorkspace.create(
        Path(runs_root),
        run_id=run_id,
        binding_ids=tuple(binding.binding_id for binding in profile.domains),
    )
    prepared = prepare_application(
        profile,
        registry=domain_registry,
        workspace=workspace.root,
        credentials=_EmptyApplicationCredentialBroker(),
    )
    binding = prepared.bindings["grid"]
    adapter = binding.binding.profile.state_adapter
    schema_id = getattr(adapter, "schema_id", None)
    if not isinstance(schema_id, str) or not schema_id:
        raise ValueError("pandapower binding does not expose a state schema")
    questions = tuple(
        str(question["text"])
        for question in cast(list[Mapping[str, object]], document["questions"])
    )
    store = ApplicationContextStore.initialize(
        workspace,
        domains={"grid": schema_id},
        core={
            "input": {
                "application_id": application_id,
                "case_id": document["case_id"],
                "questions": list(questions),
            },
            "runtime": {
                "mode": "application-instantiation",
                "provider": "scripted",
                "model": "deterministic",
            },
        },
    )
    domain_catalog = BoundDomainCatalog.from_prepared(binding)
    catalog = CompositeToolCatalog.build(
        core=CoreToolCatalog.default(namespace="agent_"),
        domains=(domain_catalog,),
    )
    transport = ScriptedApplicationTransport(
        document,
        prepared=prepared,
        catalog=catalog,
    )
    projector = ApplicationInvocationProjector(
        store=store,
        catalog=catalog,
        bindings=prepared.bindings,
    )
    controller = AuditingTurnController(
        transport=transport,
        store=store,
        workspace=workspace,
        bindings=prepared.bindings,
    )
    application = build_generic_application(
        application_id,
        version=profile.manifest.version,
        registry=registry,
        prepared_application=prepared,
        provider=transport,
        workspace=workspace,
        store=store,
        turn_controller=controller,
        projector=projector,
        catalog=catalog,
    )
    outcome = run_generic_application(
        application_id,
        questions,
        application=application,
        run_id=run_id,
    )
    return ApplicationExecution(
        case=document,
        outcome=outcome,
        workspace=workspace,
        store=store,
        transport=transport,
        controller=controller,
        prepared=prepared,
    )


@dataclass
class _EmptyApplicationCredentialLease:
    scope_id: str
    credentials: Mapping[str, str]


class _EmptyApplicationCredentialBroker(CredentialBroker):
    def issue(
        self, *, binding_id: str, scope: CredentialScope
    ) -> CredentialLease:
        del binding_id
        if scope.credential_names != ():
            raise ValueError("application acceptance credentials must be empty")
        return _EmptyApplicationCredentialLease(
            scope_id=scope.scope_id,
            credentials={},
        )


def _load_application_document(case: Path | Mapping[str, object]) -> Mapping[str, object]:
    if isinstance(case, Path):
        payload = json.loads(case.read_text(encoding="utf-8"))
    else:
        payload = case
    if not isinstance(payload, Mapping):
        raise ValueError("application case must be an object")
    if payload.get("schema_version") != "application-instantiation/1.0":
        raise ValueError("application case schema is invalid")
    for field in ("case_id", "application_id", "run_id"):
        if not isinstance(payload.get(field), str) or not payload[field]:
            raise ValueError(f"application case {field} is invalid")
    questions = payload.get("questions")
    if not isinstance(questions, list) or not questions:
        raise ValueError("application case questions are invalid")
    seen_ids: set[str] = set()
    for question in questions:
        if not isinstance(question, Mapping):
            raise ValueError("application case question is invalid")
        question_id = question.get("id")
        if not isinstance(question_id, str) or not question_id or question_id in seen_ids:
            raise ValueError("application case question identifiers are invalid")
        seen_ids.add(question_id)
        if not isinstance(question.get("text"), str) or not question["text"].strip():
            raise ValueError("application case question text is invalid")
        steps = question.get("steps")
        if not isinstance(steps, list):
            raise ValueError("application case question steps are invalid")
        for step in steps:
            if not isinstance(step, Mapping) or not isinstance(step.get("capability"), str):
                raise ValueError("application case step is invalid")
            if not isinstance(step.get("arguments", {}), Mapping):
                raise ValueError("application case step arguments are invalid")
    return payload


def _resolve_scripted_arguments(
    value: object,
    *,
    context_ref: str | None,
    result_ref: str | None,
    asset_ref: str | None,
) -> dict[str, object]:
    resolved = _resolve_scripted_value(
        value,
        context_ref=context_ref,
        result_ref=result_ref,
        asset_ref=asset_ref,
    )
    if not isinstance(resolved, Mapping):
        raise RuntimeError("scripted application arguments must be an object")
    return {str(key): item for key, item in resolved.items()}


def _resolve_scripted_value(
    value: object,
    *,
    context_ref: str | None,
    result_ref: str | None,
    asset_ref: str | None,
) -> object:
    if isinstance(value, str) and value.startswith("$"):
        values = {
            "$context_ref": context_ref,
            "$result_ref": result_ref,
            "$asset_ref": asset_ref,
        }
        if value not in values or not isinstance(values[value], str):
            raise RuntimeError(f"scripted application reference is unavailable: {value}")
        return values[value]
    if isinstance(value, Mapping):
        return {
            str(key): _resolve_scripted_value(
                item,
                context_ref=context_ref,
                result_ref=result_ref,
                asset_ref=asset_ref,
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [
            _resolve_scripted_value(
                item,
                context_ref=context_ref,
                result_ref=result_ref,
                asset_ref=asset_ref,
            )
            for item in value
        ]
    return value


def _emit_scripted_event(callback: object | None, event: Mapping[str, object], sequence: int) -> None:
    if not callable(callback):
        return
    callback(event, sequence)


def _digest_refs(value: object, prefix: str) -> tuple[str, ...]:
    refs: list[str] = []
    if isinstance(value, Mapping):
        for nested in value.values():
            refs.extend(_digest_refs(nested, prefix))
    elif isinstance(value, list | tuple):
        for nested in value:
            refs.extend(_digest_refs(nested, prefix))
    elif isinstance(value, str) and value.startswith(prefix) and len(value) == len(prefix) + 64:
        refs.append(value)
    return _ordered_unique(refs)


def _preferred_asset_ref(value: Mapping[str, object]) -> str | None:
    for key in ("asset_ref", "branch_ref"):
        candidate = value.get(key)
        if isinstance(candidate, str) and candidate.startswith("asset:"):
            return candidate
    for key in ("element", "branch"):
        nested = value.get(key)
        if isinstance(nested, Mapping):
            candidate = nested.get("asset_ref")
            if isinstance(candidate, str) and candidate.startswith("asset:"):
                return candidate
    for nested in value.values():
        if isinstance(nested, Mapping):
            candidate = _preferred_asset_ref(nested)
            if candidate is not None:
                return candidate
        elif isinstance(nested, list):
            for item in nested:
                if isinstance(item, Mapping):
                    candidate = _preferred_asset_ref(item)
                    if candidate is not None:
                        return candidate
    return None


def _ordered_unique(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if isinstance(value, str)))


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class TraceSummary:
    capabilities: tuple[str, ...]
    tool_calls: int
    result_events: tuple[ToolResultEvent, ...]

    @property
    def evidence_refs(self) -> tuple[str, ...]:
        refs: list[str] = []
        for event in self.result_events:
            refs.extend(event.evidence_refs)
        return tuple(dict.fromkeys(refs))


@dataclass(frozen=True)
class CaseExecution:
    answer: AnswerEnvelope | None
    trace: TraceSummary | None
    run_path: Path | None
    returncode: int | None
    stdout: str
    stderr: str
    duration_seconds: float
    metadata: Mapping[str, object]


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.mode is not None:
        return _main_mode(args)

    return _main_legacy(args)


def _main_legacy(args: argparse.Namespace) -> int:
    suites = tuple(args.suite or ())
    case_ids = tuple(args.case_id or ())
    cases = _select_cases(load_cases(args.cases_root), suite=suites, case_id=case_ids)
    answer_corpus = _load_required_corpus(cases, args.answer_corpus)
    passed = 0

    for case in cases:
        record = _run_case(
            case,
            args.command_template,
            trace_template=args.trace_template,
            timeout_seconds=args.timeout_seconds,
            answer_corpus=answer_corpus,
        )
        if record["passed"] is True:
            passed += 1
        _emit(record)

    summary = {"type": "summary", "total": len(cases), "passed": passed, "failed": len(cases) - passed}
    _emit(summary)
    return 0 if summary["failed"] == 0 else 1


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run deterministic grid-agent validation cases.")
    parser.add_argument("--cases-root", type=Path, default=Path("validation"))
    parser.add_argument(
        "--mode", choices=("offline", "scripted-pi", "provider", "application")
    )
    parser.add_argument("--provider")
    parser.add_argument("--model")
    parser.add_argument("--report", type=Path)
    parser.add_argument(
        "--answer-corpus",
        type=Path,
        default=_repo_root() / "docs/test_script/测试题目答案.jsonl",
    )
    parser.add_argument("--suite", action="append")
    parser.add_argument("--case-id", action="append")
    parser.add_argument("--trace-template")
    parser.add_argument("--timeout-seconds", type=float, default=60.0)
    parser.add_argument("command_template", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    if args.command_template and args.command_template[0] == "--":
        args.command_template = args.command_template[1:]
    if args.mode is None and not args.command_template:
        parser.error("a command template is required after --")
    if args.mode is not None and args.command_template:
        parser.error("command templates are not supported with --mode")
    if args.mode is not None and args.report is None:
        parser.error("--report is required with --mode")
    if args.mode == "provider" and not args.provider:
        parser.error("--provider is required in provider mode")
    if args.mode in {"offline", "scripted-pi", "application"} and args.provider:
        parser.error("--provider is only valid in provider mode")
    return args


def _main_mode(args: argparse.Namespace) -> int:
    suites = tuple(args.suite or ())
    if len(suites) != 1:
        raise SystemExit("--mode requires exactly one --suite")
    case_ids = tuple(args.case_id or ())
    if args.mode == "application":
        return _main_application_mode(args, suite=suites[0], case_ids=case_ids)
    cases = _select_cases(load_cases(args.cases_root), suite=suites, case_id=case_ids)
    answer_corpus = _load_required_corpus(cases, args.answer_corpus)
    records = [_run_mode_case(case, args, answer_corpus=answer_corpus) for case in cases]
    passed = sum(1 for record in records if record["passed"] is True)
    report = {
        "type": "validation_report",
        "version": "1.0",
        "mode": args.mode,
        "suite": suites[0],
        "provider": args.provider if args.mode == "provider" else None,
        "model": args.model if args.mode == "provider" else None,
        "summary": {"total": len(records), "passed": passed, "failed": len(records) - passed},
        "cases": records,
    }
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if report["summary"]["failed"] == 0 else 1


def _main_application_mode(
    args: argparse.Namespace,
    *,
    suite: str,
    case_ids: Sequence[str],
) -> int:
    if suite != "application-instantiation":
        raise SystemExit(
            "application mode requires the application-instantiation suite"
        )
    documents = _select_application_documents(
        args.cases_root,
        case_ids=case_ids,
    )
    records: list[dict[str, object]] = []
    for path, document in documents:
        started = time.monotonic()
        try:
            execution = execute_application_case(
                document,
                runs_root=_repo_root() / "runs",
                timeout_seconds=args.timeout_seconds,
            )
            record = _evaluate_application_execution(execution)
        except Exception as exc:
            record = {
                "type": "case",
                "case_id": document.get("case_id"),
                "passed": False,
                "checks": {},
                "errors": {"execution": [f"{type(exc).__name__}: {exc}"]},
                "scores": {"application_instantiation": 0.0},
                "metadata": {"case_path": str(path)},
            }
        record.setdefault("metadata", {})
        metadata = record["metadata"]
        if isinstance(metadata, Mapping):
            record["metadata"] = {
                **dict(metadata),
                "case_path": str(path),
                "duration_seconds": round(time.monotonic() - started, 3),
            }
        records.append(record)
    passed = sum(1 for record in records if record["passed"] is True)
    report = {
        "type": "validation_report",
        "version": "1.0",
        "mode": args.mode,
        "suite": suite,
        "provider": None,
        "model": None,
        "summary": {
            "total": len(records),
            "passed": passed,
            "failed": len(records) - passed,
        },
        "cases": records,
    }
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0 if report["summary"]["failed"] == 0 else 1


def _select_application_documents(
    cases_root: Path,
    *,
    case_ids: Sequence[str],
) -> tuple[tuple[Path, Mapping[str, object]], ...]:
    root = Path(cases_root) / "application"
    paths = tuple(sorted(root.glob("*.json")))
    selected: list[tuple[Path, Mapping[str, object]]] = []
    for path in paths:
        document = _load_application_document(path)
        if case_ids and document.get("case_id") not in case_ids:
            continue
        selected.append((path, document))
    if not selected:
        raise SystemExit("no application validation cases matched the requested filters")
    return tuple(selected)


def _evaluate_application_execution(
    execution: ApplicationExecution,
) -> dict[str, object]:
    """Evaluate generic application invariants without answer-value fixtures."""

    outcome = execution.outcome
    errors: dict[str, list[str]] = {
        "application": [],
        "output": [],
        "lineage": [],
        "context_replay": [],
        "answer_audit": [],
        "report": [],
    }
    case = execution.case
    expected_questions = case.get("questions")
    expected_count = len(expected_questions) if isinstance(expected_questions, list) else 0
    if getattr(outcome, "status", None) != "completed":
        errors["application"].append(
            f"application status is {getattr(outcome, 'status', None)!r}"
        )
    if getattr(outcome, "completed_questions", None) != expected_count:
        errors["application"].append("application did not complete every scripted question")
    if getattr(outcome, "total_questions", None) != expected_count:
        errors["application"].append("application question count does not match the case")

    result_payload: Mapping[str, object] = {}
    try:
        result_model = getattr(outcome, "result")
        dumped = result_model.model_dump(mode="json")
        if not isinstance(dumped, Mapping):
            raise ValueError("application result is not an object")
        result_payload = dumped
        if set(result_payload) != {"schema", "core", "domains"}:
            errors["output"].append("generic result does not contain exactly schema/core/domains")
        if result_payload.get("schema") != "capability-agent-output/1.0":
            errors["output"].append("generic result schema is invalid")
        core = result_payload.get("core")
        domains = result_payload.get("domains")
        if not isinstance(core, Mapping) or not isinstance(domains, Mapping):
            errors["output"].append("generic result core/domains sections are invalid")
        else:
            if core.get("application_id") != case.get("application_id"):
                errors["output"].append("core application identity is invalid")
            if core.get("status") != "completed":
                errors["output"].append("core status is not completed")
            domain = domains.get("grid")
            if not isinstance(domain, Mapping):
                errors["output"].append("domains.grid output is missing")
            else:
                if domain.get("status") != "completed":
                    errors["output"].append("domains.grid status is not completed")
                payload = domain.get("payload")
                if not isinstance(payload, Mapping):
                    errors["output"].append("domains.grid payload is invalid")
                elif set(payload) != {
                    "mode",
                    "instruction_count",
                    "completed_count",
                    "failed_count",
                    "report_artifact_ref",
                }:
                    errors["output"].append("domains.grid payload violates its domain contract")
    except Exception as exc:
        errors["output"].append(f"application result validation failed: {type(exc).__name__}: {exc}")

    rendered = getattr(outcome, "rendered", None)
    if not isinstance(rendered, str):
        errors["output"].append("generic output renderer did not return JSON text")
    else:
        try:
            rendered_payload = json.loads(rendered)
            if rendered_payload != result_payload:
                errors["output"].append("rendered output differs from validated result")
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            errors["output"].append(f"rendered output is not JSON: {exc}")

    report_path = getattr(outcome, "report_path", None)
    core_payload = result_payload.get("core")
    report_ref = (
        core_payload.get("report_ref")
        if isinstance(core_payload, Mapping)
        else None
    )
    if not isinstance(report_path, Path) or not report_path.is_file():
        errors["report"].append("application report was not created")
    elif not isinstance(report_ref, str):
        errors["report"].append("application report reference is missing")
    else:
        expected_report_ref = "artifact:sha256:" + hashlib.sha256(
            report_path.read_bytes()
        ).hexdigest()
        if report_ref != expected_report_ref:
            errors["report"].append("application report digest does not match its reference")
        produced_refs = execution.store.snapshot.core.produced_refs
        if report_ref not in produced_refs:
            errors["report"].append("application report reference was not admitted to core")

    finalizations = execution.controller.finalized_turns
    if len(finalizations) != expected_count:
        errors["answer_audit"].append("not every scripted turn reached answer audit")
    for finalized in finalizations:
        if getattr(finalized, "status", None) != "success":
            errors["answer_audit"].append("a scripted answer was not committed successfully")
        for diagnostic in getattr(finalized, "audit_diagnostics", ()):
            severity = (
                diagnostic.get("severity")
                if isinstance(diagnostic, Mapping)
                else getattr(diagnostic, "severity", None)
            )
            if severity == "error":
                errors["answer_audit"].append("answer audit returned an error diagnostic")
        answer_path = getattr(finalized, "answer_path", None)
        if not isinstance(answer_path, Path) or not answer_path.is_file():
            errors["answer_audit"].append("committed answer artifact is missing")

    try:
        replayed = ApplicationContextStore.replay(execution.workspace)
        if replayed != execution.store.snapshot:
            errors["context_replay"].append("context ledger replay differs from materialized state")
        execution.store.verify_materialized_snapshot()
    except Exception as exc:
        errors["context_replay"].append(
            f"context replay verification failed: {type(exc).__name__}: {exc}"
        )

    try:
        domain_root = execution.workspace.domain_roots["grid"]
        runtime = execution.prepared.bindings["grid"].runtime
        authority = runtime.authority
        from pandapower_domain.authority import ContentReferenceVerifier

        verifier = ContentReferenceVerifier(domain_root)
        result_refs = tuple(execution.transport.all_result_refs)
        evidence_refs = tuple(execution.transport.all_evidence_refs)
        context_refs = _digest_refs(
            tuple(
                call.get("result", {})
                for call in execution.transport.calls
                if isinstance(call, Mapping)
            ),
            "context:sha256:",
        )
        context_refs = _ordered_unique(context_refs)
        if len(context_refs) != 1:
            errors["lineage"].append("scripted turns did not reuse one simulator context")
        for reference in context_refs:
            artifact = verifier.verify_context(reference)
            artifact.path.relative_to(domain_root)
        for reference in result_refs:
            artifact = authority.verify_result(reference)
            artifact.path.relative_to(domain_root)
        for reference in evidence_refs:
            artifact = verifier.verify_evidence(reference)
            artifact.path.relative_to(domain_root)
        context_dump = execution.store.snapshot.model_dump(mode="json")
        observed_result_refs = set(_digest_refs(context_dump, "result:sha256:"))
        observed_evidence_refs = set(_digest_refs(context_dump, "evidence:sha256:"))
        if not set(result_refs).issubset(observed_result_refs):
            errors["lineage"].append("a simulator result was not persisted in current-run context")
        if not set(evidence_refs).issubset(observed_evidence_refs):
            errors["lineage"].append("simulator evidence was not persisted in current-run context")
        if not execution.transport.calls:
            errors["lineage"].append("scripted model did not execute a semantic capability")
        if any(
            event.get("type") == "tool_result"
            and event.get("ok") is not True
            for event in execution.transport.semantic_events
            if isinstance(event, Mapping)
        ):
            errors["lineage"].append("scripted semantic transport returned a failed tool event")
    except Exception as exc:
        errors["lineage"].append(
            f"current-run result/evidence admission failed: {type(exc).__name__}: {exc}"
        )

    checks = {name: not values for name, values in errors.items()}
    passed = all(checks.values())
    return {
        "type": "case",
        "case_id": case.get("case_id"),
        "passed": passed,
        "checks": checks,
        "errors": errors,
        "scores": {
            "application_instantiation": 1.0 if passed else 0.0,
            "context_reuse": 1.0 if checks["lineage"] else 0.0,
            "answer_audit": 1.0 if checks["answer_audit"] else 0.0,
            "report_admission": 1.0 if checks["report"] else 0.0,
        },
        "trace": {
            "capabilities": [call.get("capability") for call in execution.transport.calls],
            "tool_calls": len(execution.transport.calls),
        },
        "result_refs": list(execution.transport.all_result_refs),
        "evidence_refs": list(execution.transport.all_evidence_refs),
        "returncode": 0 if getattr(outcome, "status", None) == "completed" else 1,
        "metadata": {
            "run_path": str(execution.workspace.root),
            "application_id": case.get("application_id"),
            "application_output_schema": result_payload.get("schema"),
        },
    }


def _run_mode_case(
    case: ValidationCase,
    args: argparse.Namespace,
    *,
    answer_corpus: AnswerCorpus | None,
) -> dict[str, object]:
    started = time.monotonic()
    if args.mode == "offline":
        execution = _execute_offline_case(case, started_at=started, timeout_seconds=args.timeout_seconds)
    elif args.mode == "scripted-pi":
        execution = _execute_scripted_pi_case(case, started_at=started, timeout_seconds=args.timeout_seconds)
    elif args.mode == "provider":
        execution = _execute_provider_case(case, args, started_at=started, timeout_seconds=args.timeout_seconds)
    else:
        raise AssertionError(f"unsupported validation mode: {args.mode}")

    return _evaluate_execution(case, execution, answer_corpus=answer_corpus)


def _load_required_corpus(cases: Sequence[ValidationCase], path: Path) -> AnswerCorpus | None:
    if not any(case.oracle.kind == "semantic" for case in cases):
        return None
    try:
        return load_answer_corpus(path)
    except (OSError, AnswerCorpusError) as exc:
        raise SystemExit(f"semantic answer corpus unavailable: {path}: {exc}") from exc


def _select_cases(
    cases: Sequence[ValidationCase],
    *,
    suite: Sequence[str],
    case_id: Sequence[str],
) -> tuple[ValidationCase, ...]:
    selected = tuple(
        case
        for case in cases
        if (not suite or any(name in case.suites for name in suite)) and (not case_id or case.id in case_id)
    )
    if not selected:
        raise SystemExit("no validation cases matched the requested filters")
    return selected


class _RecordingClient:
    def __init__(self, client: GridctlClient) -> None:
        self.client = client
        self.events: list[ToolResultEvent] = []

    def invoke(self, capability: str, arguments: dict[str, object]) -> dict[str, object]:
        try:
            result = self.client.invoke(capability, arguments)
        except SimulatorCapabilityError as exc:
            error = dict(exc.error)
            self.events.append(
                ToolResultEvent(
                    capability=capability,
                    result={},
                    evidence_refs=_extract_evidence_refs(error),
                    ok=False,
                    error=cast(Mapping[str, JsonValue], error),
                )
            )
            raise
        self.events.append(
            ToolResultEvent(
                capability=capability,
                result=cast(Mapping[str, JsonValue], result),
                evidence_refs=_extract_evidence_refs(result),
            )
        )
        return result


def _execute_offline_case(
    case: ValidationCase,
    *,
    started_at: float,
    timeout_seconds: float,
) -> CaseExecution:
    answer = answer_information(case.question)
    trace: TraceSummary | None = None
    run_path: Path | None = None
    if answer is None:
        plan = plan_diagnostic(case.question)
        if isinstance(plan, str):
            answer = plan
        else:
            run_path = Path("runs") / case.id
            shutil.rmtree(run_path, ignore_errors=True)
            workspace = RunWorkspace.create(Path("runs"), run_id=case.id)
            client = _RecordingClient(
                GridctlClient(
                    executable=GridctlLocator(_repo_root()).resolve(),
                    workspace=workspace.root_path,
                    timeout_seconds=timeout_seconds,
                )
            )
            answer = answer_diagnostic(case.question, client)
            trace = TraceSummary(
                capabilities=tuple(event.capability for event in client.events),
                tool_calls=len(client.events),
                result_events=tuple(client.events),
            )
    envelope = AnswerEnvelope(question_id=case.id, answer_output=answer)
    return CaseExecution(
        answer=envelope,
        trace=trace,
        run_path=run_path,
        returncode=0,
        stdout=json.dumps(envelope.model_dump(), ensure_ascii=False),
        stderr="",
        duration_seconds=time.monotonic() - started_at,
        metadata={},
    )


def _execute_scripted_pi_case(
    case: ValidationCase,
    *,
    started_at: float,
    timeout_seconds: float,
) -> CaseExecution:
    if case.id == "topology-line-endpoints-001":
        return _execute_scripted_pi_cli_case(case, started_at=started_at, timeout_seconds=timeout_seconds)
    return _execute_scripted_static_case(case, started_at=started_at, timeout_seconds=timeout_seconds)


def _execute_scripted_static_case(
    case: ValidationCase,
    *,
    started_at: float,
    timeout_seconds: float,
) -> CaseExecution:
    run_path = Path("runs") / case.id
    shutil.rmtree(run_path, ignore_errors=True)
    workspace = RunWorkspace.create(Path("runs"), run_id=case.id)
    client = _RecordingClient(
        GridctlClient(
            executable=GridctlLocator(_repo_root()).resolve(),
            workspace=workspace.root_path,
            timeout_seconds=timeout_seconds,
        )
    )
    if case.oracle.kind == "semantic":
        answer = _execute_corpus_semantic_scenario(case, client)
        guide_event = ToolResultEvent(
            capability="grid_guide_open",
            result={"resource_id": "native-static-analyses"},
            evidence_refs=(),
        )
        events = (guide_event, *client.events)
        trace = TraceSummary(
            capabilities=tuple(event.capability for event in events),
            tool_calls=len(events),
            result_events=tuple(events),
        )
        envelope = AnswerEnvelope(question_id=case.id, answer_output=answer)
        return CaseExecution(
            answer=envelope,
            trace=trace,
            run_path=workspace.root_path,
            returncode=0,
            stdout=json.dumps(envelope.model_dump(), ensure_ascii=False),
            stderr="",
            duration_seconds=time.monotonic() - started_at,
            metadata={"corpus_id": case.oracle.arguments.get("corpus_id")},
        )
    guide_event = ToolResultEvent(
        capability="grid_guide_open",
        result={"resource_id": _guide_for_case(case.id)},
        evidence_refs=(),
    )
    opened = client.invoke("context.open", {"model_id": case.model or "ieee39"})
    context_ref = str(opened["context_ref"])

    if case.id == "static-line-lookup-by-alias-001":
        result = client.invoke(
            "model.element.get",
            {"context_ref": context_ref, "kind": "line", "namespace": "alias", "identifier": "pandapower:line:11"},
        )
        answer = f"resolved {result['asset_ref']}"
    elif case.id == "static-bus-listing-001":
        result = client.invoke(
            "model.dataset.query",
            {
                "context_ref": context_ref,
                "dataset": "network.buses",
                "select": ["kind", "index", "name", "vn_kv"],
                "sort": {"field": "index", "direction": "ascending"},
                "limit": 3,
            },
        )
        answer = f"listed {result['returned_row_count']} buses"
    elif case.id == "static-branch-dataset-schema-001":
        result = client.invoke("model.dataset.describe", {"context_ref": context_ref, "dataset": "network.branches"})
        fields = result.get("fields")
        answer = f"branch fields {len(fields) if isinstance(fields, list) else 0}"
    elif case.id == "static-components-001":
        result = client.invoke("topology.components.get", {"context_ref": context_ref})
        answer = f"components {result['component_count']}"
    elif case.id == "static-invalid-field-recovery-001":
        try:
            client.invoke(
                "model.dataset.query",
                {"context_ref": context_ref, "dataset": "network.branches", "select": ["not_a_field"]},
            )
        except SimulatorCapabilityError:
            pass
        answer = "typed invalid field recovery"
    elif case.id == "static-stale-result-ref-001":
        try:
            client.invoke(
                "result.branches.rank",
                {
                    "result_ref": "result:sha256:" + "0" * 64,
                    "metric": "loading_percent",
                    "direction": "descending",
                    "limit": 5,
                },
            )
        except SimulatorCapabilityError:
            pass
        answer = "typed stale result limitation"
    elif case.id == "static-evidence-mismatch-001":
        try:
            client.invoke("evidence.get", {"evidence_ref": "evidence:sha256:" + "0" * 64})
        except SimulatorCapabilityError:
            pass
        answer = "typed evidence limitation"
    elif case.id == "static-ac-non-convergence-001":
        evidence_ref = _write_synthetic_evidence(
            workspace.root_path,
            {
                "evidence_type": "powerflow_non_convergence",
                "capability_id": "analysis.powerflow.ac.run",
                "context_ref": context_ref,
                "reason": "validation injection",
            },
        )
        client.events.append(
            ToolResultEvent(
                capability="analysis.powerflow.ac.run",
                result={},
                evidence_refs=(evidence_ref,),
                ok=False,
                error={
                    "code": "powerflow_non_converged",
                    "retryable": False,
                    "allowed_recovery_actions": [
                        "inspect_network_diagnostics",
                        "change_solver_profile",
                        "report_non_convergence",
                    ],
                },
            )
        )
        answer = "typed non-convergence limitation"
    elif case.id == "static-n1-partial-failure-001":
        element = client.invoke(
            "model.element.get",
            {"context_ref": context_ref, "kind": "line", "namespace": "pandapower_index", "identifier": "11"},
        )
        element_record = _require_json_mapping(element.get("element"), "resolved element")
        asset_ref = element_record.get("asset_ref")
        if not isinstance(asset_ref, str):
            raise RuntimeError("resolved element did not include a string asset_ref")
        result = client.invoke(
            "analysis.contingency.n_minus_one.run",
            {
                "context_ref": context_ref,
                "branch_refs": [asset_ref],
            },
        )
        constraint_evaluation = _require_json_mapping(
            result.get("constraint_evaluation"),
            "constraint evaluation",
        )
        evidence_ref = _write_synthetic_evidence(
            workspace.root_path,
            {
                "evidence_type": "powerflow_non_convergence",
                "capability_id": "analysis.contingency.n_minus_one.run",
                "context_ref": context_ref,
                "reason": "validation injection",
            },
        )
        client.events[-1] = ToolResultEvent(
            capability="analysis.contingency.n_minus_one.run",
            result=cast(Mapping[str, JsonValue], {
                "status": "partial",
                "constraint_evaluation": dict(constraint_evaluation),
                "scenarios": [
                    {"status": "succeeded", "pandapower_index": 11},
                    {"status": "non_converged", "pandapower_index": 21},
                ],
            }),
            evidence_refs=_extract_evidence_refs(result) + (evidence_ref,),
        )
        answer = "typed partial N-1 result"
    elif case.id == "static-sourced-risk-001":
        constrained = client.invoke(
            "model.revision.derive",
            {
                "context_ref": context_ref,
                "patches": [
                    {
                        "operation": "set",
                        "kind": "bus",
                        "selector": {"where": {}},
                        "values": {"min_vm_pu": 0.8, "max_vm_pu": 0.9},
                    },
                    {
                        "operation": "set",
                        "kind": "line",
                        "selector": {"where": {}},
                        "values": {"max_loading_percent": 1.0},
                    },
                ],
            },
        )
        powerflow = _run_validation_analysis(
            client,
            str(constrained["context_ref"]),
            "powerflow.ac",
            {},
        )
        violations = client.invoke(
            "analysis.result.violations.evaluate",
            {"result_ref": str(powerflow["result_ref"])},
        )
        risk = client.invoke(
            "analysis.result.risk.rank",
            {"result_ref": str(violations["result_ref"]), "limit": 5},
        )
        rankings = risk.get("rankings")
        answer = f"ranked {len(rankings) if isinstance(rankings, list) else 0} sourced risks"
    else:
        answer = "执行限制 / execution limitation: scripted validation case is not implemented"

    events = (guide_event, *client.events)
    trace = TraceSummary(
        capabilities=tuple(event.capability for event in events),
        tool_calls=len(events),
        result_events=tuple(events),
    )
    envelope = AnswerEnvelope(question_id=case.id, answer_output=answer)
    return CaseExecution(
        answer=envelope,
        trace=trace,
        run_path=workspace.root_path,
        returncode=0,
        stdout=json.dumps(envelope.model_dump(), ensure_ascii=False),
        stderr="",
        duration_seconds=time.monotonic() - started_at,
        metadata={},
    )


def _execute_corpus_semantic_scenario(case: ValidationCase, client: _RecordingClient) -> str:
    corpus_id = str(case.oracle.arguments["corpus_id"])
    if corpus_id == "T-A1":
        context_ref = _open_validation_model(client, "ieee39")
        client.invoke(
            "model.dataset.query",
            {
                "context_ref": context_ref,
                "dataset": "network.bus",
                "select": ["index"],
                "where": {"in_service": True},
                "limit": 200,
            },
        )
    elif corpus_id == "T-B1":
        context_ref = _open_validation_model(client, "ieee39")
        topology = _run_validation_analysis(client, context_ref, "topology.unsupplied", {})
        _query_validation_result(
            client,
            str(topology["result_ref"]),
            "result.res_unsupplied_bus",
            ["bus_index"],
        )
    elif corpus_id == "T-C1":
        context_ref = _open_validation_model(client, "ieee39")
        powerflow = _run_validation_analysis(client, context_ref, "powerflow.ac", {"algorithm": "nr"})
        _query_validation_result(
            client,
            str(powerflow["result_ref"]),
            "result.res_ext_grid",
            ["index", "p_mw"],
            where={"index": 0},
        )
    elif corpus_id == "T-D1":
        context_ref = _open_validation_model(client, "ieee39")
        client.invoke(
            "model.element.get",
            {
                "context_ref": context_ref,
                "kind": "line",
                "namespace": "pandapower_index",
                "identifier": "0",
            },
        )
        derived = client.invoke(
            "model.revision.derive",
            {
                "context_ref": context_ref,
                "patches": [
                    {
                        "operation": "in_service",
                        "kind": "line",
                        "selector": {"indices": [0]},
                        "value": False,
                    }
                ],
            },
        )
        derived_context = str(derived["context_ref"])
        topology = _run_validation_analysis(client, derived_context, "topology.unsupplied", {})
        _query_validation_result(
            client,
            str(topology["result_ref"]),
            "result.res_unsupplied_bus",
            ["bus_index"],
        )
        _run_validation_analysis(client, derived_context, "powerflow.dc", {})
    elif corpus_id == "T-E1":
        context_ref = _open_validation_model(client, "case9")
        _run_validation_analysis(client, context_ref, "opf.dc", {})
    elif corpus_id == "T-F1":
        created = client.invoke(
            "model.create",
            {
                "name": "validation-one-bus-short-circuit",
                "sn_mva": 100.0,
                "f_hz": 50.0,
                "elements": [
                    {"id": "source_bus", "creator": "bus", "arguments": {"vn_kv": 110.0}},
                    {
                        "id": "source",
                        "creator": "ext_grid",
                        "arguments": {
                            "bus": {"element_ref": "source_bus"},
                            "vm_pu": 1.0,
                            "s_sc_max_mva": 5000.0,
                            "rx_max": 0.1,
                        },
                    },
                ],
            },
        )
        short_circuit = _run_validation_analysis(
            client,
            str(created["context_ref"]),
            "short_circuit.iec60909",
            {"bus": 0, "fault": "3ph", "case": "max"},
        )
        _query_validation_result(
            client,
            str(short_circuit["result_ref"]),
            "result.res_bus_sc",
            ["index", "ikss_ka", "skss_mw"],
            where={"index": 0},
        )
    elif corpus_id == "T-G1":
        context_ref = _open_validation_model(client, "ieee39")
        derived = client.invoke(
            "model.revision.derive",
            {
                "context_ref": context_ref,
                "patches": [
                    {
                        "operation": "scale",
                        "kind": "load",
                        "selector": {"where": {"in_service": True}},
                        "fields": ["p_mw", "q_mvar"],
                        "factor": 1.05,
                    }
                ],
            },
        )
        client.invoke(
            "analysis.powerflow.ac.run",
            {"context_ref": str(derived["context_ref"]), "algorithm": "nr"},
        )
    else:
        raise ValueError(f"unknown semantic corpus scenario: {corpus_id}")
    return f"semantic validation completed for {corpus_id}"


def _open_validation_model(client: _RecordingClient, model_id: str) -> str:
    return str(client.invoke("context.open", {"model_id": model_id})["context_ref"])


def _run_validation_analysis(
    client: _RecordingClient,
    context_ref: str,
    operation: str,
    options: dict[str, object],
) -> dict[str, object]:
    return client.invoke(
        "analysis.run",
        {"context_ref": context_ref, "operation": operation, "options": options},
    )


def _query_validation_result(
    client: _RecordingClient,
    result_ref: str,
    dataset: str,
    select: list[str],
    *,
    where: dict[str, object] | None = None,
) -> dict[str, object]:
    arguments: dict[str, object] = {
        "result_ref": result_ref,
        "dataset": dataset,
        "select": select,
        "limit": 100,
    }
    if where is not None:
        arguments["where"] = where
    return client.invoke("result.dataset.query", arguments)


def _guide_for_case(case_id: str) -> str:
    if "dataset" in case_id or "lookup" in case_id or "bus" in case_id or "field" in case_id:
        return "network-elements"
    if "components" in case_id:
        return "topology-analysis"
    if "n1" in case_id:
        return "contingency-analysis"
    if "result" in case_id:
        return "result-query"
    if "evidence" in case_id:
        return "evidence-and-recovery"
    return "capability-map"


def _execute_scripted_pi_cli_case(
    case: ValidationCase,
    *,
    started_at: float,
    timeout_seconds: float,
) -> CaseExecution:
    run_path = Path("runs") / case.id
    shutil.rmtree(run_path, ignore_errors=True)
    with tempfile.TemporaryDirectory(prefix="grid-validation-pi-") as temp_dir:
        pi_path = Path(temp_dir) / "scripted-pi"
        pi_path.write_text(_scripted_topology_pi_source(), encoding="utf-8")
        pi_path.chmod(0o755)
        completed = subprocess.run(
            [
                "grid-agent",
                "run",
                "--question-id",
                case.id,
                case.question,
            ],
            cwd=_repo_root(),
            env={
                **os.environ,
                "GRID_AGENT_PI_COMMAND": str(pi_path),
                "GRID_AGENT_LLM_PROVIDER": "openai",
                "OPENAI_API_KEY": "validation-scripted-secret",
            },
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
        )
    answer = _parse_answer(completed.stdout, []) if completed.returncode == 0 else None
    trace_path = run_path / "events.jsonl"
    trace = _load_trace(trace_path, []) if trace_path.exists() else None
    return CaseExecution(
        answer=answer,
        trace=trace,
        run_path=run_path,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        duration_seconds=time.monotonic() - started_at,
        metadata={},
    )


def _execute_provider_case(
    case: ValidationCase,
    args: argparse.Namespace,
    *,
    started_at: float,
    timeout_seconds: float,
) -> CaseExecution:
    credential_error = _provider_credential_error(args.provider)
    if credential_error is not None:
        return CaseExecution(
            answer=None,
            trace=None,
            run_path=None,
            returncode=None,
            stdout="",
            stderr=credential_error,
            duration_seconds=time.monotonic() - started_at,
            metadata={"provider": args.provider, "model": args.model, "credentials": "missing"},
        )

    run_path = Path("runs") / case.id
    shutil.rmtree(run_path, ignore_errors=True)
    command = [
        "grid-agent",
        "run",
        "--question-id",
        case.id,
        "--provider",
        args.provider,
    ]
    if args.model:
        command.extend(["--model", args.model])
    command.append(case.question)
    completed = subprocess.run(
        command,
        cwd=_repo_root(),
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
    )
    answer = _parse_answer(completed.stdout, []) if completed.stdout.strip() else None
    trace_path = run_path / "events.jsonl"
    trace = _load_trace(trace_path, []) if trace_path.exists() else None
    return CaseExecution(
        answer=answer,
        trace=trace,
        run_path=run_path if run_path.exists() else None,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        duration_seconds=time.monotonic() - started_at,
        metadata={
            "provider": args.provider,
            "model": args.model,
            "latency_seconds": time.monotonic() - started_at,
            "tokens": None,
            "cost": None,
        },
    )


def _provider_credential_error(provider: str) -> str | None:
    key_by_provider = {
        "openai": "OPENAI_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
        "minimax": "MINIMAX_API_KEY",
    }
    key_name = key_by_provider.get(provider)
    if key_name is None:
        return None
    if os.environ.get(key_name):
        return None
    return f"provider mode requires explicit credentials: {key_name}"


def _evaluate_execution(
    case: ValidationCase,
    execution: CaseExecution,
    *,
    answer_corpus: AnswerCorpus | None,
) -> dict[str, object]:
    envelope_errors: list[str] = []
    oracle_errors: list[str] = []
    capability_errors: list[str] = []
    evidence_errors: list[str] = []

    if execution.returncode not in (0, None):
        envelope_errors.append(f"command exited with return code {execution.returncode}")
    if execution.answer is None:
        envelope_errors.append("answer envelope missing")
    elif execution.answer.question_id != case.id:
        envelope_errors.append(f"answer question_id mismatch: expected {case.id}, got {execution.answer.question_id}")

    _check_requirements(case, execution.trace, capability_errors)
    _check_oracle(case, execution.answer, execution.trace, oracle_errors, answer_corpus=answer_corpus)
    _check_evidence(case, execution, evidence_errors)

    checks = {
        "envelope": not envelope_errors,
        "oracle": not oracle_errors,
        "capability_constraints": not capability_errors,
        "evidence": not evidence_errors,
    }
    errors = {
        "envelope": envelope_errors,
        "oracle": oracle_errors,
        "capability_constraints": capability_errors,
        "evidence": evidence_errors,
    }
    efficiency = execution.trace is None or execution.trace.tool_calls <= case.requirements.max_tool_calls
    return {
        "type": "case",
        "case_id": case.id,
        "passed": all(checks.values()),
        "oracle": case.oracle.evaluator,
        "checks": checks,
        "errors": errors,
        "scores": {
            "orchestration_completion": 1.0 if checks["envelope"] else 0.0,
            "semantic_correctness": 1.0 if checks["oracle"] else 0.0,
            "evidence": 1.0 if checks["evidence"] else 0.0,
            "efficiency": 1.0 if efficiency else 0.0,
        },
        "efficiency": {
            "tool_calls": execution.trace.tool_calls if execution.trace else 0,
            "advisory_max_tool_calls": case.requirements.max_tool_calls,
            "within_advisory_budget": efficiency,
        },
        "trace": {
            "capabilities": list(execution.trace.capabilities) if execution.trace else [],
            "tool_calls": execution.trace.tool_calls if execution.trace else 0,
        },
        "evidence_refs": list(execution.trace.evidence_refs) if execution.trace else [],
        "returncode": execution.returncode,
        "duration_seconds": round(execution.duration_seconds, 3),
        "metadata": dict(execution.metadata),
    }


def _run_case(
    case: ValidationCase,
    command_template: Sequence[str],
    *,
    trace_template: str | None,
    timeout_seconds: float,
    answer_corpus: AnswerCorpus | None,
) -> dict[str, object]:
    command = _format_template(command_template, case)
    errors: list[str] = []
    stdout = ""
    returncode: int | None = None
    try:
        completed = subprocess.run(command, text=True, capture_output=True, timeout=timeout_seconds)
        stdout = completed.stdout
        returncode = completed.returncode
    except subprocess.TimeoutExpired:
        errors.append(f"command_timeout: exceeded {timeout_seconds:g} seconds")
    except OSError as exc:
        errors.append(_classify_os_error(exc, command))

    if returncode is not None and returncode != 0:
        errors.append(f"command exited with return code {returncode}")

    answer = _parse_answer(stdout, errors) if returncode is not None else None
    if answer is not None:
        if answer.question_id != case.id:
            errors.append(f"answer question_id mismatch: expected {case.id}, got {answer.question_id}")

    trace_path = Path(_format_template([trace_template], case)[0]) if trace_template else None
    trace = _load_trace(trace_path, errors) if trace_path is not None else None
    _check_requirements(case, trace, errors)
    _check_oracle(case, answer, trace, errors, answer_corpus=answer_corpus)

    return {
        "type": "case",
        "case_id": case.id,
        "passed": not errors,
        "returncode": returncode,
        "oracle": case.oracle.evaluator,
        "errors": errors,
    }


def _classify_os_error(exc: OSError, command: Sequence[str]) -> str:
    executable = command[0] if command else ""
    if isinstance(exc, FileNotFoundError):
        return f"command_os_error: executable not found: {executable}"
    return f"command_os_error: {exc.__class__.__name__}: {exc.strerror or str(exc)}"


def _parse_answer(stdout: str, errors: list[str]) -> AnswerEnvelope | None:
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        errors.append("answer envelope is not valid JSON")
        return None
    try:
        return AnswerEnvelope.model_validate(payload)
    except ValidationError as exc:
        errors.append(f"answer envelope failed contract validation: {exc.errors()[0]['msg']}")
        return None


def _check_requirements(case: ValidationCase, trace: TraceSummary | None, errors: list[str]) -> None:
    requirements = case.requirements
    if trace is None:
        if case.oracle.kind == "structured":
            return
        if requirements.requires_evidence:
            errors.append("required evidence trace was not supplied")
        return

    capabilities = set(trace.capabilities)
    missing = tuple(item for item in requirements.required_capabilities if item not in capabilities)
    forbidden = tuple(item for item in requirements.forbidden_capabilities if item in capabilities)
    if missing:
        errors.append("missing required capabilities: " + ", ".join(missing))
    if forbidden:
        errors.append("forbidden capabilities observed: " + ", ".join(forbidden))


def _check_oracle(
    case: ValidationCase,
    answer: AnswerEnvelope | None,
    trace: TraceSummary | None,
    errors: list[str],
    *,
    answer_corpus: AnswerCorpus | None,
) -> None:
    if case.oracle.kind == "semantic":
        if trace is None:
            errors.append("semantic_trace_missing")
            return
        if answer_corpus is None:
            errors.append("semantic_answer_corpus_missing")
            return
        if case.oracle.evaluator != "corpus_trace_matches":
            errors.append(f"unknown semantic oracle evaluator: {case.oracle.evaluator}")
            return
        errors.extend(
            evaluate_corpus_trace(
                trace.result_events,
                dict(case.oracle.arguments),
                answer_corpus,
            )
        )
        return
    evaluator = ORACLES.get(case.oracle.evaluator)
    if evaluator is None:
        errors.append(f"unknown oracle evaluator: {case.oracle.evaluator}")
        return

    if case.oracle.kind == "structured":
        required_capability = case.requirements.required_capabilities[0]
        if trace is None:
            errors.append("verification_trace_missing: " + required_capability)
            return

        candidates = tuple(event for event in trace.result_events if event.capability == required_capability)
        if not candidates:
            errors.append("verification_result_missing: " + required_capability)
        elif case.oracle.evaluator != "error_matches" and not any(event.ok is True for event in candidates):
            errors.append("verification_result_missing: " + required_capability)
        elif (
            case.requirements.requires_evidence
            and case.oracle.evaluator != "error_matches"
            and required_capability != "result.branches.rank"
            and not any(event.evidence_refs for event in candidates)
        ):
            errors.append("verification_evidence_missing: " + required_capability)
        elif not any(evaluator(event, case.oracle.arguments) for event in candidates):
            errors.append("structured_oracle_mismatch: " + case.oracle.evaluator)
        return

    if answer is not None and not evaluator(answer.answer_output, case.oracle.arguments):
        errors.append(f"oracle failed: {case.oracle.evaluator}")


def _load_trace(path: Path, errors: list[str]) -> TraceSummary | None:
    if not path.exists():
        errors.append(f"trace file not found: {path}")
        return None

    capabilities: list[str] = []
    result_events: list[ToolResultEvent] = []
    tool_calls = 0
    observed_tool_call_ids: set[str] = set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            errors.append(f"trace line {line_number} is not valid JSON")
            continue
        payload = _trace_payload(event)
        result_event = _tool_result_event(payload, line_number, errors)
        if result_event is not None:
            result_events.append(result_event)
        capability = _event_capability(payload)
        if capability is not None:
            capabilities.append(capability)
        if capability is not None or _is_tool_event(payload):
            tool_call_id = _tool_call_id(payload)
            if tool_call_id is None or tool_call_id not in observed_tool_call_ids:
                tool_calls += 1
                if tool_call_id is not None:
                    observed_tool_call_ids.add(tool_call_id)
    return TraceSummary(
        capabilities=tuple(capabilities),
        tool_calls=tool_calls,
        result_events=tuple(result_events),
    )


def _tool_call_id(value: object) -> str | None:
    if not isinstance(value, Mapping):
        return None
    for key in ("toolCallId", "tool_call_id"):
        item = value.get(key)
        if isinstance(item, str) and item:
            return item
    return None


def _tool_result_event(value: object, line_number: int, errors: list[str]) -> ToolResultEvent | None:
    if not isinstance(value, Mapping) or value.get("event") != "tool_result":
        if not isinstance(value, Mapping) or value.get("type") != "tool_result":
            return None
    ok = value.get("ok")
    if ok is not True and ok is not False:
        return None

    capability = value.get("capability")
    result = value.get("result", {})
    error = value.get("error")
    evidence_refs = value.get("evidence_refs", [])
    if (
        not isinstance(capability, str)
        or not isinstance(result, Mapping)
        or not isinstance(evidence_refs, list)
        or not all(isinstance(reference, str) for reference in evidence_refs)
        or (error is not None and not isinstance(error, Mapping))
    ):
        errors.append(f"trace tool_result event is malformed at line {line_number}")
        return None

    return ToolResultEvent(
        capability=capability,
        result=cast(Mapping[str, JsonValue], result),
        evidence_refs=tuple(evidence_refs),
        ok=ok,
        error=cast(Mapping[str, JsonValue] | None, error),
    )


def _trace_payload(event: object) -> object:
    if isinstance(event, Mapping) and event.get("event") == "pi_event":
        payload = event.get("payload")
        if isinstance(payload, Mapping):
            return payload
    return event


def _event_capability(value: object) -> str | None:
    if not isinstance(value, Mapping):
        return None
    for key in ("capability", "operation", "tool_name"):
        item = value.get(key)
        if isinstance(item, str):
            return _OPERATION_CAPABILITIES.get(item, item)
    for nested_key in ("payload", "args"):
        nested = value.get(nested_key)
        if isinstance(nested, Mapping):
            capability = _event_capability(nested)
            if capability is not None:
                return capability
    tool_name = value.get("toolName")
    if isinstance(tool_name, str):
        return tool_name
    return None


def _is_tool_event(value: object) -> bool:
    return isinstance(value, Mapping) and str(value.get("event", value.get("type", ""))).startswith("tool")


def _format_template(values: Sequence[str | None], case: ValidationCase) -> list[str]:
    mapping = {
        "case_id": case.id,
        "question_id": case.id,
        "question": case.question,
        "model": case.model or "",
    }
    return [value.format(**mapping) for value in values if value is not None]


def _check_evidence(case: ValidationCase, execution: CaseExecution, errors: list[str]) -> None:
    if not case.requirements.requires_evidence:
        return
    if execution.trace is None:
        errors.append("required evidence trace was not supplied")
        return
    evidence_refs = execution.trace.evidence_refs
    if not evidence_refs:
        errors.append("verification_evidence_missing")
        return
    if execution.run_path is None:
        errors.append("evidence run path missing")
        return
    missing = [ref for ref in evidence_refs if _evidence_path(execution.run_path, ref) is None]
    if missing:
        errors.append("evidence not found in current run: " + ", ".join(missing))


def _evidence_path(run_path: Path, evidence_ref: str) -> Path | None:
    if not evidence_ref.startswith("evidence:sha256:"):
        return None
    digest = evidence_ref.removeprefix("evidence:sha256:")
    if len(digest) != 64:
        return None
    candidates = (
        run_path / "evidence" / "network-facts" / f"network-fact-{digest}.json",
        run_path / "evidence" / "analysis" / f"analysis-evidence-{digest}.json",
    )
    for path in candidates:
        if path.is_file():
            return path
    return None


def _extract_evidence_refs(value: Mapping[str, object]) -> tuple[str, ...]:
    refs: list[str] = []
    single = value.get("evidence_ref")
    if isinstance(single, str):
        refs.append(single)
    many = value.get("evidence_refs")
    if isinstance(many, list):
        refs.extend(item for item in many if isinstance(item, str))
    return tuple(dict.fromkeys(refs))


def _require_json_mapping(value: object, description: str) -> Mapping[str, JsonValue]:
    if not isinstance(value, Mapping):
        raise RuntimeError(f"{description} was not an object")
    return cast(Mapping[str, JsonValue], value)


def _write_synthetic_evidence(run_path: Path, document: Mapping[str, object]) -> str:
    body = dict(document)
    payload = json.dumps(body, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    path = run_path / "evidence" / "analysis" / f"analysis-evidence-{digest}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload + "\n", encoding="utf-8")
    return f"evidence:sha256:{digest}"


def _scripted_topology_pi_source() -> str:
    return """#!/usr/bin/env python3
import json
import os
import subprocess

json.loads(input())
runtime = json.load(open(os.environ["CAPABILITY_AGENT_RUNTIME_DESCRIPTOR"], encoding="utf-8"))
domain = runtime["domains"][0]
catalog = json.load(open(domain["toolCatalogPath"], encoding="utf-8"))
by_capability = {tool["capability"]: tool for tool in catalog["tools"]}

def emit(payload):
    print(json.dumps(payload, ensure_ascii=False), flush=True)

def grid(capability, args):
    tool = by_capability[capability]
    key = {"binding_id": domain["bindingId"], "capability_id": capability}
    emit({"type": "tool_execution_start", "toolCallId": capability, "toolName": tool["name"], "capability_key": key, "capability": capability, "args": args})
    request = {
        "protocol": "grid-capability",
        "protocol_version": "1.0",
        "request_id": capability,
        "capability": capability,
        "arguments": args,
    }
    completed = subprocess.run(
        ["gridctl", "request", "--workspace", domain["workspacePath"]],
        input=json.dumps(request, ensure_ascii=False) + "\\n",
        text=True,
        capture_output=True,
        check=True,
    )
    response = json.loads(completed.stdout)
    result = response.get("result") or {}
    refs = []
    if isinstance(result.get("evidence_ref"), str):
        refs.append(result["evidence_ref"])
    refs.extend(result.get("evidence_refs") or [])
    emit({"type": "tool_result", "toolCallId": capability, "toolName": tool["name"], "capability_key": key, "capability": capability, "projector_id": tool.get("projector_id"), "ok": response.get("ok") is True, "result": result, "error": response.get("error"), "evidence_refs": refs})
    return result

def guide(resource_id):
    index = json.load(open(domain["guideIndexPath"], encoding="utf-8"))
    text = open(index["resources"][resource_id], encoding="utf-8").read()
    emit({"type": "tool_execution_start", "toolCallId": "guide-1", "toolName": "grid_guide_open", "args": {"resource_id": resource_id}})
    emit({"type": "tool_execution_end", "toolCallId": "guide-1", "toolName": "grid_guide_open", "isError": False, "result": {"resource_id": resource_id}})

emit({"type": "response", "command": "prompt", "success": True})
guide("topology-analysis")
opened = grid("context.open", {"model_id": "ieee39"})
result = grid("topology.branch.endpoints.get", {"context_ref": opened["context_ref"], "kind": "line", "namespace": "pandapower_index", "identifier": "11"})
ref = result["evidence_ref"]
answer = f"线路11连接母线{result['from_bus']['name']}与{result['to_bus']['name']}。"
emit({"type": "text_delta", "text": answer})
emit({"type": "message_end", "message": {"role": "assistant", "content": [{"type": "text", "text": answer}], "stopReason": "stop"}})
emit({"type": "agent_end"})
"""


def _emit(record: Mapping[str, object]) -> None:
    print(json.dumps(record, ensure_ascii=False, sort_keys=True), flush=True)


if __name__ == "__main__":
    sys.exit(main())
