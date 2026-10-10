from __future__ import annotations

from dataclasses import replace
from typing import Any, cast

from fastapi.testclient import TestClient
import pytest

from capstone_agent.host_api import create_host_app
from capstone_agent.harness import HarnessRuntimeRegistry
from capstone_agent.session import WorkerRegistry
from capstone_agent.thread_application import ApplicationPiRuntimeFactory
from capstone_agent.thread_application import FamilyRuntimeFactory
from capstone_agent.thread_application import PreparedApplicationPiRuntimeFactory
from capstone_agent.thread_application import ThreadApplicationAssembly
from capstone_agent.model_capability import CapstoneModelCapabilityCatalog, ModelCapabilityProfileInfo
from capstone_agent.model_capability_context import ModelCapabilityContextOwner
from capstone_agent.thread_service import AttemptClaim
from capstone_agent.thread_protocol import AttemptSnapshot, ModelContextSnapshot
from capstone_agent.thread_service import InMemoryThreadService
from capstone_agent.thread_worker import run_pending_attempt
from capstone_model_capability_spi import ModelCapabilityDescriptor, ModelCapabilityRegistry


class _Session:
    def start(self) -> None:
        return None

    def prompt_and_wait(self, question: str, **kwargs: object) -> str:
        del question, kwargs
        return "answer"

    def stop(self) -> None:
        return None


class _Handle:
    def __init__(self, descriptor: ModelCapabilityDescriptor) -> None:
        self.descriptor = descriptor

    def close(self) -> None:
        return None


class _Contribution:
    def __init__(self, descriptor: ModelCapabilityDescriptor, model_context: ModelContextSnapshot) -> None:
        self.descriptor = descriptor
        self.model_context = model_context
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _Adapter:
    def __init__(self, descriptor: ModelCapabilityDescriptor) -> None:
        self.descriptor = descriptor
        self.contexts: list[ModelContextSnapshot] = []

    def prepare(self, _handle, *, model_context: ModelContextSnapshot) -> _Contribution:
        self.contexts.append(model_context)
        return _Contribution(self.descriptor, model_context)


def _prepared_owner() -> tuple[ModelCapabilityContextOwner, _Adapter]:
    descriptor = ModelCapabilityDescriptor("static", "1.0.0")
    registry = ModelCapabilityRegistry()
    catalog = CapstoneModelCapabilityCatalog(registry)
    catalog.register_profile(
        ModelCapabilityProfileInfo(descriptor, "Static", ("pandapower",)),
        lambda: _Handle(descriptor),
    )
    owner = ModelCapabilityContextOwner(catalog)
    adapter = _Adapter(descriptor)
    owner.register_adapter(descriptor.reference, adapter)
    registry.seal()
    owner.seal()
    return owner, adapter


class _CreatorService:
    def __init__(self) -> None:
        self.snapshot = None

    def create_thread(self, snapshot):
        self.snapshot = snapshot
        return snapshot


class _Ledger:
    def ping(self) -> bool:
        return True


def _runtime_service() -> InMemoryThreadService:
    return InMemoryThreadService.from_document({
        "schema": "capstone-thread-snapshot/1", "thread_id": "thr_runtime",
        "run": {"run_id": "run_runtime", "state": "open"},
        "active_model_context": {
            "id": "ctx_ieee39", "model_id": "ieee39",
            "model_revision": "revision:sha256:" + "d" * 64,
            "implementation_family": "pandapower", "selection_revision": "sel_0",
        },
        "active_grid_page_id": "page_ieee39", "current_attempt": None,
        "last_event_seq": 0, "base_event_seq": 0,
    })


def _claim() -> AttemptClaim:
    return AttemptClaim(
        thread_id="thr_application", run_id="run_application",
        attempt=AttemptSnapshot("turn_1", "attempt_1", "running", "ctx_ieee39"),
        kind="send_ordinary", instruction="inspect", model_context_id="ctx_ieee39",
        selection_revision="sel_0", lease_token="lease_1",
        model_context=ModelContextSnapshot(
            "ctx_ieee39", "ieee39", "revision:sha256:" + "a" * 64, "pandapower", "sel_0",
        ),
    )


