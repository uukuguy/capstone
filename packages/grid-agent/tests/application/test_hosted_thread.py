from __future__ import annotations

from grid_agent.hosted import build_registered_pandapower_thread_application
from grid_agent import hosted_worker
from grid_simulator.model_catalog import load_model_catalog


def test_provider_configuration_failure_keeps_prepared_context_and_safe_code(monkeypatch, tmp_path):
    import json
    from capstone_agent.thread_service import InMemoryThreadService, ThreadCreator
    from capstone_agent.thread_worker import run_pending_attempt
    from capability_agent.runtime.models import ConfigurationError
    import grid_agent.hosted as hosted
    import capstone_agent.runtime as runtime

    monkeypatch.delenv("CAPSTONE_THREAD_VALIDATION", raising=False)
    monkeypatch.setenv("CAPSTONE_RUNS_ROOT", str(tmp_path))
    calls = []

    def unavailable(**_kwargs):
        calls.append(1)
        raise ConfigurationError("private-credential-sentinel: missing API key")

    monkeypatch.setattr(runtime, "resolve_llm", unavailable)
    assembly = hosted.build_registered_pandapower_thread_application()

    class CreatorStore:
        def create_thread(self, snapshot):
            return snapshot

    snapshot = ThreadCreator(CreatorStore(), assembly.catalog, assembly.capability_catalog).create()
    service = InMemoryThreadService(snapshot, capability_catalog=assembly.capability_catalog, model_catalog=assembly.catalog)
    rollbacks = []
    monkeypatch.setattr(service, "rollback_context_if_preparation_failed", lambda *_args, **_kwargs: rollbacks.append(1))
    service.submit_command({
        "schema": "capstone-command/1", "command_id": "cmd_configuration",
        "idempotency_key": "idem_configuration", "thread_id": snapshot.thread_id,
        "run_id": snapshot.run.run_id, "kind": "send_professional", "expected_event_seq": 0,
        "payload": {"text": "有哪些 PyPSA 的电网模型？"},
    })
    try:
        result = run_pending_attempt(service, assembly.runtime_factory, worker_id="configuration-test")
        assert calls == [1]
        assert result is not None and result.error_code == "runtime_configuration_invalid"
        assert rollbacks == []
        assert service.snapshot(snapshot.thread_id).active_model_context == snapshot.active_model_context
        assert service.snapshot(snapshot.thread_id).current_attempt is None
        events = service.read_events(snapshot.thread_id, 0).events
        assert events[-1].event_type == "attempt_failed"
        assert events[-1].payload == {"error_code": "runtime_configuration_invalid"}
        assert "private-credential-sentinel" not in json.dumps([dict(e.payload) for e in events])
    finally:
        assembly.capability_context_owner.close()


def test_hosted_pandapower_thread_assembly_registers_default_profile():
    assembly = build_registered_pandapower_thread_application()
    try:
        descriptor = assembly.catalog.resolve("ieee39")
        assert descriptor.implementation_family == "pandapower"
        assert assembly.capability_catalog is not None
        selected = assembly.capability_catalog.resolve(descriptor)
        assert selected.enabled_profiles == (("pandapower-static-analysis", "1.0.1"),)
        assert callable(assembly.runtime_factory)
        assert set(assembly.catalog.list_model_ids()) == {model["model_id"] for model in load_model_catalog()}
        rts = assembly.catalog.resolve("case24_ieee_rts")
        assert rts.authority_model_ref == "gridctl:case24_ieee_rts"
        assert rts.diagram_provider_id == "gridctl"
    finally:
        if assembly.capability_context_owner is not None:
            assembly.capability_context_owner.close()


def test_grid_hosted_worker_delegates_factory_to_capstone_host(monkeypatch) -> None:
    assembly = object()
    seen = []

    monkeypatch.setattr(
        hosted_worker,
        "build_registered_pandapower_thread_application",
        lambda: assembly,
    )
    monkeypatch.setattr(
        hosted_worker,
        "run_hosted_worker",
        lambda factory: seen.append(factory) or 37,
    )

    assert hosted_worker.main() == 37
    assert seen == [hosted_worker.build_worker_application]
