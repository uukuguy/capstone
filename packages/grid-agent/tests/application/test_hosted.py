from grid_agent.hosted import RegisteredPandapowerThreadCatalog
from grid_agent import hosted


def test_hosted_catalog_resolves_registered_ieee39_revision() -> None:
    descriptor = RegisteredPandapowerThreadCatalog().resolve(None)

    assert descriptor.model_id == "ieee39"
    assert descriptor.implementation_family == "pandapower"
    assert descriptor.model_revision.startswith("revision:sha256:")


def test_grid_hosted_entry_point_delegates_factory_to_capstone_host(monkeypatch) -> None:
    assembly = object()
    seen = []

    monkeypatch.setattr(hosted, "build_registered_pandapower_thread_application", lambda: assembly)
    monkeypatch.setattr(
        hosted,
        "run_hosted_api",
        lambda factory: seen.append(factory) or 31,
    )

    assert hosted.main() == 31
    assert seen == [hosted.build_registered_pandapower_thread_application]
