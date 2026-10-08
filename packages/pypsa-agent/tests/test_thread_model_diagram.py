import pytest

from pypsa_agent.hosted import RegisteredPyPSAThreadCatalog
from pypsa_agent.thread_model_diagram import model_diagram
from capstone_agent.network_diagram import normalize_network_diagram


def test_registered_model_can_be_browsed_without_calculation_profiles():
    model = RegisteredPyPSAThreadCatalog().resolve("regional-six-bus")
    diagram = normalize_network_diagram(model_diagram(model.model_id, model.model_revision))
    assert diagram["model"]["revision"] == model.model_revision
    assert len(diagram["buses"]) == 6


def test_model_browsing_rejects_a_different_exact_revision():
    with pytest.raises(ValueError, match="revision"):
        model_diagram("regional-six-bus", "revision:sha256:" + "f" * 64)
