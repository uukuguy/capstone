"""Finite model decisions through the real Harness and PowerMCP Authority."""
from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path

import pytest

from capstone_agent.professional_resources import resolve_harness_resource_profile, bind_harness_skill
from capstone_agent.thread_commands import ThreadCommandFactory
from capstone_agent.thread_protocol import ModelContextSnapshot, ThreadSnapshot
from capstone_agent.thread_service import InMemoryThreadService
from capstone_agent.thread_worker import run_pending_attempt
from grid_agent import hosted
from test_thread_model_sequence import ModelSequenceSession


ROOT = Path(__file__).resolve().parents[4]


@pytest.mark.skipif(os.environ.get("CAPSTONE_POWERMCP_TESTS") != "1", reason="explicit real isolated MCP check")
def test_selected_skill_direct_harness_calls_real_mcp_and_admits_current_revision(monkeypatch, tmp_path):
    sessions = []
    class StructuralSession(ModelSequenceSession):
        def __init__(self, claim, context, profiles):
            super().__init__(claim, context, profiles)
            bindings = profiles[0].prepared_application.bindings
            profile = resolve_harness_resource_profile(ROOT / "configs/runtime", bindings)
            selected = next(item for item in profile.to_document()["resources"] if item["id"] == "powerskills-pandapower")
            assert selected["ready"], selected["reason"]
            self.selection = bind_harness_skill(profile, skill_id=selected["id"], skill_version=selected["version"], profile_revision=profile.revision)

        def prompt_and_wait(self, question, *, on_semantic_event, correlation_id, on_heartbeat):
            assert "diagnostic.structural" in self.guide["text"]
            assert "N-2 is" in self.guide["text"]
            on_semantic_event({"type": "tool_execution_end", "toolCallId": "selected-guide", "toolName": "agent_guide_open",
                "isError": False, "args": {"binding_id": "grid", "resource_id": self.guide["resource_id"]},
                "result": {"resource_id": self.guide["resource_id"], "sha256": self.guide["sha256"], "text": self.guide["text"]}})
            result = self._invoke("analysis.run", {"context_ref": self.binding.context_ref, "operation": "diagnostic.structural", "options": {}}, on_semantic_event)
            self.audit_result = result
            self._invoke("result.dataset.describe", {"result_ref": result["result_ref"], "dataset": "result.res_structural_audit"}, on_semantic_event)
            self._invoke("result.dataset.query", {"result_ref": result["result_ref"], "dataset": "result.res_structural_audit",
                "select": ["severity", "code", "message", "element_kind", "element_index", "subject_asset_ref"], "limit": 10}, on_semantic_event)
            for evidence in result["evidence_refs"]:
                self._invoke("evidence.get", {"evidence_ref": evidence}, on_semantic_event)
            return f"Structural audit completed with verdict {result['summary']['audit_status']}. The coverage excludes power-flow convergence and operating security."

    def build(claim, context, profiles):
        # Only the model/RPC transport is controlled. The standard hosted
        # session builder performs selected guide loading and admission.
        import capstone_agent.kernel_pi_session as session_module
        from capability_agent.runtime.environment import RuntimeHost
        from capability_agent.runtime.lock import PiCommand, PiRuntimeIdentity
        from capability_agent.runtime.models import ResolvedLLM, ResolvedLLMConfig
        session = StructuralSession(claim, context, profiles)
        sessions.append(session)
        class ControlledModelClient:
            command = None
            def __init__(self, launch, *args, **kwargs):
                policy = Path(launch.argv[launch.argv.index("--system-prompt") + 1])
                session.receipt = json.loads((policy.parent / "harness-skill-load.json").read_text())
                text = policy.read_text()
                assert "Selected professional skill: powerskills-pandapower" in text
                assert "--no-builtin-tools" in launch.argv and "--no-skills" in launch.argv
                session.guide = {"resource_id": session.receipt["guide_resource_id"], "sha256": session.receipt["guide_sha256"], "text": text}
            def start(self):
                session.start()
            def stop(self):
                session.stop()
            def prompt_and_wait(self, question, *, on_semantic_event, **kwargs):
                return session.prompt_and_wait(question, on_semantic_event=lambda e: on_semantic_event(e, 0), **kwargs)
        monkeypatch.setattr(session_module, "PiRpcClient", ControlledModelClient)
        policy = profiles[0].profile.domains[0].profile.manifest.system_policy_path
        host = RuntimeHost(command=PiCommand(("controlled-model",), PiRuntimeIdentity(path=tmp_path / "model", source="fixture", package_version="1", lock_sha256="fixed")),
            project_pi_dir=tmp_path / "pi", extension_path=ROOT / "packages/pi-capability-tools",
            system_policy_path=policy)
        resolved = ResolvedLLM(ResolvedLLMConfig(provider="fixture", model="fixture-model", base_url="http://127.0.0.1/v1",
            auth_kind="none", credential_reference="FIXTURE_KEY", timeout_seconds=60, max_retries=0,
            pi_provider="fixture", compatibility_profile="generic", descriptor_version="fixture", public_headers={}, field_sources={}, supports_tools=True), None)
        selected_claim = replace(claim, turn_plan=replace(claim.turn_plan,
            intent_resources={**(claim.turn_plan.intent_resources or {}), "harness_skill_selection": session.selection}))
        return session_module.PreparedKernelPiRpcSessionBuilder(runtime_host=host, resolved_llm=resolved,
            base_environment={"PATH": os.environ.get("PATH", "")})(selected_claim, context, profiles)

    monkeypatch.setenv("CAPSTONE_RUNS_ROOT", str(tmp_path / "runs"))
    monkeypatch.setenv("CAPSTONE_POWERMCP_MANAGED_ROOT", str(ROOT / ".grid-agent/runtime/agent-resources"))
    monkeypatch.setattr(hosted, "select_validation_builder", lambda *_args: build)
    assembly = hosted.build_registered_pandapower_thread_application()
    initial = assembly.catalog.resolve("ieee39")
    selection = assembly.capability_catalog.resolve(initial)
    context = ModelContextSnapshot("ctx_audit", initial.model_id, initial.model_revision,
        initial.implementation_family, "sel_0", selection.enabled_profiles)
    service = InMemoryThreadService.from_document({"schema": "capstone-thread-snapshot/1", "thread_id": "thr_audit",
        "run": {"run_id": "run_audit", "state": "open"}, "active_model_context": context.to_document(),
        "active_grid_page_id": "page_ieee39", "current_attempt": None, "last_event_seq": 0, "base_event_seq": 0},
        model_catalog=assembly.catalog, capability_catalog=assembly.capability_catalog)
    commands = ThreadCommandFactory("thr_audit", "run_audit")
    try:
        receipt = service.submit_command(commands.send_professional("Run the selected structural preflight skill.",
            expected_event_seq=0, command_id="cmd_audit", idempotency_key="idem_audit"))
        assert receipt.status == "accepted"
        outcome = run_pending_attempt(service, assembly.runtime_factory, worker_id="audit-worker", lease_seconds=120,
            turn_router=assembly.turn_router_for_worker(), implementation_family="pandapower")
        assert outcome is not None and outcome.status == "completed", outcome
        session = sessions[0]
        result = session.audit_result
        assert outcome.result_refs == (result["result_ref"],)
        assert set(outcome.evidence_refs) == set(result["evidence_refs"])
        assert result["revision_ref"] == context.model_revision
        assert session.receipt["backend_descriptor_sha256"] == result["summary"]["provenance"]["descriptor_sha256"]
        assert [call["tool"] for call in result["summary"]["provenance"]["calls"]] == ["load_network", "audit_network"]
        authority = session.runtime.authority
        persisted = authority.verify_result(outcome.result_refs[0]).document
        assert persisted["revision_ref"] == context.model_revision
        assert persisted["metadata"]["coverage"]["topology"] == "checked"
        for evidence in outcome.evidence_refs:
            assert authority.verify_evidence(evidence).document["result_ref"] == outcome.result_refs[0]
        snapshot = service.snapshot("thr_audit")
        assert ThreadSnapshot.from_document(json.loads(json.dumps(snapshot.to_document()))) == snapshot
        terminal = service.read_events("thr_audit", 0).events[-1]
        assert terminal.payload["admission"]["mode"] == "authority_backed"
        assert terminal.payload["evidence_refs"] == list(outcome.evidence_refs)
        # Independently re-read the exact saved result/evidence in replay.
        from pandapower_domain.authority import PandapowerArtifactAuthority
        replay = PandapowerArtifactAuthority(session.runtime.authority.workspace_root)
        assert replay.verify_result(outcome.result_refs[0]).document == persisted
        assert replay.verify_evidence(outcome.evidence_refs[0]).document["revision_ref"] == context.model_revision
    finally:
        assembly.capability_context_owner.close()