class _Runtime:
    def start(self) -> None: pass
    def prompt(self, question: str, **kwargs: object) -> str:
        return "answer"
    def stop(self) -> None: pass


def test_family_runtime_factory_dispatches_from_immutable_model_context() -> None:
    pandapower = _Runtime()
    pypsa = _Runtime()
    factory = FamilyRuntimeFactory({
        "pandapower": lambda claim: pandapower,
        "pypsa": lambda claim: pypsa,
    })

    assert factory(_claim()) is pandapower
    pypsa_claim = replace(
        _claim(),
        model_context=replace(_claim().model_context, implementation_family="pypsa"),
    )
    assert factory(pypsa_claim) is pypsa
    with pytest.raises(RuntimeError, match="implementation family"):
        FamilyRuntimeFactory({"pandapower": lambda claim: pandapower})(pypsa_claim)


def test_composite_application_assembly_uses_family_dispatcher() -> None:
    class Catalog:
        default_model_id = "ieee39"
        def resolve(self, model_id):
            return _claim().model_context

    catalog = Catalog()
    assembly = ThreadApplicationAssembly.from_composite_authority(
        catalog=catalog,
        runtime_factories={"pandapower": lambda claim: _Runtime()},
    )
    assert assembly.catalog is catalog
    assert assembly.runtime_factory(_claim()) is not None


def test_application_assembly_accepts_harness_runtime_registry() -> None:
    class Catalog:
        default_model_id = "ieee39"

        def resolve(self, model_id):
            return _claim().model_context

    runtime = _Runtime()
    registry = HarnessRuntimeRegistry()
    registry.register("pi", lambda _claim: runtime)
    assembly = ThreadApplicationAssembly(
        catalog=cast(Any, Catalog()),
        runtime_registry=registry,
        runtime_name="pi",
    )

    assert assembly.runtime_registry is registry
    assert assembly.runtime_factory(_claim()) is runtime


def test_application_assembly_rejects_conflicting_runtime_factory_and_registry() -> None:
    class Catalog:
        default_model_id = "ieee39"

        def resolve(self, model_id):
            return _claim().model_context

    selected = _Runtime()
    registry = HarnessRuntimeRegistry()
    registry.register("pi", lambda _claim: selected)

    with pytest.raises(ValueError, match="runtime registry selection"):
        ThreadApplicationAssembly(
            catalog=cast(Any, Catalog()),
            runtime_factory=lambda _claim: _Runtime(),
            runtime_registry=registry,
            runtime_name="pi",
        )


def test_application_factory_wraps_injected_session_as_harness_runtime() -> None:
    received: list[AttemptClaim] = []
    factory = ApplicationPiRuntimeFactory(
        lambda claim: received.append(claim) or _Session(), runtime_mode="capstone",
    )

    runtime = factory(_claim())
    runtime.start()
    assert runtime.prompt("inspect", on_event=lambda _event: None) == "answer"
    runtime.stop()
    assert received[0].attempt.attempt_id == "attempt_1"


def test_application_assembly_binds_authority_catalog_and_pi_factory() -> None:
    service = _CreatorService()
    sessions: list[AttemptClaim] = []
    assembly = ThreadApplicationAssembly.from_authority(
        default_model_id="ieee39",
        model_resolver=lambda model_id: {
            "model_id": model_id,
            "revision_ref": "revision:sha256:" + "b" * 64,
            "implementation_family": "pandapower",
        },
        session_factory=lambda claim: sessions.append(claim) or _Session(),
    )

    created = assembly.thread_creator(service).create()
    assert created.active_model_context.model_revision == "revision:sha256:" + "b" * 64
    runtime = assembly.runtime_factory(_claim())
    runtime.start()
    assert runtime.prompt("inspect", on_event=lambda _event: None) == "answer"
    runtime.stop()
    assert sessions[0].attempt.attempt_id == "attempt_1"


