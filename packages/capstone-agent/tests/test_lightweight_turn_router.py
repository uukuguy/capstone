import pytest

from capstone_agent.turn_router import DecisionUnavailable, DefaultTurnRouter, RoutingInput


def test_lightweight_route_does_not_compile_or_rewrite_instruction():
    from capstone_agent.lightweight_turn_router import LightweightTurnRouter
    calls = []
    request = RoutingInput("turn_1", "attempt_1", "业务原始指令", "send_auto", {"model_id": "ieee39"})
    router = LightweightTurnRouter(lambda value: calls.append(value) or "professional")
    plan = DefaultTurnRouter(decision_router=router).plan(request)
    assert plan.route == "professional"
    assert plan.source == "llm"
    assert calls == [request]


def test_invalid_llm_route_does_not_fall_back_to_keywords():
    from capstone_agent.lightweight_turn_router import LightweightTurnRouter
    request = RoutingInput("turn_1", "attempt_1", "执行潮流", "send_auto", {})
    with pytest.raises(DecisionUnavailable):
        DefaultTurnRouter(decision_router=LightweightTurnRouter(lambda _: "invalid")).plan(request)


def test_pi_classifier_has_no_tools_and_receives_only_route_input(monkeypatch, tmp_path):
    import json
    from types import SimpleNamespace
    import capstone_agent.lightweight_turn_router as module
    observed = {}
    resolutions = []
    def resolve_model():
        resolutions.append(1)
        return SimpleNamespace(secret=None)
    class Client:
        def __init__(self, launch, workspace, trace, **kwargs):
            observed["launch"] = launch
            assert workspace.root_path.is_dir()
        def start(self):
            pass
        def prompt_and_wait(self, text):
            observed["input"] = json.loads(text)
            return '{"schema":"capstone-intent-route/1","route":"professional"}'
        def stop(self):
            observed["stopped"] = True
    monkeypatch.setattr(module, "PiRpcClient", Client)
    monkeypatch.setattr(module, "build_pi_launch", lambda *_args, **_kwargs:
        SimpleNamespace(argv=("pi", "--no-builtin-tools", "--no-extensions"), environment={}))
    router = module.build_lightweight_router(runtime_host=SimpleNamespace(command=None, project_pi_dir=tmp_path),
        resolved_llm_factory=resolve_model, environment={})
    assert resolutions == []
    request = RoutingInput("turn_1", "attempt_1", "original question", "send_auto", {"model_id": "ieee39"})
    assert router.plan(request).route == "professional"
    assert resolutions == [1]
    assert set(observed["input"]) == {"instruction", "selected_model"}
    assert "--thinking" in observed["launch"].argv
    assert observed["stopped"]


def test_worker_reports_route_failure_without_running_execution():
    from test_thread_worker import _service
    from capstone_agent.thread_worker import run_pending_attempt
    from capstone_agent.lightweight_turn_router import LightweightTurnRouter
    service = _service()
    service.submit_command({"schema": "capstone-command/1", "command_id": "cmd_route_failure",
        "idempotency_key": "idem_route_failure", "thread_id": "thr_worker", "run_id": "run_worker",
        "kind": "send_auto", "expected_event_seq": 0, "payload": {"text": "inspect"}})
    def execute(_claim):
        pytest.fail("execution must not run after a failed route")
    result = run_pending_attempt(service, execute, worker_id="worker",
        turn_router=LightweightTurnRouter(lambda _: "invalid"))
    assert result.error_code == "llm_route_unavailable"
