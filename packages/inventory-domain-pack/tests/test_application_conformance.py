"""Real inventory authority conformance; only the model transport is scripted."""
from __future__ import annotations

import json
import pytest
from dataclasses import replace
from types import SimpleNamespace

from capability_agent.application.context_store import ApplicationContextStore
from capability_agent.application.errors import CapabilityTransportError
from capability_agent.application.manifest import ApplicationManifest
from capability_agent.application.output import JsonOutputRenderer
from capability_agent.application.profile import (
    ApplicationProfile, CredentialScope, DataSharingPolicy, DomainBinding,
)
from capability_agent.application.registry import DomainRegistry
from capability_agent.application.reporting import GenericReportShell
from capability_agent.application.runner import AgentApplication, ApplicationRequest
from capability_agent.application.workspace import ApplicationWorkspace
from inventory_domain.profile import build_inventory_profile


class EmptyCredentials:
    def issue(self, *, binding_id, scope):
        assert binding_id == "inventory" and scope.credential_names == ()
        return SimpleNamespace(scope_id=scope.scope_id, credentials={})


class ScriptedInventory:
    def __init__(self, request, prepared, catalog, turns, overrides, after_invoke):
        self.request = request
        self.binding = prepared.bindings["inventory"]
        self.tools = {tool.key.capability_id: tool for tool in catalog.domain_tools}
        self.effects = {doc["id"]: doc["context_effect"] for doc in self.binding.runtime.capability_documents}
        self.turns = iter(turns)
        self.overrides = overrides
        self.after_invoke = after_invoke
        self.context_ref = None
        self.calls = []
        self.events = []
        self.started = self.stopped = False

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True

    def prompt_and_wait(self, question, *, on_semantic_event, correlation_id, on_heartbeat):
        on_heartbeat()
        steps = next(self.turns)
        for capability, supplied in steps:
            arguments = {key: self.context_ref if value == "$context" else value for key, value in supplied.items()}
            tool = self.tools[capability]
            identity = {
                "call_id": f"call-{len(self.calls) + 1}",
                "tool_name": tool.name, "capability": capability,
                "capability_key": {"binding_id": "inventory", "capability_id": capability},
                "run_id": self.request.run_id, "turn_id": correlation_id,
            }
            self._emit(on_semantic_event, {**identity, "type": "tool_execution_start", "arguments": arguments})
            try:
                if capability in self.overrides:
                    result = self.overrides[capability]
                else:
                    result = self.binding.endpoint.executor.invoke(capability, arguments)
            except CapabilityTransportError:
                # The public credential-screening executor intentionally hides
                # raw domain exceptions. Model recovery uses its typed failure.
                error = {"code": "capability_transport_failed"}
                self.calls.append((capability, arguments, error))
                self._emit(on_semantic_event, {**identity, "type": "tool_result", "ok": False, "error": error})
                continue
            if self.after_invoke is not None:
                self.after_invoke(capability, result, self.binding)
            self.calls.append((capability, arguments, result))
            if "context_ref" in result:
                self.context_ref = result["context_ref"]
            effect = self.effects[capability]
            self._emit(on_semantic_event, {
                **identity, "type": "tool_result", "ok": True, "result": result,
                "result_refs": [result["result_ref"]] if "result_ref" in result else [],
                "evidence_refs": result.get("evidence_refs", []),
                "projector_id": effect["projector"], "result_kind": effect.get("result_kind"),
            })
        return "The requested inventory operation has been processed."

    def _emit(self, callback, event):
        self.events.append(event)
        callback(event, len(self.events))


def run_application(tmp_path, turns, *, questions=None, report_shell=None, domain=None, overrides=None, after_invoke=None):
    domain = domain or build_inventory_profile()
    registry = DomainRegistry()
    registry.register(domain.manifest.domain_id, domain.manifest.version, lambda: domain)
    workspace = ApplicationWorkspace.create(tmp_path.resolve() / "runs", binding_ids=("inventory",))
    profile = ApplicationProfile(
        manifest=ApplicationManifest(
            "inventory-conformance", "1.0", "Inventory conformance",
            "application-context/1.0", "application-result/1.0", "artifact/1.0", "agent_",
        ),
        domains=(DomainBinding("inventory", domain.manifest.tool_name_prefix, domain, CredentialScope(), DataSharingPolicy()),),
        output_renderer=JsonOutputRenderer(),
        application_policy=SimpleNamespace(load=lambda: "Use registered inventory capabilities."),
        report_shell=report_shell or GenericReportShell(),
        acceptance_profile=SimpleNamespace(cases=lambda: ()),
    )
    created = []

    def provider_factory(*, request, profile, prepared_application, bindings, catalog):
        transport = ScriptedInventory(request, prepared_application, catalog, turns, overrides or {}, after_invoke)
        created.append(transport)
        return transport

    application = AgentApplication(
        profile=profile, workspace=workspace, registry=registry,
        credentials=EmptyCredentials(), provider_factory=provider_factory,
    )
    request = ApplicationRequest(
        profile.manifest.application_id,
        tuple(questions or [f"Process inventory request {index}" for index in range(len(turns))]),
        workspace.run_id,
    )
    outcome = application.run(request)
    return outcome, workspace, created


TWO_TURNS = [
    [("catalog.open", {"catalog_id": "warehouse-a"}), ("asset.list", {"context_ref": "$context"})],
    [("stock.summary", {"context_ref": "$context"})],
]