def test_application_assembly_requires_catalog_and_runtime_together() -> None:
    try:
        ThreadApplicationAssembly(catalog=object(), runtime_factory=None)  # type: ignore[arg-type]
    except TypeError:
        return
    raise AssertionError("invalid assembly must fail closed")


def test_host_app_can_accept_the_complete_application_assembly() -> None:
    service = _CreatorService()
    assembly = ThreadApplicationAssembly.from_authority(
        default_model_id="ieee39",
        model_resolver=lambda model_id: {
            "model_id": model_id,
            "revision_ref": "revision:sha256:" + "c" * 64,
            "implementation_family": "pandapower",
        },
        session_factory=lambda _claim: _Session(),
    )
    app = create_host_app(
        _Ledger(), WorkerRegistry(()), operator_token="hosted-secret",
        allowed_hosts={"localhost"}, allowed_origins={"http://localhost:5173"},
        thread_service=service, thread_application=assembly,
    )

    with TestClient(app, base_url="http://localhost") as client:
        response = client.post(
            "/api/v1/threads",
            headers={"Authorization": "Bearer hosted-secret"},
            json={},
        )

    assert response.status_code == 201
    assert response.json()["active_model_context"]["model_revision"] == (
        "revision:sha256:" + "c" * 64
    )


def test_assembly_runtime_worker_and_sse_share_one_thread_contract() -> None:
    service = _runtime_service()
    assembly = ThreadApplicationAssembly.from_authority(
        default_model_id="ieee39",
        model_resolver=lambda model_id: {
            "model_id": model_id,
            "revision_ref": "revision:sha256:" + "d" * 64,
            "implementation_family": "pandapower",
        },
        session_factory=lambda _claim: _Session(),
    )
    service.submit_command({
        "schema": "capstone-command/1", "command_id": "cmd_runtime_001",
        "idempotency_key": "idem_runtime_001", "thread_id": "thr_runtime",
        "run_id": "run_runtime", "kind": "send_ordinary", "expected_event_seq": 0,
        "payload": {"text": "inspect"},
    })

    result = run_pending_attempt(
        service, assembly.runtime_factory, worker_id="assembly-worker",
    )
    assert result is not None and result.status == "completed"

    app = create_host_app(
        _Ledger(), WorkerRegistry(()), operator_token="hosted-secret",
        allowed_hosts={"localhost"}, allowed_origins={"http://localhost:5173"},
        thread_service=service, thread_application=assembly,
    )
    with TestClient(app, base_url="http://localhost") as client:
        assert client.get("/api/v1/threads/thr_runtime").status_code == 401
        stream = client.get(
            "/api/v1/threads/thr_runtime/events/stream?after=0",
            headers={"Authorization": "Bearer hosted-secret"},
        )

    assert stream.status_code == 200
    assert "event: command_accepted" in stream.text
    assert "event: attempt_started" in stream.text
    assert "event: attempt_completed" in stream.text


def test_prepared_application_factory_passes_context_to_session_without_closing_it_on_stop() -> None:
    owner, adapter = _prepared_owner()
    claim = replace(
        _claim(),
        model_context=replace(_claim().model_context, enabled_profiles=(("static", "1.0.0"),)),
    )
    received = []
    factory = PreparedApplicationPiRuntimeFactory(
        owner,
        lambda claim, context: received.append((claim, context)) or _Session(),
    )
    runtime = factory(claim)
    runtime.start()
    assert runtime.prompt("inspect", on_event=lambda _event: None) == "answer"
    runtime.stop()
    assert received[0][0].attempt.attempt_id == "attempt_1"
    assert received[0][1].model_context == claim.model_context
    assert len(adapter.contexts) == 1
    assert not received[0][1].closed
    owner.close_run("thr_application", "run_application")
    assert received[0][1].closed


