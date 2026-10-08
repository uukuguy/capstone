from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest


def request_document():
    return {
        "schema": "capstone-intent-request/1", "thread_id": "thread_1",
        "turn_id": "turn_1", "attempt_id": "attempt_1", "instruction": "Translate that answer.",
        "history_cutoff": 7, "messages": [{"message_id": "message_1", "role": "assistant",
            "content": "The result is available.", "turn_id": "turn_0", "attempt_id": "attempt_0",
            "model_context_id": "context_0", "status": "completed"}],
        "objects": [], "capabilities": [], "mode_hint": "auto",
    }


def decision_document():
    return {"schema": "capstone-intent-decision/1", "attempt_id": "attempt_1",
        "history_cutoff": 7, "relationship": "continuation", "goals": [{
            "goal_id": "goal_1", "description": "Translate the previous answer.",
            "operation": "rewrite", "message_refs": ["message_1"], "object_refs": [],
            "capability_refs": [], "missing_requirements": [], "depends_on": []}], "clarification": None}


class Control:
    deadline = None

    def __init__(self):
        self.calls = 0

    def checkpoint(self):
        self.calls += 1


class Session:
    def __init__(self, events, error=None):
        self.events = events
        self.error = error
        self.stopped = False

    def start(self):
        pass

    def prompt_and_wait(self, question, *, on_semantic_event, correlation_id, on_heartbeat):
        self.question = question
        assert correlation_id == "attempt_1"
        on_heartbeat()
        for event in self.events:
            on_semantic_event(event)
        if self.error:
            raise self.error
        return "Ignored reader text."

    def stop(self):
        self.stopped = True


def test_recognizer_uses_validated_terminating_tool_and_closes():
    from capstone_agent.pi_intent import PiIntentRecognizer
    from capstone_agent.request_intent import IntentRequest, IntentEngineIdentity
    event = {"type": "tool_result", "capability": "capstone.intent.decision", "ok": True,
             "result": decision_document()}
    session = Session([event])
    control = Control()
    recognizer = PiIntentRecognizer(lambda request, control: session,
        IntentEngineIdentity(engine="pi", model="fixture", config_revision="fixture"))
    request = IntentRequest.from_document(request_document())
    decision = recognizer.recognize(request, control)
    assert decision.to_document() == decision_document()
    assert json.loads(session.question) == request_document()
    assert session.stopped and control.calls >= 4


@pytest.mark.parametrize("events", [[], [{"type": "tool_result", "capability": "capstone.intent.decision",
    "ok": True, "result": decision_document()}] * 2])
def test_recognizer_fails_without_exactly_one_decision(events):
    from capstone_agent.pi_intent import PiIntentRecognizer
    from capstone_agent.request_intent import IntentRequest, IntentEngineIdentity
    session = Session(events)
    recognizer = PiIntentRecognizer(lambda request, control: session,
        IntentEngineIdentity(engine="pi", model="fixture", config_revision="fixture"))
    with pytest.raises(ValueError, match="one intent decision"):
        recognizer.recognize(IntentRequest.from_document(request_document()), Control())
    assert session.stopped


def test_recognizer_failure_and_cancel_close_session():
    from capstone_agent.pi_intent import PiIntentRecognizer
    from capstone_agent.request_intent import IntentRequest, IntentEngineIdentity
    session = Session([], RuntimeError("cancelled"))
    recognizer = PiIntentRecognizer(lambda request, control: session,
        IntentEngineIdentity(engine="pi", model="fixture", config_revision="fixture"))
    with pytest.raises(RuntimeError, match="cancelled"):
        recognizer.recognize(IntentRequest.from_document(request_document()), Control())
    assert session.stopped