def test_real_two_turn_application_context_output_report_and_replay(tmp_path):
    outcome, workspace, transports = run_application(tmp_path, TWO_TURNS)
    assert outcome.status == "completed", outcome.error
    assert outcome.completed_questions == 2
    transport, = transports
    assert transport.started and transport.stopped
    assert [item[0] for item in transport.calls] == ["catalog.open", "asset.list", "stock.summary"]
    assert transport.calls[1][1]["context_ref"] == transport.calls[2][1]["context_ref"]
    payload = json.loads(outcome.rendered)
    assert len(payload["core"]["answer_refs"]) == 2
    inventory = payload["domains"]["inventory"]["payload"]
    assert inventory["asset_result_refs"] == [transport.calls[1][2]["result_ref"]]
    assert inventory["stock_summary_refs"] == [transport.calls[2][2]["result_ref"]]
    assert inventory["report_artifact_ref"] == payload["core"]["report_ref"]
    assert outcome.report_path is not None
    report = outcome.report_path.read_text()
    assert "Domain summary" in report and "warehouse-a" in report
    assert str(transport.calls[2][2]["total_quantity_on_hand"]) in report
    snapshot = json.loads(workspace.context_snapshot_path.read_text())
    assert ApplicationContextStore.replay(workspace).model_dump(mode="json") == snapshot


def admissions(workspace):
    return [
        json.loads(path.read_text())
        for path in sorted(workspace.turns_path.glob("*/answer-admission.json"))
    ]


def test_missing_asset_has_typed_failure_and_persisted_limited_admission(tmp_path):
    turns = [
        TWO_TURNS[0],
        [("asset.get", {"context_ref": "$context", "asset_id": "not-an-asset"})],
    ]
    outcome, workspace, transports = run_application(tmp_path, turns)
    assert outcome.status == "completed"
    # The runner counts durable finalized turns, including a limited turn.
    assert outcome.completed_questions == 2
    assert transports[0].calls[-1][2]["code"] == "capability_transport_failed"
    assert [item["mode"] for item in admissions(workspace)] == ["authority_backed", "limited"]
    answers = [json.loads(path.read_text()) for path in sorted(workspace.turns_path.glob("*/answer.json"))]
    assert answers[-1]["result_refs"] == [] and answers[-1]["evidence_refs"] == []


@pytest.mark.parametrize("question,mode", [
    ("guide:capability-map", "offline_information"),
    ("How many assets are in warehouse-a?", "limited"),
    ("Explain current-run evidence and give stock totals.", "limited"),
])
def test_full_application_zero_reference_admission(tmp_path, question, mode):
    outcome, workspace, transports = run_application(tmp_path, [[]], questions=[question])
    assert transports[0].calls == []
    assert admissions(workspace)[0]["mode"] == mode
    assert outcome.status == "completed"
    assert not list(workspace.domain_path("inventory").rglob("facts/*.json"))
    if mode == "offline_information":
        from inventory_domain.guide import InventoryGuideProvider
        answer_path, = workspace.turns_path.glob("*/answer.json")
        answer = json.loads(answer_path.read_text())
        assert answer["answer_output"] == InventoryGuideProvider().open("capability-map")["text"]
        assert answer["result_refs"] == [] and answer["evidence_refs"] == []


@pytest.mark.parametrize("stage", ["prepare", "render"])
def test_report_failures_preserve_primary_answers_with_correct_publication_semantics(tmp_path, stage):
    class FailingShell(GenericReportShell):
        def prepare(self, *, questions, workspace):
            if stage == "prepare":
                raise RuntimeError("intentional prepare failure")

        def render(self, **kwargs):
            if stage == "render":
                raise RuntimeError("intentional publication failure")
            return super().render(**kwargs)

    outcome, workspace, _ = run_application(tmp_path, TWO_TURNS, report_shell=FailingShell())
    assert outcome.status == "completed", outcome.error
    assert outcome.completed_questions == 2
    assert [item["mode"] for item in admissions(workspace)] == ["authority_backed"] * 2
    assert outcome.result.core.diagnostic_refs
    payload = json.loads(outcome.rendered)
    if stage == "render":
        assert outcome.report_path is None
        assert payload["core"]["report_ref"] is None
        assert payload["domains"]["inventory"]["payload"]["report_artifact_ref"] is None
    else:
        assert outcome.report_path is not None and outcome.report_path.is_file()
        assert payload["core"]["report_ref"] is not None


def test_foreign_run_result_cannot_acquire_current_run_lineage(tmp_path):
    source, _, source_transports = run_application(tmp_path / "source", TWO_TURNS)
    assert source.status == "completed"
    foreign_summary = source_transports[0].calls[-1][2]
    outcome, workspace, _ = run_application(
        tmp_path / "target", TWO_TURNS, overrides={"stock.summary": foreign_summary},
    )
    assert outcome.status == "failed"
    assert outcome.completed_questions == 1
    assert len(admissions(workspace)) == 1


def test_tampered_current_run_result_fails_authority_verification(tmp_path):
    def tamper(capability, result, binding):
        if capability != "stock.summary":
            return
        admitted = binding.runtime.authority.admit(capability, result, tuple(result["evidence_refs"]))
        artifact = admitted.results[0]
        artifact.path.write_text("{}", encoding="utf-8")

    outcome, workspace, _ = run_application(tmp_path, TWO_TURNS, after_invoke=tamper)
    assert outcome.status == "failed"
    assert outcome.completed_questions == 1
    assert len(admissions(workspace)) == 1


def test_wrong_authority_is_rejected_before_provider_start(tmp_path):
    from inventory_domain.authority import InventoryArtifactAuthority

    domain = build_inventory_profile()
    class WrongAuthority(InventoryArtifactAuthority):
        authority_id = "not-inventoryctl"

    domain = replace(domain, authority_factory=WrongAuthority)
    outcome, workspace, transports = run_application(tmp_path, TWO_TURNS, domain=domain)
    assert outcome.status == "failed"
    assert transports == []
    assert admissions(workspace) == []
