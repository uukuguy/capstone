"""Application-owned deterministic execution of registered scripted cases."""
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
    ApplicationRequest,
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
from pandapower_application.composition import build_generic_application, run_generic_application
from pandapower_application.registry import ApplicationRegistry
from pandapower_domain.provisioning import PandapowerRuntimeProvisioner

SemanticEventCallback = Callable[[Mapping[str, object], int | None], None]

def _render_scripted_answer(calls: Sequence[Mapping[str, object]]) -> str:
    """Render reader-facing text from the current turn's authority results.

    Scripted runs still execute the real registered capabilities.  Their answer
    must therefore be a small deterministic projection of those returned
    documents, rather than an instruction echo that only proves the harness
    advanced to the next turn.
    """

    for call in reversed(calls):
        capability = call.get("capability")
        result = call.get("result")
        if not isinstance(capability, str) or not isinstance(result, Mapping):
            continue
        if capability == "topology.branch.endpoints.get":
            branch = result.get("branch")
            from_bus = result.get("from_bus")
            to_bus = result.get("to_bus")
            if isinstance(branch, Mapping) and isinstance(from_bus, Mapping) and isinstance(to_bus, Mapping):
                branch_name = branch.get("name", branch.get("index", "目标"))
                from_name = from_bus.get("name", from_bus.get("index", "未知"))
                to_name = to_bus.get("name", to_bus.get("index", "未知"))
                return f"线路 {branch_name} 连接母线 {from_name} 与母线 {to_name}。"
        if capability == "analysis.powerflow.ac.run":
            converged = result.get("converged") is True
            loss = result.get("total_active_loss")
            if isinstance(loss, Mapping) and isinstance(loss.get("value"), int | float):
                state = "已收敛" if converged else "未收敛"
                return f"交流潮流{state}；系统总有功网损为 {float(loss['value']):.2f} {loss.get('unit', 'MW')}。"
            return "交流潮流已完成，但本轮未返回可展示的有功网损。"
        if capability == "result.branches.rank":
            branches = result.get("branches")
            if isinstance(branches, list):
                rows = [
                    (item.get("pandapower_index"), item.get("loading_percent", item.get("metric_value")))
                    for item in branches
                    if isinstance(item, Mapping)
                    and isinstance(item.get("pandapower_index"), int)
                    and isinstance(item.get("loading_percent", item.get("metric_value")), int | float)
                ]
                if rows:
                    values = "、".join(f"线路 {line}（{float(value):.1f}%）" for line, value in rows)
                    return f"按当前潮流结果，负载率最高的 {len(rows)} 条线路为：{values}。"
        if capability == "analysis.contingency.n_minus_one.run":
            scenarios = result.get("scenarios")
            if isinstance(scenarios, list) and scenarios and isinstance(scenarios[0], Mapping):
                scenario = scenarios[0]
                violations = scenario.get("violations")
                count = len(violations) if isinstance(violations, list) else 0
                status = scenario.get("status", "未知")
                maximum = scenario.get("max_loading_percent")
                suffix = f"最大线路负载率为 {float(maximum):.1f}%。" if isinstance(maximum, int | float) else ""
                return f"单支路静态校核状态为 {status}，发现 {count} 项越限。{suffix}"
        if capability == "model.constraints.describe":
            constraints = result.get("constraints")
            if isinstance(constraints, list) and constraints:
                labels = []
                for item in constraints:
                    if not isinstance(item, Mapping):
                        continue
                    quantity = item.get("quantity")
                    subject = item.get("subject_kind")
                    upper = item.get("upper")
                    unit = item.get("unit")
                    if isinstance(quantity, str) and isinstance(subject, str):
                        limit = f"≤ {upper} {unit}" if isinstance(upper, int | float) and isinstance(unit, str) else ""
                        labels.append(f"{subject} 的 {quantity}{limit}")
                if labels:
                    return "已读取模型显式约束：" + "；".join(labels) + "。"
        if capability == "model.element.get":
            element = result.get("element")
            if isinstance(element, Mapping):
                name = element.get("name", element.get("index", "目标"))
                return f"已解析线路 {name}，正在读取其端点与当前运行约束。"
    return "本步已完成，结果与证据已写入当前运行。"


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
        on_progress: Callable[[dict[str, object]], None] | None = None,
    ) -> None:
        self.case = case
        self.run_id = str(case["run_id"])
        self.on_progress = on_progress
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

    def _notify_progress(self, event: dict[str, object]) -> None:
        if self.on_progress is not None:
            try:
                self.on_progress(event)
            except Exception:
                pass  # Progress observation cannot veto an admitted answer.

    @property
    def current_result_refs(self) -> tuple[str, ...]:
        return self._current_result_refs

    @property
    def current_evidence_refs(self) -> tuple[str, ...]:
        return self._current_evidence_refs

    @property
    def current_context_ref(self) -> str | None:
        return self._context_ref

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
        if self.on_progress is not None:
            ordinal = self._question_index + 1
            total = len(questions)
            self._notify_progress({"event": "turn_started", "ordinal": ordinal,
                              "total": total, "instruction": question, "run_id": self.run_id,
                              "message": f"开始第 {ordinal}/{total} 轮：{question}"})
        steps = scripted.get("steps")
        if not isinstance(steps, list):
            raise RuntimeError("scripted application question has invalid semantic steps")
        turn_start = len(self.calls)
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
        scripted_answer = scripted.get("answer")
        if scripted_answer is not None:
            if not isinstance(scripted_answer, str) or not scripted_answer.strip():
                raise RuntimeError("scripted application answer is invalid")
            return scripted_answer
        return _render_scripted_answer(self.calls[turn_start:])

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
        if self.on_progress is not None:
            self._notify_progress({"event": "capability_started", "ordinal": self._question_index + 1,
                              "total": len(self.case["questions"]), "capability": capability,
                              "run_id": self.run_id,
                              "message": f"第 {self._question_index + 1}/{len(self.case['questions'])} 轮：开始 {capability}"})
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
        if self.on_progress is not None:
            self._notify_progress({"event": "capability_completed", "ordinal": self._question_index + 1,
                              "total": len(self.case["questions"]), "capability": capability,
                              "run_id": self.run_id,
                              "message": f"第 {self._question_index + 1}/{len(self.case['questions'])} 轮：完成 {capability}"})
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
        answer_summary: str | None = None,
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
            answer_summary=answer_summary,
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
    on_progress: Callable[[dict[str, object]], None] | None = None,
    instruction_source: Iterable[str] | None = None,
    on_semantic_event: Callable[[Mapping[str, object]], None] | None = None,
    on_prepared: Callable[[object], None] | None = None,
    on_transport: Callable[[ScriptedApplicationTransport], None] | None = None,
) -> ApplicationExecution:
    """Run one JSON scripted case through the generic application entry point."""

    document = _load_application_document(case)
    application_id = str(document["application_id"])
    run_id = str(document["run_id"])
    _remove_generated_application_run(runs_root, run_id)

    from pandapower_application.profile import build_pandapower_application_profile

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
    if on_prepared is not None:
        on_prepared(prepared)
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
                "questions": [] if instruction_source is not None else list(questions),
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
        on_progress=on_progress,
    )
    if on_transport is not None:
        on_transport(transport)
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
        semantic_event_observer=on_semantic_event,
    )
    if instruction_source is None:
        outcome = run_generic_application(
            application_id, questions, application=application, run_id=run_id,
        )
    else:
        def checked_instructions() -> Iterable[str]:
            count = 0
            for instruction in instruction_source:
                if count >= len(questions) or instruction != questions[count]:
                    raise ValueError("scripted application instruction order changed")
                count += 1
                yield instruction
            if count != len(questions):
                raise ValueError("scripted application instructions are incomplete")

        outcome = application.run_stream(
            ApplicationRequest(application_id, (), run_id), checked_instructions(),
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
        answer = question.get("answer")
        if answer is not None and (not isinstance(answer, str) or not answer.strip()):
            raise ValueError("application case question answer is invalid")
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
