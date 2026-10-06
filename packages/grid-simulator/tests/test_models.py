from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock

import pytest

from grid_simulator.engine import Pandapower340Engine
from grid_simulator.models import ContextStore, ModelNotFoundError, ModelRegistry
from grid_simulator.workspace import SimulatorWorkspace


def test_catalog_checks_operator_capacity_before_offering_a_model() -> None:
    class Engine:
        def open_registered(self, _factory):
            return SimpleNamespace(bus=range(10001), line=(), trafo=(), trafo3w=())

        def serialize(self, _net):
            return '{"fixture":"oversized"}'

    assert ModelRegistry(Engine()).operator_diagram_unavailable_reason("case9") == "diagram_limit"


def test_concurrent_revision_reads_cannot_observe_incomplete_diagram_eligibility(monkeypatch) -> None:
    from grid_simulator import models
    entered, release, lock = Event(), Event(), Lock()
    calls = 0
    geometry = models.operator_geometry

    def blocked(net):
        nonlocal calls
        with lock:
            calls += 1
            first = calls == 1
        if first:
            entered.set()
            assert release.wait(timeout=10)
        return geometry(net)

    monkeypatch.setattr(models, "operator_geometry", blocked)
    registry = ModelRegistry(Pandapower340Engine())
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(registry.operator_diagram_unavailable_reason, "case9")
        assert entered.wait(timeout=10)
        try:
            assert registry.operator_diagram_unavailable_reason("case9") is None
        finally:
            release.set()
        assert first.result(timeout=10) is None


def test_registry_lists_ieee39_with_domain_aliases() -> None:
    model = ModelRegistry(Pandapower340Engine()).list()[0]

    assert model.model_id == "ieee39"
    assert "IEEE-39节点系统" in model.aliases
    assert model.source == "pandapower.networks.case39"
    assert model.engine == "pandapower"
    assert model.engine_version == "3.4.0"


def test_registry_lists_the_versioned_pandapower_network_catalog() -> None:
    models = ModelRegistry(Pandapower340Engine()).list()
    by_id = {model.model_id: model for model in models}

    assert len(models) >= 50
    assert {"ieee39", "case9", "case14", "create_cigre_network_mv"} <= set(by_id)
    assert by_id["case9"].source == "pandapower.networks.case9"
    assert by_id["create_cigre_network_mv"].source == "pandapower.networks.create_cigre_network_mv"
    assert len({model.source for model in models}) == len(models)


@pytest.mark.parametrize(
    ("model_id", "expected_buses"),
    [("case9", 9), ("case14", 14), ("ieee39", 39)],
)
def test_registry_opens_multiple_allowlisted_networks(model_id: str, expected_buses: int) -> None:
    model, net = ModelRegistry(Pandapower340Engine()).open(model_id)

    assert model.model_id == model_id
    assert len(net.bus) == expected_buses


def test_registry_opens_specialized_packaged_network() -> None:
    model, net = ModelRegistry(Pandapower340Engine()).open("create_cigre_network_mv")

    assert model.source == "pandapower.networks.create_cigre_network_mv"
    assert len(net.bus) > 0
    assert len(net.line) > 0


def test_open_context_persists_immutable_revision(tmp_path: Path) -> None:
    workspace = SimulatorWorkspace(tmp_path)
    context = ContextStore(workspace, ModelRegistry(Pandapower340Engine())).create("ieee39")
    loaded = ContextStore(workspace, ModelRegistry(Pandapower340Engine())).require(context.context_ref)

    assert loaded == context
    assert context.revision_ref.startswith("revision:sha256:")
    assert workspace.model_artifact(context.revision_ref).is_file()


def test_context_revision_matches_registry_trusted_revision(tmp_path: Path) -> None:
    engine = Pandapower340Engine()
    registry = ModelRegistry(engine)
    context = ContextStore(SimulatorWorkspace(tmp_path), registry).create("ieee39")

    assert context.revision_ref == registry.trusted_revision_ref("ieee39")


def test_reopening_registered_model_keeps_same_context_and_revision(tmp_path: Path) -> None:
    store = ContextStore(SimulatorWorkspace(tmp_path), ModelRegistry(Pandapower340Engine()))

    first = store.create("ieee39")
    second = store.create("ieee39")

    assert second == first


def test_registry_rejects_arbitrary_model_ids_without_callable_resolution() -> None:
    registry = ModelRegistry(Pandapower340Engine())

    with pytest.raises(ModelNotFoundError):
        registry.open("pandapower.networks.case118")

    with pytest.raises(ModelNotFoundError):
        registry.open("pp_elements")