def test_context_launch_records_projection_and_adds_only_trusted_extension(tmp_path):
    from capability_agent.application.workspace import ApplicationWorkspace
    from capability_agent.runtime.environment import PiLaunch
    from capstone_agent.pi_intent import prepare_context_launch
    workspace = ApplicationWorkspace.create(tmp_path)
    original = PiLaunch(("node", "pi.js", "--no-builtin-tools"), {"SAFE": "value"})
    messages = request_document()["messages"]
    launch = prepare_context_launch(original, workspace, "attempt_1", messages, {"mode": "execution"})
    assert launch.argv[:3] == original.argv
    assert Path(launch.argv[-1]).name == "conversation-context.mjs"
    projection = json.loads(Path(launch.environment["CAPSTONE_PI_CONTEXT_PATH"]).read_text())
    assert projection["messages"] == messages
    assert projection["supplemental_context"] == {"mode": "execution"}
    assert original.environment == {"SAFE": "value"}


def test_context_launch_rejects_unsafe_attempt_path(tmp_path):
    from capability_agent.application.workspace import ApplicationWorkspace
    from capability_agent.runtime.environment import PiLaunch
    from capstone_agent.pi_intent import prepare_context_launch
    with pytest.raises(ValueError):
        prepare_context_launch(PiLaunch(("pi",), {}), ApplicationWorkspace.create(tmp_path),
            "../../escape", [], {})


def runtime_inputs(tmp_path, base_url="http://127.0.0.1:1234/v1", command=None):
    from capability_agent.runtime.environment import RuntimeHost
    from capability_agent.runtime.lock import PiCommand, PiRuntimeIdentity
    from capability_agent.runtime.models import ResolvedLLM, ResolvedLLMConfig, SecretValue
    host = RuntimeHost(command=command or PiCommand(("node", "pi.js"), PiRuntimeIdentity(
        path=tmp_path / "pi.js", source="fixture", package_version="fixture", lock_sha256="fixture")),
        project_pi_dir=tmp_path / "protected", extension_path=tmp_path / "domain-extension.mjs",
        system_policy_path=tmp_path / "domain.md")
    llm = ResolvedLLM(ResolvedLLMConfig(provider="fixture", model="fixture-model",
        base_url=base_url, auth_kind="api-key", credential_reference="FIXTURE_API_KEY",
        timeout_seconds=10, max_retries=0, pi_provider="fixture", compatibility_profile="generic",
        descriptor_version="fixture", public_headers={}, field_sources={}, supports_tools=True),
        SecretValue("synthetic-loopback-key"))
    return host, llm


def test_builder_loads_native_config_and_ordinary_stage_has_no_business_policy(tmp_path, monkeypatch):
    import capstone_agent.pi_intent as module
    from capstone_agent.request_intent import IntentRequest, IntentDecision
    captured = []
    class Client:
        def __init__(self, launch, workspace, trace, **kwargs):
            captured.append((launch, workspace))
        def stop(self):
            pass
    monkeypatch.setattr(module, "PiRpcClient", Client)
    host, llm = runtime_inputs(tmp_path)
    host.system_policy_path.write_text("GRID DOMAIN ROLE MUST NOT LEAK")
    builder = module.NativeConversationPiSessionBuilder(runtime_host=host, resolved_llm=llm,
        workspace_root=tmp_path / "workspaces", base_environment={"PATH": "/usr/bin"})
    request = IntentRequest.from_document(request_document())
    decision = IntentDecision.from_document(decision_document(), request)
    session = builder.build_execution(SimpleNamespace(intent_request=request, application_catalog=None), decision)
    launch, workspace = captured[0]
    assert str(host.extension_path) not in launch.argv
    assert "intent-decision.mjs" not in " ".join(launch.argv)
    assert "--no-builtin-tools" in launch.argv and "--no-context-files" in launch.argv
    assert launch.environment["PI_CODING_AGENT_DIR"] == str(host.project_pi_dir)
    system = Path(launch.argv[launch.argv.index("--system-prompt") + 1]).read_text()
    assert "You are Capstone" in system and "GRID DOMAIN ROLE" not in system
    assert "The result is available" not in system
    assert json.loads((workspace.root_path / ".pi/settings.json").read_text())["compaction"]["enabled"] is False
    projection = Path(launch.environment["CAPSTONE_PI_CONTEXT_PATH"]).read_text()
    assert "The result is available" in projection and "synthetic-loopback-key" not in projection
    session.stop()


