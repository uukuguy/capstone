"""Repository acceptance: real authorities, scripted provider, owned claims."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from capability_agent.application import (
    AgentApplication, ApplicationContextStore, ApplicationManifest,
    ApplicationProfile, ApplicationRequest, ApplicationWorkspace,
    CredentialScope, DataSharingPolicy, DomainBinding, DomainRegistry,
    GenericReportShell, JsonOutputRenderer, TurnController,
)
from inventory_domain.profile import build_inventory_profile


ROOT = Path(__file__).resolve().parents[3]


def test_real_two_binding_two_turn_application(tmp_path, monkeypatch):
    # The inventory distribution stays independent of the grid distribution.
    # This repository acceptance assembles their public profiles explicitly.
    for package in ("pandapower-domain-pack", "grid-simulator"):
        monkeypatch.syspath_prepend(str(ROOT / "packages" / package / "src"))
    from pandapower_domain import build_pandapower_profile
    import capability_agent.application.runner as runner_module

    profiles = {"grid": build_pandapower_profile(), "inventory": build_inventory_profile()}
    registry = DomainRegistry()
    for domain in profiles.values():
        registry.register(domain.manifest.domain_id, domain.manifest.version, lambda domain=domain: domain)
    profile = ApplicationProfile(
        manifest=ApplicationManifest("two-authorities", "1.0", "Two authorities", "application-context/1.0", "application-result/1.0", "artifact/1.0", "agent_"),
        domains=tuple(DomainBinding(key, domain.manifest.tool_name_prefix, domain, CredentialScope(), DataSharingPolicy()) for key, domain in profiles.items()),
        output_renderer=JsonOutputRenderer(),
        application_policy=SimpleNamespace(load=lambda: "Use each registered authority independently."),
        report_shell=GenericReportShell(), acceptance_profile=SimpleNamespace(cases=lambda: ()),
    )
    workspace = ApplicationWorkspace.create(tmp_path.resolve() / "runs", binding_ids=profiles)
    providers = []

    class ClaimController(TurnController):
        # AgentApplication accepts provider text; explicit claims use the public
        # controller API. Keep all validation and persistence in real submit.
        def submit(self, handle, **kwargs):
            return super().submit(handle, claims=providers[0].claims, **kwargs)

        def start(self, ordinal, instruction):
            handle = super().start(ordinal, instruction)
            if ordinal == 2:
                # Expose only the two admitted context references to the script.
                # Neither binding receives the other binding's state or refs.
                domains = self.store.snapshot.domains
                bounded = {
                    "grid": domains["grid"].state["model"]["context_ref"],
                    "inventory": domains["inventory"].state["active_context_ref"],
                }
                assert bounded == providers[0].contexts
                providers[0].contexts = bounded
                providers[0].reused_context = True
            return handle

    monkeypatch.setattr(runner_module, "TurnController", ClaimController)

    def provider_factory(*, request, profile, prepared_application, bindings, catalog):
        provider = TwoAuthorityProvider(request, prepared_application, catalog)
        providers.append(provider)
        return provider

    application = AgentApplication(
        profile=profile, registry=registry, workspace=workspace,
        credentials=SimpleNamespace(issue=lambda *, binding_id, scope: SimpleNamespace(scope_id=scope.scope_id, credentials={})),
        provider_factory=provider_factory,
    )
    outcome = application.run(ApplicationRequest(profile.manifest.application_id, ("Inspect both systems.", "Repeat using each system's existing context."), workspace.run_id))
    assert outcome.status == "completed", outcome.error
    assert outcome.completed_questions == 2
    provider, = providers
    assert provider.started and provider.stopped
    assert provider.reused_context
    assert [capability for _, capability, _ in provider.calls] == [
        "context.open", "catalog.open", "analysis.powerflow.ac.run",
        "stock.summary", "model.constraints.describe", "stock.summary",
    ]
    for binding_id, capability, arguments in provider.calls[2:]:
        assert arguments["context_ref"] == provider.contexts[binding_id]
    payload = json.loads(outcome.rendered)
    assert set(payload["domains"]) == {"grid", "inventory"}
    assert payload["domains"]["grid"]["payload"]["completed_count"] == 2
    inventory = payload["domains"]["inventory"]["payload"]
    assert set(inventory["stock_summary_refs"]) == {provider.results[turn]["inventory"]["result_ref"] for turn in range(2)}
    answers = [json.loads(path.read_text()) for path in sorted(workspace.turns_path.glob("*/answer.json"))]
    assert len(answers) == 2
    for turn, answer in enumerate(answers):
        assert len(answer["claims"]) == 2
        for binding_id, claim in zip(profiles, answer["claims"], strict=True):
            result = provider.results[turn][binding_id]
            assert claim["result_refs"] == ([result["result_ref"]] if "result_ref" in result else [])
            assert claim["evidence_refs"] == result["evidence_refs"]
            authority = provider.bindings[binding_id].runtime.authority
            if "result_ref" in result:
                assert authority.verify_result(result["result_ref"]).path.is_relative_to(workspace.domain_path(binding_id))
            capability = ("stock.summary" if binding_id == "inventory" else
                          "analysis.powerflow.ac.run" if turn == 0 else "model.constraints.describe")
            admitted = authority.admit(capability, result, tuple(result["evidence_refs"]))
            assert {artifact.reference for artifact in admitted.evidence} == set(result["evidence_refs"])
            assert all(artifact.path.is_relative_to(workspace.domain_path(binding_id)) for artifact in admitted.evidence)
    admissions = [json.loads(path.read_text()) for path in sorted(workspace.turns_path.glob("*/answer-admission.json"))]
    assert all(set(item["bindings"]) == set(profiles) for item in admissions)
    assert all(decision["assurance"] == "lineage_verified" for item in admissions for decision in item["bindings"].values())
    assert outcome.report_path is not None and outcome.report_path.is_file()
    report = outcome.report_path.read_text()
    assert all(claim["statement"] in report for answer in answers for claim in answer["claims"])
    assert all(domain["payload"]["report_artifact_ref"] == payload["core"]["report_ref"] for domain in payload["domains"].values())
    assert ApplicationContextStore.replay(workspace).model_dump(mode="json") == json.loads(workspace.context_snapshot_path.read_text())


class TwoAuthorityProvider:
    def __init__(self, request, prepared, catalog):
        self.request = request
        self.bindings = prepared.bindings
        self.tools = {(tool.key.binding_id, tool.key.capability_id): tool for tool in catalog.domain_tools}
        self.contexts = {}
        self.results = []
        self.claims = []
        self.calls = []
        self.reused_context = False
        self.started = self.stopped = False
        self.sequence = 0

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True

    def prompt_and_wait(self, question, *, on_semantic_event, correlation_id, on_heartbeat):
        on_heartbeat()
        if not self.contexts:
            for binding_id, capability, arguments in (
                ("grid", "context.open", {"model_id": "ieee39"}),
                ("inventory", "catalog.open", {"catalog_id": "warehouse-a"}),
            ):
                result = self.invoke(binding_id, capability, arguments, on_semantic_event, correlation_id)
                self.contexts[binding_id] = result["context_ref"]
        self.claims = []
        results = {}
        for binding_id, capability, category in (
            ("grid", "analysis.powerflow.ac.run", "numerical_result"),
            ("inventory", "stock.summary", "stock"),
        ):
            arguments = {"context_ref": self.contexts[binding_id]}
            if binding_id == "grid" and self.results:
                capability, category = "model.constraints.describe", "constraint"
            result = self.invoke(binding_id, capability, arguments, on_semantic_event, correlation_id)
            results[binding_id] = result
            if binding_id == "grid":
                statement = (f"Model constraint groups: {len(result['constraints'])}." if self.results
                             else f"AC power flow converged: {result['converged']}.")
            else:
                statement = f"Inventory quantity on hand: {result['total_quantity_on_hand']}."
            self.claims.append(dict(statement=statement, category=category, result_refs=[result["result_ref"]] if "result_ref" in result else [], evidence_refs=result["evidence_refs"]))
        self.results.append(results)
        return " ".join(claim["statement"] for claim in self.claims)

    def invoke(self, binding_id, capability, arguments, callback, turn_id):
        tool = self.tools[binding_id, capability]
        binding = self.bindings[binding_id]
        document = next(doc for doc in binding.runtime.capability_documents if doc["id"] == capability)
        self.sequence += 1
        identity = dict(call_id=f"call-{self.sequence}", tool_name=tool.name, capability=capability, capability_key=dict(binding_id=binding_id, capability_id=capability), run_id=self.request.run_id, turn_id=turn_id)
        callback(dict(identity, type="tool_execution_start", arguments=arguments), self.sequence)
        result = binding.endpoint.executor.invoke(capability, arguments)
        self.calls.append((binding_id, capability, arguments))
        self.sequence += 1
        effect = document["context_effect"]
        callback(dict(identity, type="tool_result", ok=True, result=result, result_refs=[result["result_ref"]] if "result_ref" in result else [], evidence_refs=result.get("evidence_refs", []), projector_id=effect["projector"], result_kind=effect.get("result_kind")), self.sequence)
        return result
