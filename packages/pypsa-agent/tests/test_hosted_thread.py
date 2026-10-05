from __future__ import annotations

from typing import cast

from capstone_agent.model_capability import CapstoneModelCapabilityCatalog
from capstone_agent.thread_catalog import AuthorityThreadModelCatalog
import pypsa_agent.hosted as hosted
import pypsa_agent.hosted_worker as hosted_worker


def test_provider_configuration_failure_keeps_prepared_context_and_safe_code(monkeypatch, tmp_path):
    import json
    from capstone_agent.thread_service import InMemoryThreadService, ThreadCreator
    from capstone_agent.thread_worker import run_pending_attempt
    from capability_agent.runtime.models import ConfigurationError

    monkeypatch.delenv("CAPSTONE_THREAD_VALIDATION", raising=False)
    monkeypatch.setenv("CAPSTONE_RUNS_ROOT", str(tmp_path))
    calls = []

    def unavailable(**_kwargs):
        calls.append(1)
        raise ConfigurationError("private-credential-sentinel: missing API key")

    monkeypatch.setattr(hosted, "resolve_llm", unavailable)
    assembly = hosted.build_registered_pypsa_thread_application()

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
        "payload": {"text": "查看当前模型"},
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


def test_registered_pypsa_thread_application_uses_the_capstone_host() -> None:
    assembly = hosted.build_registered_pypsa_thread_application()

    catalog = cast(AuthorityThreadModelCatalog, assembly.catalog)
    assert catalog.default_model_id == "regional-six-bus"
    assert "regional-six-bus" in catalog.list_model_ids()
    capability_catalog = cast(CapstoneModelCapabilityCatalog, assembly.capability_catalog)
    assert any(
        profile.descriptor.profile_id == "pypsa-business-cases"
        for profile in capability_catalog.profiles_for_family("pypsa")
    )
    assert assembly.network_projection_factory is not None


def test_pypsa_model_resolver_returns_stable_authority_revision() -> None:
    resolver = hosted.RegisteredPyPSAThreadCatalog()

    record = resolver.resolve("regional-six-bus")

    assert record.model_id == "regional-six-bus"
    assert record.model_revision.startswith("revision:sha256:")
    assert len(record.model_revision.rsplit(":", 1)[-1]) == 64
    assert record.implementation_family == "pypsa"


def test_hosted_entrypoints_delegate_to_capstone(monkeypatch) -> None:
    sentinel = object()
    seen: list[object] = []

    monkeypatch.setattr(hosted, "build_registered_pypsa_thread_application", lambda: sentinel)
    monkeypatch.setattr(hosted, "run_hosted_api", lambda factory: seen.append(factory()) or 17)
    assert hosted.main() == 17
    assert seen == [sentinel]


def test_hosted_worker_entrypoint_delegates_to_capstone(monkeypatch) -> None:
    sentinel = object()
    seen: list[object] = []

    monkeypatch.setattr(
        hosted_worker,
        "build_registered_pypsa_thread_application",
        lambda: sentinel,
    )
    monkeypatch.setattr(
        hosted_worker,
        "run_hosted_worker",
        lambda factory: seen.append(factory()) or 23,
    )

    assert hosted_worker.main() == 23
    assert seen == [sentinel]