def test_builder_fails_for_missing_native_configuration(tmp_path):
    from capstone_agent.pi_intent import NativeConversationPiSessionBuilder
    host, llm = runtime_inputs(tmp_path)
    with pytest.raises(ValueError, match="configuration is missing"):
        NativeConversationPiSessionBuilder(runtime_host=host, resolved_llm=llm,
            workspace_root=tmp_path / "workspaces", config_root=tmp_path / "missing")


def test_ordinary_session_admission_rejects_tools_and_authority_references(tmp_path, monkeypatch):
    import capstone_agent.pi_intent as module
    from capstone_agent.request_intent import IntentRequest, IntentDecision
    class Client:
        def __init__(self, *args, **kwargs):
            pass
        def stop(self):
            pass
    monkeypatch.setattr(module, "PiRpcClient", Client)
    host, llm = runtime_inputs(tmp_path)
    builder = module.NativeConversationPiSessionBuilder(runtime_host=host, resolved_llm=llm,
        workspace_root=tmp_path / "runs")
    request = IntentRequest.from_document(request_document())
    session = builder.build_execution(SimpleNamespace(intent_request=request, application_catalog=None),
        IntentDecision.from_document(decision_document(), request))
    result = session.admit_attempt(None, "A direct reply.", (), (), ())
    assert (result.mode, result.assurance) == ("offline_information", "general_knowledge")
    for results, evidence, events in [(('result:foreign',), (), ()), ((), ('evidence:foreign',), ()),
                                    ((), (), ({"capability": "business.execute"},))]:
        with pytest.raises(ValueError, match="ordinary session"):
            session.admit_attempt(None, "A direct reply.", results, evidence, events)
    session.stop()


def test_execution_projects_only_decision_resources_and_catalog_for_lookup(tmp_path, monkeypatch):
    import capstone_agent.pi_intent as module
    from capstone_agent.request_intent import IntentRequest, IntentDecision
    launches = []
    class Client:
        def __init__(self, launch, *args, **kwargs):
            launches.append(launch)
        def stop(self):
            pass
    monkeypatch.setattr(module, "PiRpcClient", Client)
    host, llm = runtime_inputs(tmp_path)
    builder = module.NativeConversationPiSessionBuilder(runtime_host=host, resolved_llm=llm,
        workspace_root=tmp_path / "runs")
    doc = request_document()
    doc["history_truncated"] = True
    doc["objects"] = [{"object_id": "model_selected"}, {"object_id": "model_other"}]
    doc["capabilities"] = [{"capability_id": "cap_selected", "enabled": True, "available": True},
        {"capability_id": "cap_other", "enabled": True, "available": True}]
    request = IntentRequest.from_document(doc)
    claim = SimpleNamespace(intent_request=request, application_catalog={"models": [{"model_id": "catalog_1"}]})
    decision = decision_document()
    session = builder.build_execution(claim, IntentDecision.from_document(decision, request))
    session.stop()
    projection = json.loads(Path(launches[-1].environment["CAPSTONE_PI_CONTEXT_PATH"]).read_text())
    context = projection["supplemental_context"]
    assert context["history_truncated"] is True
    assert context["objects"] == context["capabilities"] == []
    assert "application_catalog" not in context
    decision["goals"][0].update(operation="catalog_lookup", object_refs=["model_selected"],
                                capability_refs=["cap_selected"])
    session = builder.build_execution(claim, IntentDecision.from_document(decision, request))
    session.stop()
    context = json.loads(Path(launches[-1].environment["CAPSTONE_PI_CONTEXT_PATH"]).read_text())["supplemental_context"]
    assert context["objects"] == [{"object_id": "model_selected"}]
    assert [item["capability_id"] for item in context["capabilities"]] == ["cap_selected"]
    assert context["application_catalog"] == claim.application_catalog
    assert context["executable_goal_ids"] == ["goal_1"]


