from __future__ import annotations

from fastapi.testclient import TestClient

from capstone_agent.host_api import create_host_app
from capstone_agent.session import WorkerRegistry
from capstone_agent.thread_protocol import CommandReceipt, EventPage, ThreadSnapshot
from capstone_agent.thread_service import ThreadCreator, ThreadModelDescriptor
from capstone_agent.model_capability import CapstoneModelCapabilityCatalog, ModelCapabilityProfileInfo
from capstone_model_capability_spi import ModelCapabilityDescriptor, ModelCapabilityRegistry, ModelCapabilitySelection


class _Catalog:
    default_model_id = "ieee39"

    def resolve(self, model_id: str | None) -> ThreadModelDescriptor:
        if model_id not in {None, "ieee39"}:
            raise ValueError("model is not registered")
        return ThreadModelDescriptor("ieee39", "revision:sha256:" + "a" * 64, "pandapower")


class _Handle:
    def __init__(self, descriptor: ModelCapabilityDescriptor) -> None:
        self.descriptor = descriptor

    def close(self) -> None:
        return None


class _Service:
    def __init__(self) -> None:
        self.created: ThreadSnapshot | None = None

    def create_thread(self, snapshot: ThreadSnapshot) -> ThreadSnapshot:
        self.created = snapshot
        return snapshot

    def snapshot(self, thread_id: str) -> ThreadSnapshot:
        assert self.created is not None and self.created.thread_id == thread_id
        return self.created

    def read_events(self, thread_id: str, after_event_seq: int) -> EventPage:
        raise AssertionError("not used by creation route")

    def submit_command(self, command: dict[str, object]) -> CommandReceipt:
        raise AssertionError("not used by creation route")


class _Ledger:
    def ping(self) -> bool:
        return True


def test_thread_creator_defaults_to_registered_ieee39_and_pins_revision() -> None:
    service = _Service()
    snapshot = ThreadCreator(service, _Catalog()).create()

    assert snapshot.active_model_context.model_id == "ieee39"
    assert snapshot.active_model_context.model_revision == "revision:sha256:" + "a" * 64
    assert snapshot.active_grid_page_id == "page_ieee39"
    assert service.created == snapshot


def test_thread_creator_derives_a_safe_page_id_for_hierarchical_model() -> None:
    service = _Service()

    class Catalog(_Catalog):
        default_model_id = "pypsa-example/scigrid_de"

        def resolve(self, model_id: str | None) -> ThreadModelDescriptor:
            assert model_id == self.default_model_id
            return ThreadModelDescriptor(
                self.default_model_id, "revision:sha256:" + "b" * 64, "pypsa",
            )

    snapshot = ThreadCreator(service, Catalog()).create()
    assert snapshot.active_grid_page_id == "page_pypsa-example__scigrid_de"


def test_thread_creator_persists_selected_profile_references_in_model_context() -> None:
    service = _Service()
    registry = ModelCapabilityRegistry()
    capabilities = CapstoneModelCapabilityCatalog(registry)
    descriptor = ModelCapabilityDescriptor("static-analysis", "1.0.0")
    capabilities.register_profile(
        ModelCapabilityProfileInfo(descriptor, "Static", ("pandapower",)),
        lambda: _Handle(descriptor),
    )
    capabilities.set_family_default("pandapower", ModelCapabilitySelection((descriptor.reference,)))

    snapshot = ThreadCreator(service, _Catalog(), capabilities).create()

    assert snapshot.active_model_context.enabled_profiles == (descriptor.reference,)


def test_thread_creator_does_not_treat_an_explicit_empty_model_id_as_default() -> None:
    service = _Service()

    class Catalog(_Catalog):
        def resolve(self, model_id: str | None) -> ThreadModelDescriptor:
            assert model_id == ""
            raise ValueError("model is not registered")

    try:
        ThreadCreator(service, Catalog()).create("")
    except ValueError as error:
        assert str(error) == "model is not registered"
    else:
        raise AssertionError("explicit empty model_id must not select the default")


def test_thread_creation_route_returns_pinned_snapshot() -> None:
    service = _Service()
    app = create_host_app(
        _Ledger(), WorkerRegistry(()), operator_token="hosted-secret",
        allowed_hosts={"localhost"}, allowed_origins={"http://localhost:5173"},
        thread_service=service, thread_creator=ThreadCreator(service, _Catalog()),
    )
    with TestClient(app, base_url="http://localhost") as client:
        response = client.post(
            "/api/v1/threads", headers={"Authorization": "Bearer hosted-secret"}, json={},
        )

    assert response.status_code == 201
    document = response.json()
    assert document["schema"] == "capstone-thread-snapshot/1"
    assert document["active_model_context"]["model_id"] == "ieee39"


def test_public_demo_cannot_create_or_read_private_threads() -> None:
    service = _Service()
    app = create_host_app(
        _Ledger(), WorkerRegistry(()), operator_token="hosted-secret", public_demo=True,
        public_provider="deepseek", public_model="deepseek-flash",
        allowed_hosts={"localhost"}, allowed_origins={"http://localhost:5173"},
        thread_service=service, thread_creator=ThreadCreator(service, _Catalog()),
    )
    with TestClient(app, base_url="http://localhost") as client:
        token = client.get("/api/v1/demo-credential").json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        assert client.post("/api/v1/threads", headers=headers, json={}).status_code == 404
        assert client.get("/api/v1/threads/thr_demo_39", headers=headers).status_code == 404
