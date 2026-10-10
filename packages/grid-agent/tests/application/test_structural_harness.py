"""Professional guide/backend coverage, including the real Pi semantic channel."""
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
def test_selected_guide_backend_and_downstream_admission_with_scripted_dispatch(monkeypatch, tmp_path):
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
        # This narrower fixture controls RPC, semantic dispatch and initial
        # admission. It covers guide loading, backend and downstream admission.
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


@pytest.mark.skipif(os.environ.get("CAPSTONE_POWERMCP_TESTS") != "1", reason="explicit real isolated Pi/MCP check")
def test_selected_skill_real_pi_semantic_channel_to_mcp_admission_and_replay(monkeypatch, tmp_path):
    """Control only HTTP model responses; Pi and all tool execution stay real."""
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from threading import Thread
    from capability_agent.runtime.environment import RuntimeHost
    from capability_agent.runtime.extension import ExtensionSpec, PiExtensionLocator
    from capability_agent.runtime.locator import PiRuntimeLocator
    from capability_agent.runtime.lock import PiRuntimeLock
    from capability_agent.runtime.models import ResolvedLLM, ResolvedLLMConfig, SecretValue
    from capstone_agent.kernel_pi_session import PreparedKernelPiRpcSessionBuilder

    state = {"requests": [], "results": {}, "errors": []}
    class Provider(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):
            try:
                request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                assert self.path == "/v1/chat/completions"
                assert self.headers["Authorization"] == "Bearer synthetic-loopback-key"
                state["requests"].append(request)
                step = len(state["requests"])
                published = {item["function"]["name"] for item in request["tools"]}
                functions = {item["function"]["name"]: item["function"] for item in request["tools"]}
                capabilities = ("context.open", "analysis.operation.describe", "analysis.run",
                    "result.dataset.describe", "result.dataset.query", "evidence.get")
                tools = {capability: next(name for name in published if name.endswith(capability.replace(".", "_")))
                    for capability in capabilities}
                guide_tool = next(name for name in published if name.endswith("_guide_open"))
                assert not {"bash", "read", "write", "edit"} & published
                policy = request["messages"][0]["content"]
                assert "Selected professional skill: powerskills-pandapower" in policy
                assert "05bda3a51d5f1ecad888d4d4663c28478c643a7e" in policy
                tool_messages = [item for item in request["messages"] if item["role"] == "tool"]
                if step == 2:
                    assert "diagnostic.structural" in tool_messages[-1]["content"]
                elif step > 2:
                    response = json.loads(tool_messages[-1]["content"])
                    if response["ok"] is not True:
                        raise ValueError(json.dumps(response["error"]))
                    state["results"][step - 1] = response["result"]
                    if step == 4:
                        assert response["result"]["availability"]["status"] == "available"

                opened = state["results"].get(2)
                audit = state["results"].get(4)
                choices = {
                    1: (guide_tool, {"resource_id": "powerskills-pandapower-adapter"}),
                    2: (tools["context.open"], {"model_id": functions[tools["context.open"]]["parameters"]["properties"]["model_id"]["enum"][0]}),
                    3: (tools["analysis.operation.describe"], {"operation": "diagnostic.structural"}),
                }
                if opened:
                    choices[4] = (tools["analysis.run"], {"context_ref": opened["context_ref"], "operation": "diagnostic.structural", "options": {}})
                if audit:
                    choices.update({
                        5: (tools["result.dataset.describe"], {"result_ref": audit["result_ref"], "dataset": "result.res_structural_audit"}),
                        6: (tools["result.dataset.query"], {"result_ref": audit["result_ref"], "dataset": "result.res_structural_audit",
                            "select": ["severity", "code", "message", "element_kind", "element_index", "subject_asset_ref"], "limit": 10}),
                        7: (tools["evidence.get"], {"evidence_ref": audit["evidence_refs"][0]}),
                    })
                if step <= 7:
                    name, arguments = choices[step]
                    assert name in published
                    delta = {"role": "assistant", "tool_calls": [{"index": 0, "id": f"call_structural_{step}",
                        "type": "function", "function": {"name": name, "arguments": json.dumps(arguments)}}]}
                    finish = "tool_calls"
                else:
                    assert step == 8
                    delta = {"role": "assistant", "content": f"Structural audit completed with verdict {audit['summary']['audit_status']}. Coverage excludes power-flow convergence and operating security."}
                    finish = "stop"
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                for content, reason in [(delta, None), ({}, finish)]:
                    chunk = {"id": f"structural_response_{step}", "object": "chat.completion.chunk", "created": 0,
                        "model": "fixture-model", "choices": [{"index": 0, "delta": content, "finish_reason": reason}]}
                    self.wfile.write(("data: " + json.dumps(chunk) + "\n\n").encode())
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()
            except Exception as exc:
                state["errors"].append(str(exc))
                self.send_error(500)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Provider)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    command = PiRuntimeLocator(ROOT / ".grid-agent/runtime/pi", {"PATH": os.environ["PATH"]},
        runtime_lock=PiRuntimeLock.load(ROOT / "configs/runtime/pi-runtime.lock.json")).resolve(require_managed=True)
    extension = PiExtensionLocator(ROOT, spec=ExtensionSpec(package_name="@capability-agent/pi-tools",
        package_version="0.1.0", candidates=(Path("packages/pi-capability-tools"),))).resolve()
    private_config = tmp_path / "pi-config"
    private_config.mkdir(mode=0o700)
    origin = f"http://127.0.0.1:{server.server_port}/v1"
    (private_config / "models.json").write_text(json.dumps({"providers": {"fixture": {
        "baseUrl": origin, "api": "openai-completions", "apiKey": "$FIXTURE_API_KEY",
        "models": [{"id": "fixture-model", "reasoning": False}]}}}))
    resolved = ResolvedLLM(ResolvedLLMConfig(provider="fixture", model="fixture-model", base_url=origin,
        auth_kind="api-key", credential_reference="FIXTURE_API_KEY", timeout_seconds=120, max_retries=0,
        pi_provider="fixture", compatibility_profile="generic", descriptor_version="loopback-test",
        public_headers={}, field_sources={}, supports_tools=True), SecretValue("synthetic-loopback-key"))

    def build(claim, context, profiles):
        bindings = profiles[0].prepared_application.bindings
        profile = resolve_harness_resource_profile(ROOT / "configs/runtime", bindings)
        resource = next(item for item in profile.to_document()["resources"] if item["id"] == "powerskills-pandapower")
        assert resource["ready"], resource["reason"]
        selection = bind_harness_skill(profile, skill_id=resource["id"], skill_version=resource["version"], profile_revision=profile.revision)
        runtime = bindings["grid"].runtime
        state["runtime"] = runtime
        state["selection"] = selection
        host = RuntimeHost(command=command, project_pi_dir=private_config, extension_path=extension,
            system_policy_path=profiles[0].profile.domains[0].profile.manifest.system_policy_path)
        selected_claim = replace(claim, turn_plan=replace(claim.turn_plan,
            intent_resources={**(claim.turn_plan.intent_resources or {}), "harness_skill_selection": selection}))
        session = PreparedKernelPiRpcSessionBuilder(runtime_host=host, resolved_llm=resolved,
            base_environment={"PATH": os.environ["PATH"], "HOME": str(tmp_path / "private-home")})(selected_claim, context, profiles)
        return session

    monkeypatch.setenv("CAPSTONE_RUNS_ROOT", str(tmp_path / "runs"))
    monkeypatch.setenv("CAPSTONE_POWERMCP_MANAGED_ROOT", str(ROOT / ".grid-agent/runtime/agent-resources"))
    monkeypatch.setattr(hosted, "select_validation_builder", lambda *_args: build)
    assembly = hosted.build_registered_pandapower_thread_application()
    initial = assembly.catalog.resolve("ieee39")
    capability_selection = assembly.capability_catalog.resolve(initial)
    context = ModelContextSnapshot("ctx_real_audit", initial.model_id, initial.model_revision,
        initial.implementation_family, "sel_0", capability_selection.enabled_profiles)
    service = InMemoryThreadService.from_document({"schema": "capstone-thread-snapshot/1", "thread_id": "thr_real_audit",
        "run": {"run_id": "run_real_audit", "state": "open"}, "active_model_context": context.to_document(),
        "active_grid_page_id": "page_ieee39", "current_attempt": None, "last_event_seq": 0, "base_event_seq": 0},
        model_catalog=assembly.catalog, capability_catalog=assembly.capability_catalog)
    commands = ThreadCommandFactory("thr_real_audit", "run_real_audit")
    try:
        receipt = service.submit_command(commands.send_professional("Run the selected structural preflight skill.",
            expected_event_seq=0, command_id="cmd_real_audit", idempotency_key="idem_real_audit"))
        assert receipt.status == "accepted"
        outcome = run_pending_attempt(service, assembly.runtime_factory, worker_id="real-audit-worker", lease_seconds=180,
            turn_router=assembly.turn_router_for_worker(), implementation_family="pandapower")
        if state["errors"]:
            pytest.fail("\n".join(state["errors"]))
        assert outcome is not None and outcome.status == "completed", outcome
        assert len(state["requests"]) == 8
        audit = state["results"][4]
        assert outcome.result_refs == (audit["result_ref"],)
        assert set(outcome.evidence_refs) == set(audit["evidence_refs"])
        assert audit["revision_ref"] == context.model_revision
        assert audit["context_ref"] == state["results"][2]["context_ref"]
        assert [call["tool"] for call in audit["summary"]["provenance"]["calls"]] == ["load_network", "audit_network"]
        load_receipts = list((tmp_path / "runs").rglob("harness-skill-load.json"))
        assert len(load_receipts) == 1
        loaded = json.loads(load_receipts[0].read_text())
        assert loaded["guide_sha256"] == state["selection"].guide_sha256
        assert loaded["backend_descriptor_sha256"] == audit["summary"]["provenance"]["descriptor_sha256"]
        # These are Pi's own persisted native messages, produced by the real
        # extension. The fixture supplies no tool event or admission callback.
        native_sessions = list((tmp_path / "runs").rglob("session/*.jsonl"))
        assert len(native_sessions) == 1
        messages = [json.loads(line).get("message", {}) for line in native_sessions[0].read_text().splitlines()]
        completed_tools = [message for message in messages if message.get("role") == "toolResult"]
        assert len(completed_tools) == 7
        assert [message["toolCallId"] for message in completed_tools] == [f"call_structural_{step}" for step in range(1, 8)]
        assert all(message["details"]["ok"] is True for message in completed_tools)
        assert completed_tools[3]["toolName"] == "grid_analysis_run"
        assert completed_tools[3]["details"]["capability_key"] == {"binding_id": "grid", "capability_id": "analysis.run"}
        assert completed_tools[3]["details"]["result"]["result_ref"] == audit["result_ref"]
        terminal = service.read_events("thr_real_audit", 0).events[-1]
        assert terminal.payload["admission"]["mode"] == "authority_backed"
        assert terminal.payload["evidence_refs"] == list(outcome.evidence_refs)
        snapshot = service.snapshot("thr_real_audit")
        assert ThreadSnapshot.from_document(json.loads(json.dumps(snapshot.to_document()))) == snapshot
        from pandapower_domain.authority import PandapowerArtifactAuthority
        replay = PandapowerArtifactAuthority(state["runtime"].authority.workspace_root)
        persisted = replay.verify_result(outcome.result_refs[0]).document
        assert persisted["revision_ref"] == context.model_revision
        assert persisted["metadata"]["coverage"]["topology"] == "checked"
        assert replay.verify_evidence(outcome.evidence_refs[0]).document["result_ref"] == outcome.result_refs[0]
        assert "synthetic-loopback-key" not in json.dumps(persisted)
    finally:
        assembly.capability_context_owner.close()
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
