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
        resolved_llm=SimpleNamespace(secret=None), environment={})
    request = RoutingInput("turn_1", "attempt_1", "original question", "send_auto", {"model_id": "ieee39"})
    assert router.plan(request).route == "professional"
    assert set(observed["input"]) == {"instruction", "selected_model"}
    assert "--thinking" in observed["launch"].argv
    assert observed["stopped"]
