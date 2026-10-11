from types import SimpleNamespace

import pytest


@pytest.mark.parametrize("scripted", [False, True])
def test_registered_pypsa_hosted_recognizer_forwards_public_schema(monkeypatch, tmp_path, scripted):
    import pypsa_agent.hosted as hosted
    from capstone_agent.kernel_pi_session import PreparedKernelPiSessionFactory
    monkeypatch.setenv("CAPSTONE_RUNS_ROOT", str(tmp_path))
    schemas = ({"binding_id": "source", "schema": "capstone-professional-task/1"},)
    calls = []
    def recognize(claim, *, on_heartbeat, requirement_schemas=()):
        on_heartbeat()
        calls.append((claim, requirement_schemas))
        return "controlled recognition"
    class Builder:
        recognize_task = staticmethod(recognize)
        def __call__(self, *args):
            pytest.fail("recognition must not create execution session")
    monkeypatch.setattr(hosted, "select_validation_builder", lambda *_: Builder() if scripted else None)
    monkeypatch.setattr(hosted, "load_runtime_environment", lambda *_: {})
    monkeypatch.setattr(hosted, "resolve_harness_llm", lambda *_: object())
    monkeypatch.setattr(hosted, "build_runtime_host", lambda *_: object())
    monkeypatch.setattr(hosted, "PreparedKernelPiRpcSessionBuilder", lambda **_: Builder())
    assembly = hosted.build_registered_pypsa_thread_application()
    try:
        factory = assembly.runtime_factory._session_factory
        assert isinstance(factory, PreparedKernelPiSessionFactory)
        claim = SimpleNamespace()
        beats = []
        assert factory.recognize_task(claim, on_heartbeat=lambda: beats.append(1), requirement_schemas=schemas) == "controlled recognition"
        assert calls == [(claim, schemas)] and beats == [1]
    finally:
        assembly.capability_context_owner.close()
