#!/usr/bin/env python3
"""Run registered PyPSA business cases through a local scripted agent turn.

The scripted provider is a deterministic acceptance harness. It exercises the
real application, Domain Packs, handoff, authority, solver, and evidence path.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
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
                 catalog: Any, handoff: ReferenceHandoffService) -> None:
        self.case = case
        self.request = request
        self.prepared = prepared
        self.handoff = handoff
        self.tools = {
            (tool.key.binding_id, tool.key.capability_id): tool
            for tool in catalog.domain_tools
        }
        self.results: dict[str, dict[str, Any]] = {}
        self.answer = ""
        self._event = 0

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def _invoke(self, binding_id: str, capability: str, arguments: dict[str, object],
                on_semantic_event: Any, turn_id: str, *, target_result: dict[str, Any] | None = None
                ) -> dict[str, Any]:
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
        return result

    def prompt_and_wait(self, question: str, *, on_semantic_event: Any,
                        correlation_id: str, on_heartbeat: Any) -> str:
        if question != self.case["question"]:
            raise ValueError("case question changed during run")
        on_heartbeat()
        opened = self._invoke("source", "model.open", {"catalog_id": self.case["model_id"]},
                              on_semantic_event, correlation_id)
        model_ref = opened["model_ref"]
        dispatch_count = 0
        for capability in self.case["workflow"][1:]:
            if capability == "model.derive_series":
                scenario = self.case["scenario"]
                derived = self._invoke("source", capability, {
                    "model_ref": model_ref, "load_id": scenario["load_id"],
                    "p_set_mw": scenario["variant_mw"],
                }, on_semantic_event, correlation_id)
                model_ref = derived["model_ref"]
            elif capability.startswith("model."):
                self._invoke("source", capability, {"model_ref": model_ref}, on_semantic_event, correlation_id)
            elif capability == "operations.dispatch":
                result, receipt = self.handoff.invoke_target(
                    source_binding_id="source", target_binding_id="operations",
                    reference=model_ref, reference_kind="model", purpose="operations",
                    capability=capability, arguments={},
                )
                dispatched = self._invoke("operations", capability,
                             {"reference": model_ref, "handoff_ref": receipt.receipt_ref},
                             on_semantic_event, correlation_id, target_result=result)
                dispatch_count += 1
                if dispatch_count == 1 and "model.derive_series" in self.case["workflow"]:
                    self.results["baseline_dispatch"] = dispatched
            else:
                raise ValueError(f"case capability is not supported: {capability}")
        inspection = self.results["model.inspect"]
        if "baseline_dispatch" in self.results:
            baseline = self.results["baseline_dispatch"]
            variant = self.results["operations.dispatch"]
            delta = variant["objective"] - baseline["objective"]
            self.answer = (
                f"{self.case['title']}：基准与增长情景分别为 "
                f"{baseline['status']}/{baseline['condition']} 和 "
                f"{variant['status']}/{variant['condition']}。"
                f"模型运行成本目标由 {baseline['objective']:.2f} 变为 "
                f"{variant['objective']:.2f}，增加 {delta:.2f}（模型成本单位）。"
                f"{self.case['limitations'][0]}"
            )
            return self.answer
        if "operations.dispatch" in self.results:
            dispatch = self.results["operations.dispatch"]
            self.answer = (
                f"{self.case['title']}：固定容量线性调度求解状态为 {dispatch['status']}/{dispatch['condition']}，"
                f"目标值为 {dispatch['objective']:.2f}（模型的运行成本单位）。"
                f"网络包含 {inspection['component_counts']['Bus']} 个母线、"
                f"{inspection['component_counts']['Generator']} 台发电机。"
                f"{self.case['limitations'][0]}"
            )
            return self.answer
        self.answer = (
            f"{self.case['title']}：网络包含 {inspection['component_counts']['Bus']} 个母线、"
            f"{inspection['component_counts']['Line']} 条交流线路和 "
            f"{inspection['component_counts'].get('Link', 0)} 条链路。"
            f"{self.case['limitations'][0]}"
        )
        return self.answer


def run_case(case_id: str, *, root: Path = RUN_ROOT) -> dict[str, Any]:
    case = next((item for item in load_cases() if item["id"] == case_id), None)
    if case is None:
        raise ValueError("business case is not registered")
    if case["status"] != "runnable":
        raise ValueError("business case is catalog-only and has no verified agent workflow")
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
        provider = CaseProvider(case, request, prepared_application, catalog, handoff)
        providers.append(provider)
        return provider

    application = AgentApplication(
        profile=profile, prepared_application=prepared, workspace=workspace, store=store,
        provider_factory=provider_factory,
    )
    outcome = application.run(ApplicationRequest(profile.manifest.application_id, (case["question"],), run_id))
    if outcome.status != "completed" or not providers:
        raise RuntimeError(f"business case failed: {outcome.error}")
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
    args = parser.parse_args(argv)
    try:
        if args.command == "list":
            print(json.dumps({"cases": load_cases()}, ensure_ascii=False))
        else:
            print(json.dumps(run_case(args.case_id), ensure_ascii=False))
    except (ValueError, RuntimeError) as exc:
        print(f"PyPSA case error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
