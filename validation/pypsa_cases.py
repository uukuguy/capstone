#!/usr/bin/env python3
"""Run registered PyPSA business cases through local scripted agent turns.

The scripted provider is a deterministic acceptance harness. It exercises the
real application, Domain Packs, handoff, authority, solver, and evidence path.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from collections.abc import Callable, Sequence
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from capability_agent.application.composition import prepare_application
from capability_agent.application.context_store import ApplicationContextStore
from capability_agent.application.manifest import ApplicationManifest
from capability_agent.application.output import JsonOutputRenderer
from capability_agent.application.profile import (
    ApplicationProfile, CredentialScope, DataSharingPolicy, DomainBinding, ReferenceGrant,
)
from capability_agent.application.reference_handoff import ReferenceHandoffService
from capability_agent.application.registry import DomainRegistry
from capability_agent.application.reporting import GenericReportShell
from capability_agent.application.runner import AgentApplication, ApplicationRequest
from capability_agent.application.workspace import ApplicationWorkspace
from pypsa_model_authority.catalog import list_registered_models
from pypsa_network_modeling.profile import build_pypsa_network_modeling_profile
from pypsa_power_operations.profile import build_pypsa_power_operations_profile


CASES_PATH = Path(__file__).with_name("pypsa-cases") / "cases.json"
RUN_ROOT = Path.cwd() / "runs" / "pypsa-cases"


def _notify_progress(callback: Callable[[dict[str, object]], None] | None,
                     event: dict[str, object]) -> None:
    if callback is not None:
        try:
            callback(event)
        except Exception:
            pass  # Progress observation cannot veto an admitted answer.


def load_cases() -> tuple[dict[str, Any], ...]:
    document = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    if document.get("schema") != "capstone-pypsa-business-cases/1.0":
        raise ValueError("PyPSA business case catalog schema is invalid")
    cases = tuple(document["cases"])
    catalog_ids = {item["catalog_id"] for item in list_registered_models()}
    if len({case["id"] for case in cases}) != len(cases) or any(
        case["model_id"] not in catalog_ids
        or case["status"] not in {"runnable", "catalog-only"}
        or (case["status"] == "runnable" and case["workflow"][0] != "model.open")
        or (case["status"] == "runnable" and (
            len(case["demo_workflow"]) != len(case["introduction"]["demo_instructions"])
            or [step for turn in case["demo_workflow"] for step in turn] != case["workflow"]
        ))
        for case in cases
    ):
        raise ValueError("PyPSA business case catalog is inconsistent")
    return cases


class EmptyCredentials:
    def issue(self, *, binding_id: str, scope: Any) -> SimpleNamespace:
        del binding_id
        return SimpleNamespace(scope_id=scope.scope_id, credentials={})


class CaseProvider:
    """Deterministic tool caller that records real semantic events for one case."""

    def __init__(self, case: dict[str, Any], request: ApplicationRequest, prepared: Any,
                 catalog: Any, handoff: ReferenceHandoffService,
                 on_progress: Callable[[dict[str, object]], None] | None = None,
                 demo: bool | None = None) -> None:
        self.case = case
        self.request = request
        self.prepared = prepared
        self.handoff = handoff
        self.on_progress = on_progress
        self.demo = len(request.questions) > 1 if demo is None else demo
        self.total = len(case["introduction"]["demo_instructions"]) if self.demo else 1
        self.tools = {
            (tool.key.binding_id, tool.key.capability_id): tool
            for tool in catalog.domain_tools
        }
        self.results: dict[str, dict[str, Any]] = {}
        self.answer = ""
        self._event = 0
        self._turn_index = 0
        self._dispatch_count = 0
        self._model_ref: str | None = None

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def _report_capability_started(self, capability: str) -> None:
        _notify_progress(self.on_progress, {"event": "capability_started", "ordinal": self._turn_index,
                          "total": self.total, "capability": capability,
                          "run_id": self.request.run_id,
                          "message": f"第 {self._turn_index}/{self.total} 轮：开始 {capability}"})

    def _invoke(self, binding_id: str, capability: str, arguments: dict[str, object],
                on_semantic_event: Any, turn_id: str, *, target_result: dict[str, Any] | None = None,
                progress_started: bool = False,
                ) -> dict[str, Any]:
        if not progress_started:
            self._report_capability_started(capability)
        self._event += 1
        identity = {
            "call_id": f"case-tool-{self._event}",
            "tool_name": self.tools[(binding_id, capability)].name,
            "capability": capability,
            "capability_key": {"binding_id": binding_id, "capability_id": capability},
            "run_id": self.request.run_id, "turn_id": turn_id,
        }
        on_semantic_event({**identity, "type": "tool_execution_start", "arguments": arguments}, self._event * 2 - 1)
        result = target_result or self.prepared.bindings[binding_id].endpoint.executor.invoke(capability, arguments)
        projector = "pypsa-operations-result-v1" if binding_id == "operations" else "pypsa-model-revision-v1"
        result_kind = (
            "pypsa-operations.result" if binding_id == "operations"
            else {"model.open": "pypsa-model.revision", "model.derive_series": "pypsa-model.revision",
                  "model.inspect": "pypsa-model.inspection",
                  "model.topology": "pypsa-model.topology"}[capability]
        )
        try:
            on_semantic_event({
                **identity, "type": "tool_result", "ok": True, "result": result,
                "result_refs": [result["result_ref"]], "evidence_refs": result["evidence_refs"],
                "projector_id": projector, "result_kind": result_kind,
            }, self._event * 2)
        except Exception as exc:
            print(f"{capability} event rejected: {exc!r}; cause={exc.__cause__!r}", file=sys.stderr)
            raise
        self.results[capability] = result
        if self.on_progress is not None:
            _notify_progress(self.on_progress, {"event": "capability_completed", "ordinal": self._turn_index,
                              "total": self.total, "capability": capability,
                              "run_id": self.request.run_id,
                              "message": f"第 {self._turn_index}/{self.total} 轮：完成 {capability}"})
        return result

    def prompt_and_wait(self, question: str, *, on_semantic_event: Any,
                        correlation_id: str, on_heartbeat: Any) -> str:
        demo = self.demo
        if demo:
            instructions = self.case["introduction"]["demo_instructions"]
            if self._turn_index >= len(instructions) or question != instructions[self._turn_index]:
                raise ValueError("case instruction changed during run")
            workflow = self.case["demo_workflow"][self._turn_index]
        else:
            if question != self.case["question"]:
                raise ValueError("case question changed during run")
            workflow = self.case["workflow"]
        self._turn_index += 1
        if self.on_progress is not None:
            _notify_progress(self.on_progress, {"event": "turn_started", "ordinal": self._turn_index,
                              "total": self.total, "instruction": question,
                              "run_id": self.request.run_id,
                              "message": f"开始第 {self._turn_index}/{self.total} 轮：{question}"})
        on_heartbeat()
        for capability in workflow:
            if capability == "model.open":
                opened = self._invoke("source", capability,
                                      {"catalog_id": self.case["model_id"]},
                                      on_semantic_event, correlation_id)
                self._model_ref = opened["model_ref"]
            elif capability == "model.derive_series":
                if self._model_ref is None:
                    raise ValueError("model revision is not open")
                scenario = self.case["scenario"]
                derived = self._invoke("source", capability, {
                    "model_ref": self._model_ref, "load_id": scenario["load_id"],
                    "p_set_mw": scenario["variant_mw"],
                }, on_semantic_event, correlation_id)
                self._model_ref = derived["model_ref"]
            elif capability.startswith("model."):
                if self._model_ref is None:
                    raise ValueError("model revision is not open")
                self._invoke("source", capability, {"model_ref": self._model_ref},
                             on_semantic_event, correlation_id)
            elif capability == "operations.dispatch":
                if self._model_ref is None:
                    raise ValueError("model revision is not open")
                self._report_capability_started(capability)
                result, receipt = self.handoff.invoke_target(
                    source_binding_id="source", target_binding_id="operations",
                    reference=self._model_ref, reference_kind="model", purpose="operations",
                    capability=capability, arguments={},
                )
                dispatched = self._invoke("operations", capability,
                             {"reference": self._model_ref, "handoff_ref": receipt.receipt_ref},
                             on_semantic_event, correlation_id, target_result=result,
                             progress_started=True)
                self._dispatch_count += 1
                if self._dispatch_count == 1 and "model.derive_series" in self.case["workflow"]:
                    self.results["baseline_dispatch"] = dispatched
            else:
                raise ValueError(f"case capability is not supported: {capability}")
        self.answer = self._answer_for_turn(workflow, demo=demo)
        return self.answer

    def _answer_for_turn(self, workflow: list[str], *, demo: bool) -> str:
        if demo and not workflow:
            return ("结构核查已完成。后续潮流研究需要指定运行快照、注入与约束，"
                    "当前连接关系不能推出功率流或输电能力。")
        if demo and "model.derive_series" in workflow:
            return ("已在同一运行中创建增长情景的独立模型修订，基准修订仍保留；"
                    "增长情景尚未求解。")
        inspection = self.results["model.inspect"]
        if self._dispatch_count >= 2 and "baseline_dispatch" in self.results:
            baseline = self.results["baseline_dispatch"]
            variant = self.results["operations.dispatch"]
            delta = variant["objective"] - baseline["objective"]
            base_dispatch = baseline.get("generator_dispatch_mw", {})
            variant_dispatch = variant.get("generator_dispatch_mw", {})
            changed_generators = [
                name for name in sorted(set(base_dispatch) | set(variant_dispatch))
                if len(base_dispatch.get(name, ())) != len(variant_dispatch.get(name, ()))
                or any(abs(before - after) > 1e-6 for before, after in zip(
                    base_dispatch.get(name, ()), variant_dispatch.get(name, ()), strict=True
                ))
            ]
            generation_note = (
                f"逐时出力发生变化的机组包括 {', '.join(changed_generators[:4])}。"
                if changed_generators else "逐时机组出力明细见本轮结果。"
            )
            return (
                f"{self.case['title']}：基准与增长情景分别为 "
                f"{baseline['status']}/{baseline['condition']} 和 "
                f"{variant['status']}/{variant['condition']}。"
                f"模型运行成本目标由 {baseline['objective']:.2f} 变为 "
                f"{variant['objective']:.2f}，增加 {delta:.2f}（模型成本单位）。"
                f"{generation_note}"
                f"{self.case['limitations'][0]}"
            )
        if "operations.dispatch" in workflow:
            dispatch = self.results["operations.dispatch"]
            generation = dispatch.get("generation_by_carrier_mw", {})
            lines = dispatch.get("top_line_loading", ())
            summary = (
                f"按能源类型汇总了 {len(generation)} 类逐时发电结果。"
                if generation else ""
            )
            if lines:
                examples = "、".join(
                    f"{item['line_id']}（{item['max_loading_pct']:.1f}%）"
                    for item in lines[:3]
                )
                summary += f"负载率较高的线路示例：{examples}。"
            return (
                f"{self.case['title']}：固定容量线性调度求解状态为 {dispatch['status']}/{dispatch['condition']}，"
                f"目标值为 {dispatch['objective']:.2f}（模型的运行成本单位）。"
                f"网络包含 {inspection['component_counts']['Bus']} 个母线、"
                f"{inspection['component_counts']['Generator']} 台发电机。"
                f"{summary}"
                f"{self.case['limitations'][0]}"
            )
        if demo and "model.topology" in workflow:
            topology = self.results["model.topology"]
            branches = topology["lines"] + topology["links"]
            connections = ""
            if len(branches) <= 12:
                carriers = {bus["id"]: bus["carrier"] for bus in topology["buses"]}

                def endpoint(bus_id: str) -> str:
                    return f"{bus_id}({carriers.get(bus_id, '未知')})"

                line_text = "、".join(
                    f"{item['id']} {endpoint(item['from_bus'])}→{endpoint(item['to_bus'])}"
                    for item in topology["lines"]
                )
                link_text = "、".join(
                    f"{item['id']} {endpoint(item['from_bus'])}→{endpoint(item['to_bus'])}"
                    for item in topology["links"]
                )
                connections = f"Line 组件：{line_text}。Link 组件：{link_text}。"
            omitted = sum(topology["omitted_counts"].values())
            return (f"{self.case['title']}：已读取同一模型修订的受限拓扑预览；"
                    f"母线预览 {len(topology['buses'])} 个，省略组件 {omitted} 个。"
                    f"{connections}"
                    "拓扑连接不能替代调度或潮流结果。")
        return (
            f"{self.case['title']}：网络包含 {inspection['component_counts']['Bus']} 个母线、"
            f"{inspection['component_counts']['Line']} 个 Line 组件和 "
            f"{inspection['component_counts'].get('Link', 0)} 个 Link 组件。"
            f"{self.case['limitations'][0]}"
        )


def run_case(case_id: str, *, root: Path = RUN_ROOT,
             instructions: Sequence[str] | None = None,
             on_progress: Callable[[dict[str, object]], None] | None = None) -> dict[str, Any]:
    case = next((item for item in load_cases() if item["id"] == case_id), None)
    if case is None:
        raise ValueError("business case is not registered")
    if case["status"] != "runnable":
        raise ValueError("business case is catalog-only and has no verified agent workflow")
    if isinstance(instructions, str):
        raise ValueError("case instructions must be an ordered list")
    selected_instructions = None if instructions is None else tuple(instructions)
    if (selected_instructions is not None
            and selected_instructions != tuple(case["introduction"]["demo_instructions"])):
        raise ValueError("case instructions must match the registered demo sequence")
    questions = (case["question"],) if selected_instructions is None else selected_instructions
    model = build_pypsa_network_modeling_profile()
    operations = build_pypsa_power_operations_profile(source_binding_id="source")
    registry = DomainRegistry()
    registry.register(model.manifest.domain_id, model.manifest.version, lambda: model)
    registry.register(operations.manifest.domain_id, operations.manifest.version, lambda: operations)
    run_id = f"pypsa-case-{uuid.uuid4().hex[:16]}"
    workspace = ApplicationWorkspace.create(root, run_id=run_id, binding_ids=("source", "operations"))
    profile = ApplicationProfile(
        manifest=ApplicationManifest(
            "pypsa-business-cases", "1.0", "PyPSA business cases",
            "application-context/1.0", "application-result/1.0", "artifact/1.0", "agent_",
        ),
        domains=(
            DomainBinding("source", "pypsa_model_", model, CredentialScope(), DataSharingPolicy()),
            DomainBinding("operations", "pypsa_ops_", operations, CredentialScope(), DataSharingPolicy()),
        ),
        output_renderer=JsonOutputRenderer(),
        application_policy=SimpleNamespace(load=lambda: "Use only registered PyPSA capabilities and current-run evidence."),
        report_shell=GenericReportShell(),
        acceptance_profile=SimpleNamespace(cases=lambda: ()),
        reference_grants=(ReferenceGrant("source", "operations", "model", "operations", "operations"),),
    )
    credentials = EmptyCredentials()
    prepared = prepare_application(profile, registry=registry, workspace=workspace.root, credentials=credentials)
    store = ApplicationContextStore.initialize(workspace)
    handoff = ReferenceHandoffService(profile, workspace, store, prepared.bindings)
    providers: list[CaseProvider] = []

    def provider_factory(*, request: ApplicationRequest, prepared_application: Any,
                         catalog: Any, **_: Any) -> CaseProvider:
        provider = CaseProvider(case, request, prepared_application, catalog, handoff,
                                on_progress=on_progress)
        providers.append(provider)
        return provider

    application = AgentApplication(
        profile=profile, prepared_application=prepared, workspace=workspace, store=store,
        provider_factory=provider_factory,
    )
    outcome = application.run(ApplicationRequest(profile.manifest.application_id, questions, run_id))
    if outcome.status != "completed" or not providers:
        raise RuntimeError(f"business case failed: {outcome.error}")
    if outcome.completed_questions != len(questions) or len(outcome.result.core.answer_refs) != len(questions):
        raise RuntimeError("business case did not commit every instruction")
    turns = []
    for ordinal, (question, answer_ref) in enumerate(
        zip(questions, outcome.result.core.answer_refs, strict=True), start=1
    ):
        turn_id = f"{run_id}-t{ordinal:03d}"
        answer = json.loads((workspace.turns_path / turn_id / "answer.json").read_text(encoding="utf-8"))
        if answer["run_id"] != run_id or answer["turn_id"] != turn_id:
            raise RuntimeError("business case answer belongs to another run or turn")
        turns.append({
            "turn_id": turn_id, "instruction": question,
            "answer": answer["answer_output"], "answer_ref": answer_ref,
            "result_refs": answer["result_refs"], "evidence_refs": answer["evidence_refs"],
        })
    results = providers[0].results
    admitted = {
        binding_id: set(outcome.result.domains[binding_id].payload["result_refs"])
        for binding_id in ("source", "operations")
    }
    if any(
        result["result_ref"] not in admitted[
            "operations" if capability in {"operations.dispatch", "baseline_dispatch"} else "source"
        ]
        for capability, result in results.items()
    ):
        raise RuntimeError("business case output omitted an admitted authority result")
    metadata = next(item for item in list_registered_models() if item["catalog_id"] == case["model_id"])
    solver = results.get("operations.dispatch")
    baseline = results.get("baseline_dispatch")
    presentation = {
        "schema": "capstone-pypsa-case-presentation/1.0",
        "case_id": case["id"], "title": case["title"], "question": case["question"],
        "run_id": run_id, "status": outcome.status,
        "model": metadata,
        "answer": providers[0].answer,
        "turns": turns,
        "answer_refs": list(outcome.result.core.answer_refs),
        "component_counts": results["model.inspect"]["component_counts"],
        "snapshot_count": results["model.inspect"]["snapshot_count"],
        "topology": {
            "buses": results["model.topology"]["buses"],
            "lines": results["model.topology"]["lines"],
            "links": results["model.topology"]["links"],
            "transformers": results["model.topology"]["transformers"],
            "omitted_counts": results["model.topology"]["omitted_counts"],
            "selection": results["model.topology"]["selection"],
            "coordinate_status": results["model.topology"]["coordinate_status"],
        },
        "solver": None if solver is None else {
            key: solver[key] for key in (
                "status", "condition", "objective_kind", "objective", "generator_count",
                "generation_by_carrier_mw", "total_generation_mw", "top_line_loading",
                "omitted_line_count", "generator_dispatch_mw",
            ) if key in solver
        },
        "scenario": case.get("scenario"),
        "comparison": None if baseline is None or solver is None else {
            "baseline_objective": baseline["objective"],
            "variant_objective": solver["objective"],
            "objective_delta": solver["objective"] - baseline["objective"],
            "objective_kind": solver["objective_kind"],
            "baseline_status": baseline["condition"],
            "variant_status": solver["condition"],
            "baseline_result_ref": baseline["result_ref"],
            "variant_result_ref": solver["result_ref"],
        },
        "limitations": case["limitations"],
        "result_refs": list(dict.fromkeys(result["result_ref"] for result in results.values())),
        "evidence_refs": list(dict.fromkeys(
            ref for result in results.values() for ref in result["evidence_refs"]
        )),
        "artifacts": [
            {
                "binding_id": "operations" if capability in {"operations.dispatch", "baseline_dispatch"} else "source",
                "capability": capability,
                "result_ref": result["result_ref"],
                "evidence_refs": result["evidence_refs"],
            }
            for capability, result in results.items()
        ],
    }
    (workspace.root / "presentation.json").write_text(json.dumps(presentation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return presentation


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    command = parser.add_subparsers(dest="command", required=True)
    command.add_parser("list")
    runner = command.add_parser("run")
    runner.add_argument("case_id")
    instruction_source = runner.add_mutually_exclusive_group()
    instruction_source.add_argument("--demo", action="store_true")
    instruction_source.add_argument("--instructions", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "list":
            print(json.dumps({"cases": load_cases()}, ensure_ascii=False))
        else:
            instructions = None
            if args.demo:
                case = next((item for item in load_cases() if item["id"] == args.case_id), None)
                if case is None or case["status"] != "runnable":
                    raise ValueError("business case has no registered demo instructions")
                instructions = tuple(case["introduction"]["demo_instructions"])
            elif args.instructions is not None:
                instructions = tuple(
                    line.strip() for line in args.instructions.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                )
            def report_progress(event: dict[str, object]) -> None:
                print(json.dumps({"schema": "capstone-client-progress/1.0",
                                  "application_id": "pypsa-business-cases", **event},
                                 ensure_ascii=False), file=sys.stderr, flush=True)

            print(json.dumps(run_case(args.case_id, instructions=instructions,
                                      on_progress=report_progress), ensure_ascii=False))
    except (ValueError, RuntimeError) as exc:
        print(f"PyPSA case error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