def test_failed_session_preparation_releases_the_context_pin():
    owner, _ = _prepared_owner()
    claim = replace(_claim(), model_context=replace(_claim().model_context, enabled_profiles=(("static", "1.0.0"),)))

    def fail(_claim, _context):
        raise RuntimeError('session preparation failed')

    with pytest.raises(RuntimeError, match='session preparation failed'):
        PreparedApplicationPiRuntimeFactory(owner, fail)(claim)
    assert owner.resource_counts() == {'retained': 1, 'active': 0}
    owner.close_run(claim.thread_id, claim.run_id)
    assert owner.resource_counts() == {'retained': 0, 'active': 0}


def test_prepared_application_factory_passes_exact_claim_and_context_to_network_provider() -> None:
    owner, _ = _prepared_owner()
    claim = replace(
        _claim(),
        model_context=replace(_claim().model_context, enabled_profiles=(("static", "1.0.0"),)),
    )
    received = []
    factory = PreparedApplicationPiRuntimeFactory(
        owner,
        lambda _claim, _context: _Session(),
        network_projection_factory=lambda claimed, context: received.append((claimed, context)) or None,
    )

    first_runtime = factory(claim)

    assert len(received) == 1
    assert received[0][0] is claim
    assert received[0][1].model_context == claim.model_context

    class _Provider:
        def project(self, _claim, _results, _evidence, _events):
            return None

    runtime = PreparedApplicationPiRuntimeFactory(
        owner,
        lambda _claim, _context: _Session(),
        network_projection_factory=lambda _claimed, _context: _Provider(),
    )(claim)
    assert getattr(runtime, "network_projection_enabled") is True
    first_runtime.stop()
    runtime.stop()
    owner.close_run("thr_application", "run_application")


def test_prepared_application_factory_does_not_start_session_after_preparation_failure() -> None:
    owner, _ = _prepared_owner()
    called = []

    def fail_session(_claim, _context):
        called.append(True)
        raise RuntimeError("session setup failed")

    factory = PreparedApplicationPiRuntimeFactory(owner, fail_session)
    claim = replace(
        _claim(),
        model_context=replace(_claim().model_context, enabled_profiles=(("static", "1.0.0"),)),
    )
    with pytest.raises(RuntimeError, match="session setup failed"):
        factory(claim)
    assert called == [True]
    owner.close()


def test_empty_selection_skips_domain_network_projection_and_releases_context():
    owner, adapter = _prepared_owner()
    def projection(claim, context):
        pytest.fail("Empty selection must not prepare a Domain Pack projection")
    runtime = PreparedApplicationPiRuntimeFactory(
        owner, lambda claim, context: _Session(), network_projection_factory=projection,
    )(_claim())
    assert not runtime.network_projection_enabled
    assert adapter.contexts == []
    runtime.start()
    assert runtime.prompt("hello", on_event=lambda event: None) == "answer"
    runtime.stop()
    assert owner.resource_counts()["active"] == 0
    owner.close()


def test_prepared_authority_assembly_keeps_catalog_owner_and_runtime_paired() -> None:
    owner, _ = _prepared_owner()
    assembly = ThreadApplicationAssembly.from_prepared_authority(
        default_model_id="ieee39",
        model_resolver=lambda model_id: {
            "model_id": model_id,
            "revision_ref": "revision:sha256:" + "b" * 64,
            "implementation_family": "pandapower",
        },
        capability_catalog=owner.catalog,
        capability_context_owner=owner,
        session_factory=lambda _claim, _context: _Session(),
    )
    assert assembly.capability_context_owner is owner
    assert assembly.capability_catalog is owner.catalog
    assert isinstance(assembly.runtime_factory, PreparedApplicationPiRuntimeFactory)
    owner.close()