def test_business_native_policy_uses_frozen_bytes_and_provider_change_changes_identity(tmp_path):
    from dataclasses import replace
    from capability_agent.application.workspace import ApplicationWorkspace
    from capability_agent.runtime.environment import PiLaunch
    from capstone_agent.pi_intent import NativeConversationPiSessionBuilder
    host, llm = runtime_inputs(tmp_path)
    host.system_policy_path.write_text("Original domain rules")
    builder = NativeConversationPiSessionBuilder(runtime_host=host, resolved_llm=llm,
        workspace_root=tmp_path / "runs")
    original_identity = builder.identity
    host.system_policy_path.write_text("Changed domain rules")
    workspace = ApplicationWorkspace.create(tmp_path / "runs")
    launch = builder.apply_configuration(PiLaunch(("pi", "--system-prompt", "old-policy"), {}),
        workspace, "attempt_1", domain_policy=host.system_policy_path)
    assert "old-policy" not in launch.argv
    assert Path(launch.argv[-1]).read_text() == "Original domain rules"
    changed = NativeConversationPiSessionBuilder(runtime_host=host,
        resolved_llm=replace(llm, config=replace(llm.config, base_url="http://127.0.0.1:9876/v1")),
        workspace_root=tmp_path / "runs")
    assert changed.identity.config_revision != original_identity.config_revision


def test_native_identity_binds_protected_transport_config_without_exposing_it(tmp_path):
    from capability_agent.application.workspace import ApplicationWorkspace
    from capability_agent.runtime.environment import PiLaunch
    from capstone_agent.pi_intent import NativeConversationPiSessionBuilder
    host, llm = runtime_inputs(tmp_path)
    host.project_pi_dir.mkdir()
    models = host.project_pi_dir / "models.json"
    models.write_text('{"providers":{"fixture":{"baseUrl":"http://127.0.0.1:1234/v1"}}}')
    first = NativeConversationPiSessionBuilder(runtime_host=host, resolved_llm=llm,
        workspace_root=tmp_path / "runs")
    models.write_text('{"providers":{"fixture":{"baseUrl":"http://127.0.0.1:5678/v1"}}}')
    second = NativeConversationPiSessionBuilder(runtime_host=host, resolved_llm=llm,
        workspace_root=tmp_path / "runs")
    assert first.identity.config_revision != second.identity.config_revision
    assert "baseUrl" not in str(first.identity.to_document())
    with pytest.raises(ValueError, match="transport configuration changed"):
        first.apply_configuration(PiLaunch(("pi",), {}),
            ApplicationWorkspace.create(tmp_path / "runs"), "attempt_1")


def test_native_identity_binds_global_settings_and_fails_on_mutation(tmp_path):
    from capability_agent.application.workspace import ApplicationWorkspace
    from capability_agent.runtime.environment import PiLaunch
    from capstone_agent.pi_intent import NativeConversationPiSessionBuilder
    host, llm = runtime_inputs(tmp_path)
    host.project_pi_dir.mkdir()
    settings = host.project_pi_dir / "settings.json"
    settings.write_text('{"defaultThinkingLevel":"low"}')
    first = NativeConversationPiSessionBuilder(runtime_host=host, resolved_llm=llm,
        workspace_root=tmp_path / "runs")
    settings.write_text('{"defaultThinkingLevel":"high"}')
    second = NativeConversationPiSessionBuilder(runtime_host=host, resolved_llm=llm,
        workspace_root=tmp_path / "runs")
    assert first.identity.config_revision != second.identity.config_revision
    with pytest.raises(ValueError, match="global settings changed"):
        first.apply_configuration(PiLaunch(("pi",), {}),
            ApplicationWorkspace.create(tmp_path / "runs"), "attempt_1")


