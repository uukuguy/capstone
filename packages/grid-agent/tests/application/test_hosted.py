from grid_agent.hosted import RegisteredPandapowerThreadCatalog


def test_hosted_catalog_resolves_registered_ieee39_revision() -> None:
    descriptor = RegisteredPandapowerThreadCatalog().resolve(None)

    assert descriptor.model_id == "ieee39"
    assert descriptor.implementation_family == "pandapower"
    assert descriptor.model_revision.startswith("revision:sha256:")

