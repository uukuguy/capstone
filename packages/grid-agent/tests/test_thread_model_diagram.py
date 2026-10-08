import pytest

from capstone_agent.network_diagram import normalize_network_diagram
from grid_agent.thread_model_diagram import model_diagram
from grid_agent.hosted import RegisteredPandapowerThreadCatalog


def test_model_browsing_uses_registered_authority_without_provider_credentials():
    model = RegisteredPandapowerThreadCatalog().resolve("ieee39")
    diagram = normalize_network_diagram(model_diagram(model.model_id, model.model_revision))
    assert diagram["model"]["id"] == "ieee39"
    assert diagram["model"]["revision"] == model.model_revision
    assert len(diagram["buses"]) == 39


def test_browsing_does_not_substitute_an_unavailable_historical_revision():
    with pytest.raises(ValueError, match="revision"):
        model_diagram("ieee39", "unavailable")