def test_intent_native_launch_disables_session_persistence(tmp_path):
    from capability_agent.application.workspace import ApplicationWorkspace
    from capability_agent.runtime.environment import PiLaunch
    from capstone_agent.pi_intent import NativeConversationPiSessionBuilder
    host, llm = runtime_inputs(tmp_path)
    builder = NativeConversationPiSessionBuilder(runtime_host=host, resolved_llm=llm,
        workspace_root=tmp_path / "runs")
    workspace = ApplicationWorkspace.create(tmp_path / "runs")
    launch = builder.apply_configuration(PiLaunch(("pi",), {}), workspace, "attempt_1", intent=True)
    assert "--no-session" in launch.argv
    assert "--offline" in launch.argv
    launch = builder.apply_configuration(PiLaunch(("pi",), {}), workspace, "attempt_2")
    assert "--no-session" not in launch.argv


@pytest.mark.parametrize("worker_tools_enabled", [None, False, True], ids=["adapter", "worker-tools-off", "worker-tools-on"])
def test_pinned_pi_loopback_loads_history_and_terminates_once_then_executes(tmp_path, worker_tools_enabled):
    """Real Pi, a local SSE fixture, no external provider or credentials."""
    import shutil
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from threading import Thread
    from capability_agent.runtime.lock import PiCommand, PiRuntimeIdentity
    from capstone_agent.pi_intent import NativeConversationPiSessionBuilder, PiIntentRecognizer
    from capstone_agent.request_intent import IntentRequest
    root = Path(__file__).resolve().parents[3]
    cli = root / ".grid-agent/runtime/pi/source/packages/coding-agent/dist/cli.js"
    node = shutil.which("node")
    if not cli.is_file() or node is None:
        pytest.skip("Managed Pi runtime is not installed")
    requests = []
    intent_inputs = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_POST(self):
            request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append(request)
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            if len(requests) == 1:
                content = request["messages"][-1]["content"]
                if isinstance(content, list):
                    content = "".join(block["text"] for block in content if block.get("type") == "text")
                intent_request = json.loads(content)
                intent_inputs.append(intent_request)
                decision = decision_document()
                decision.update(attempt_id=intent_request["attempt_id"], history_cutoff=intent_request["history_cutoff"])
                decision["goals"][0]["message_refs"] = [next(message["message_id"]
                    for message in intent_request["messages"] if message["role"] == "assistant")]
                delta = {"role": "assistant", "tool_calls": [{"index": 0, "id": "call_fixture",
                    "type": "function", "function": {"name": "capstone_intent_decision",
                    "arguments": json.dumps(decision)}}]}
                reason = "tool_calls"
            else:
                delta = {"role": "assistant", "content": "Translated fixture answer."}
                reason = "stop"
            for content, finish in [(delta, None), ({}, reason)]:
                chunk = {"id": "fixture_response", "object": "chat.completion.chunk", "created": 0,
                    "model": "fixture-model", "choices": [{"index": 0, "delta": content,
                    "finish_reason": finish}]}
                self.wfile.write(("data: " + json.dumps(chunk) + "\n\n").encode())
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        command = PiCommand((node, str(cli)), PiRuntimeIdentity(path=cli, source="managed-fixture",
            package_version="0.84.4", lock_sha256="fixture"))
        host, llm = runtime_inputs(tmp_path, f"http://127.0.0.1:{server.server_port}/v1", command)
        host.project_pi_dir.mkdir()
        (host.project_pi_dir / "models.json").write_text(json.dumps({"providers": {"fixture": {
            "baseUrl": llm.config.base_url, "api": "openai-completions", "apiKey": "$FIXTURE_API_KEY",
            "models": [{"id": "fixture-model", "reasoning": False}]}}}))
        builder = NativeConversationPiSessionBuilder(runtime_host=host, resolved_llm=llm,
            workspace_root=tmp_path / "runs", base_environment={"PATH": os.environ["PATH"]})
        if worker_tools_enabled is None:
            request = IntentRequest.from_document(request_document())
            decision = PiIntentRecognizer(builder.build_intent, builder.identity).recognize(request, Control())
            assert len(requests) == 1, "Terminating decision must avoid a follow-up model request"
            assert not [path for path in (tmp_path / "runs").rglob("*.jsonl") if "session" in path.parts], \
                "Intent preparation must not persist native session messages or thinking"
            session = builder.build_execution(SimpleNamespace(intent_request=request, application_catalog=None), decision)
            try:
                session.start()
                answer = session.prompt_and_wait("Translate that answer.", on_semantic_event=lambda event: None,
                    correlation_id="attempt_1", on_heartbeat=lambda: None)
            finally:
                session.stop()
        else:
            from capstone_agent.intent_runtime import IntentRuntimeFactory
            from capstone_agent.thread_service import InMemoryThreadService
            from capstone_agent.thread_worker import run_pending_attempt
            from capstone_model_capability_spi import ModelCapabilitySelection
            selection = ModelCapabilitySelection((("fixture-profile", "1.0.0"),) if worker_tools_enabled else ())
            service = InMemoryThreadService.from_document({
                "schema": "capstone-thread-snapshot/1", "thread_id": "thread_loopback",
                "run": {"run_id": "run_loopback", "state": "open"},
                "active_model_context": {"id": "context_loopback", "model_id": "fixture-grid",
                    "model_revision": "revision_fixture", "implementation_family": "pandapower",
                    "selection_revision": "selection_fixture", "enabled_profiles": selection.to_document()},
                "active_grid_page_id": "page_fixture", "current_attempt": None,
                "last_event_seq": 0, "base_event_seq": 0,
            })

            def submit(command_id, text):
                service.submit_command({"schema": "capstone-command/1", "command_id": command_id,
                    "idempotency_key": command_id, "thread_id": "thread_loopback", "run_id": "run_loopback",
                    "kind": "send_auto", "expected_event_seq": service.snapshot("thread_loopback").last_event_seq,
                    "payload": {"text": text}})

            submit("command_prior", "What is available?")
            prior = service.claim_attempt("seed_worker", 30)
            assert prior is not None
            service.finish_attempt(prior, phase="completed", payload={"answer": "The result is available."})
            submit("command_current", "Translate that answer.")
            factory = IntentRuntimeFactory(
                lambda claim: pytest.fail("Ordinary worker prepared a business Domain Pack"),
                lambda: PiIntentRecognizer(builder.build_intent, builder.identity), builder.build_execution)
            result = run_pending_attempt(service, factory, worker_id="native_loopback_worker")
            assert result is not None and result.status == "completed", result
            assert result.result_refs == result.evidence_refs == ()
            assert result.admission == {"mode": "offline_information", "assurance": "general_knowledge"}
            answer = result.answer
            events = service.read_events("thread_loopback", 0).events
            current = [event for event in events if event.attempt_id != prior.attempt.attempt_id]
            types = [event.event_type for event in current]
            assert types.index("intent_started") < types.index("turn_plan_created") < types.index("attempt_completed")
            completed = next(event for event in current if event.event_type == "attempt_completed")
            assert completed.payload["result_refs"] == completed.payload["evidence_refs"] == []
            plan = next(event for event in current if event.event_type == "turn_plan_created")
            assert plan.payload["route"] == "ordinary"
            assert bool(intent_inputs[0]["capabilities"]) == worker_tools_enabled
            assert service.snapshot("thread_loopback").active_model_context.enabled_profiles == selection.enabled_profiles
            assert service.snapshot("thread_loopback").current_attempt is None
        assert answer == "Translated fixture answer." and len(requests) == 2
        for captured in requests:
            history = next(message for message in captured["messages"]
                if message["role"] == "assistant" and "The result is available" in str(message["content"]))
            assert history["role"] == "assistant"
            system = captured["messages"][0]["content"]
            assert "You are Capstone" in system and "The result is available" not in system
            assert "GRID DOMAIN ROLE" not in system
            if worker_tools_enabled is not None:
                assert any(message["role"] == "user" and "What is available?" in str(message["content"])
                           for message in captured["messages"])
                assert "What is available?" not in system
        assert [tool["function"]["name"] for tool in requests[0]["tools"]] == ["capstone_intent_decision"]
        assert not requests[1].get("tools")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
