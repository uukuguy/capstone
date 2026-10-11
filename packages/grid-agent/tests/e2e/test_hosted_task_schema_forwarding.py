"""Exercise the real composed hosted recognizer adapters without Provider calls."""
from types import SimpleNamespace

import pytest


@pytest.mark.parametrize("family", ["pandapower"])
@pytest.mark.parametrize("scripted", [False, True])
def test_registered_hosted_recognizer_forwards_public_schema(monkeypatch, tmp_path, family, scripted):
    if family == "pandapower":
        import grid_agent.hosted as hosted
        create = hosted.build_registered_pandapower_thread_application
    else:
        import pypsa_agent.hosted as hosted
        create = hosted.build_registered_pypsa_thread_application
    from capstone_agent.kernel_pi_session import PreparedKernelPiSessionFactory
    monkeypatch.setenv("CAPSTONE_RUNS_ROOT", str(tmp_path))
    schemas = ({"binding_id": "controlled", "schema": "controlled/1"},)
    calls = []
    def recognize(claim, *, on_heartbeat, requirement_schemas=()):
        on_heartbeat()
        calls.append((claim, requirement_schemas))
        return "controlled recognition"
    class Builder:
        recognize_task = staticmethod(recognize)
        def route_task(self, claim, *, on_heartbeat):
            on_heartbeat()
            return "controlled route"
        def routing_metrics(self):
            return {"phase": "routing"}
        def __call__(self, *args):
            pytest.fail("recognition must not build execution session")
    monkeypatch.setattr(hosted, "select_validation_builder", lambda *_: Builder() if scripted else None)
    monkeypatch.setattr(hosted, "load_runtime_environment", lambda *_: {})
    monkeypatch.setattr(hosted, "resolve_harness_llm", lambda *_: object())
    monkeypatch.setattr(hosted, "build_runtime_host", lambda *_: object())
    monkeypatch.setattr(hosted, "PreparedKernelPiRpcSessionBuilder", lambda **_: Builder())
    assembly = create()
    try:
        factory = assembly.runtime_factory._session_factory
        assert isinstance(factory, PreparedKernelPiSessionFactory)
        claim = SimpleNamespace()
        beats = []
        assert factory.recognize_task(claim, on_heartbeat=lambda: beats.append(1), requirement_schemas=schemas) == "controlled recognition"
        assert calls == [(claim, schemas)] and beats == [1]
        monkeypatch.setattr(assembly.capability_context_owner, "acquire", lambda *_: pytest.fail("routing must not prepare a Pack"))
        assert assembly.runtime_factory.route_task(claim, on_heartbeat=lambda: None) == (None if scripted else "controlled route")
        assert assembly.runtime_factory.routing_metrics(claim) == ({} if scripted else {"phase": "routing"})
    finally:
        assembly.capability_context_owner.close()


@pytest.mark.parametrize("family", ["pandapower", "pypsa"])
def test_m11_scripted_recognizer_consumes_selected_schema(family, monkeypatch):
    from pathlib import Path
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[4]))
    from validation.thread.m11_session import build_m11_session_builder, INSTRUCTIONS, MODELS
    from capstone_agent.task_understanding import TaskRequest, SCHEMA_V2
    request = TaskRequest("thread", "turn", "attempt", INSTRUCTIONS[family][0], 0, "context", MODELS[family], "revision")
    schema = "pandapower-task-requirement/1" if family == "pandapower" else "capstone-professional-task/1"
    claim = SimpleNamespace(instruction=request.instruction, task_request=request,
                            model_context=SimpleNamespace(model_id=MODELS[family], implementation_family=family))
    result = build_m11_session_builder(family).recognize_task(claim, on_heartbeat=lambda: None,
        requirement_schemas=({"binding_id": "selected", "schema": schema},))
    assert result.schema == SCHEMA_V2
    assert result.goals[0].domain_request.binding_id == "selected"