def test_operator_diagram_uses_complete_ieee39_schematic_from_gridctl(grid, context_ref) -> None:
    diagram = grid.call("operator.diagram.get", {"context_ref": context_ref})
    described = grid.call("environment.describe", {})

    assert len(diagram["buses"]) == 39
    assert len(diagram["branches"]) == 35 + 11
    assert diagram["coordinate_system"] == "schematic"
    assert all(bus["x"] is not None and bus["y"] is not None for bus in diagram["buses"])
    assert {branch["kind"] for branch in diagram["branches"]} == {"line", "trafo"}
    assert "operator.diagram.get" not in {
        item["id"] for item in described["executable_capabilities"]
    }
    assert "operator.diagram.get" not in {
        contract.id for contract in grid.services.capability_registry.list()
    }


@pytest.mark.parametrize("model_id", ["ieee39", "case14", "case9"])
def test_operator_labels_match_model_tool_names(grid, model_id) -> None:
    from grid_simulator.queries import list_branch_records, list_bus_records

    context = grid.call("context.open", {"model_id": model_id})
    diagram = grid.call("operator.diagram.get", {"context_ref": context["context_ref"]})
    _, net = ModelRegistry(Pandapower340Engine()).open(model_id)
    revision = context["revision_ref"]

    assert {bus["id"]: bus["label"] for bus in diagram["buses"]} == {
        str(bus.index): bus.name for bus in list_bus_records(net, revision)
    }
    assert {branch["id"]: branch["label"] for branch in diagram["branches"]} == {
        f"{branch.kind}:{branch.index}": branch.name
        for branch in list_branch_records(net, revision)
    }
    # Labels use model names; endpoint IDs keep the authority's original index.
    assert diagram["buses"][0]["id"] == "0"
    assert diagram["buses"][0]["label"] == "1"


@pytest.mark.parametrize("name", [0, 13, "Substation A", None, float("nan"), ""])
def test_operator_labels_preserve_scalar_names_and_tool_fallbacks(name) -> None:
    from grid_simulator.operator_diagram import operator_geometry
    from grid_simulator.queries import list_branch_records, list_bus_records

    net = Pandapower340Engine().open_registered("case39")
    for table in (net.bus, net.line, net.trafo):
        table["name"] = table["name"].astype(object)
    net.bus.at[10, "name"] = name
    net.line.at[11, "name"] = name
    net.trafo.at[0, "name"] = name
    diagram = operator_geometry(net)
    revision = "revision:sha256:" + "0" * 64
    bus_names = {str(bus.index): bus.name for bus in list_bus_records(net, revision)}
    branch_names = {
        f"{branch.kind}:{branch.index}": branch.name
        for branch in list_branch_records(net, revision)
    }

    assert all(bus["label"] == bus_names[bus["id"]] for bus in diagram["buses"])
    assert all(branch["label"] == branch_names[branch["id"]] for branch in diagram["branches"])
    assert all(bus["label"] for bus in diagram["buses"])
    assert all(branch["label"] for branch in diagram["branches"])


def test_three_winding_transformer_legs_share_the_model_tool_name() -> None:
    import pandas as pd
    from grid_simulator.operator_diagram import operator_geometry
    from grid_simulator.queries import list_branch_records

    net = SimpleNamespace(
        bus=pd.DataFrame({"name": [11, 13, 30], "vn_kv": [110, 20, 10]}, index=[2, 7, 9]),
        line=pd.DataFrame(), trafo=pd.DataFrame(),
        trafo3w=pd.DataFrame({"name": [15], "hv_bus": [2], "mv_bus": [7], "lv_bus": [9]}, index=[4]),
    )
    diagram = operator_geometry(net)
    branch = list_branch_records(net, "revision:sha256:" + "0" * 64)[0]
    assert {leg["id"] for leg in diagram["branches"]} == {"trafo3w:4:mv", "trafo3w:4:lv"}
    assert all(leg["label"] == branch.name for leg in diagram["branches"])


@pytest.mark.parametrize("model_id", ["GBnetwork", "case9241pegase"])
def test_operator_diagram_keeps_large_registered_network_complete(grid, model_id) -> None:
    context = grid.call("context.open", {"model_id": model_id})
    diagram = grid.call("operator.diagram.get", {"context_ref": context["context_ref"]})
    _, net = ModelRegistry(Pandapower340Engine()).open(model_id)
    assert len(diagram["buses"]) == len(net.bus) > 2000
    assert len(diagram["branches"]) == len(net.line) + len(net.trafo) + 2 * len(net.trafo3w)
    assert {bus["id"] for bus in diagram["buses"]} == {str(index) for index in net.bus.index}
    assert diagram["revision_ref"] == context["revision_ref"]
