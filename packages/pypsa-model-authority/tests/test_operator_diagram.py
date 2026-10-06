"""Operator-only diagrams preserve complete registered topology."""

from __future__ import annotations

import hashlib

import pandas as pd
import pypsa
import pytest

from pypsa_model_authority import model_library
from pypsa_model_authority.catalog import PROJECT_MODEL_IDS
from pypsa_model_authority.operations import execute


def test_operator_diagram_keeps_connected_model_beyond_model_tool_limit(tmp_path, monkeypatch) -> None:
    network = pypsa.Network()
    network.set_snapshots(pd.date_range("2026-01-01", periods=1, freq="h"))
    for index in range(55):
        network.add("Bus", f"bus-{index}", x=6.0 + index * 0.01,
                    y=50.0 + index * 0.01, v_nom=220.0)
    for index in range(54):
        network.add("Line", f"line-{index}", bus0=f"bus-{index}",
                    bus1=f"bus-{index + 1}", x=0.1, r=0.01, s_nom=100.0)
    library = tmp_path / "library"
    library.mkdir()
    asset = library / "complete.nc"
    network.export_to_netcdf(asset)
    payload = asset.read_bytes()
    entry = model_library.OfficialModel(
        "pypsa-example/complete", "Complete", "complete",
        "https://data.pypsa.org/networks/examples/v1.3.0/complete.nc",
        len(payload), hashlib.sha256(payload).hexdigest(), "operator diagram",
    )
    monkeypatch.setattr(model_library, "get_official_example", lambda _: entry)
    monkeypatch.setenv("CAPSTONE_PYPSA_MODEL_LIBRARY_DIR", str(library))
    workspace = tmp_path / "runs" / "diagram-run" / "domains" / "model"
    opened = execute("model.open", {"catalog_id": entry.catalog_id}, workspace,
                     run_id="diagram-run")
    model_tool = execute("model.topology", {"model_ref": opened["model_ref"]}, workspace,
                         run_id="diagram-run")
    diagram = execute("operator.diagram", {"model_ref": opened["model_ref"]}, workspace,
                      run_id="diagram-run")
    described = execute("environment.describe", {}, workspace, run_id="diagram-run")

    assert len(model_tool["buses"]) == 50
    assert len(diagram["buses"]) == 55
    assert len(diagram["branches"]) == 54
    assert diagram["coordinate_system"] == "geographic"
    assert diagram["buses"][-1]["vn_kv"] == 220.0
    assert any(branch["to_bus"] == "bus-54" for branch in diagram["branches"])
    assert "operator.diagram" not in {item["id"] for item in described["executable_capabilities"]}


@pytest.mark.parametrize("catalog_id", PROJECT_MODEL_IDS)
def test_registered_diagram_labels_match_model_topology_names(tmp_path, catalog_id) -> None:
    opened = execute("model.open", {"catalog_id": catalog_id}, tmp_path, run_id="names")
    arguments = {"model_ref": opened["model_ref"]}
    topology = execute("model.topology", arguments, tmp_path, run_id="names")
    diagram = execute("operator.diagram", arguments, tmp_path, run_id="names")

    assert {bus["id"]: bus["label"] for bus in diagram["buses"]} == {
        bus["id"]: bus["id"] for bus in topology["buses"]
    }
    assert {branch["id"]: branch["label"] for branch in diagram["branches"]} == {
        f"{kind}:{branch['id']}": branch["id"]
        for kind, table in (("line", "lines"), ("link", "links"), ("transformer", "transformers"))
        for branch in topology[table]
    }


def test_official_diagram_preserves_numeric_and_named_components(tmp_path, monkeypatch) -> None:
    network = pypsa.Network()
    for name in ("11", "13", "Central AC", "Hydrogen"):
        network.add("Bus", name, v_nom=220.0)
    network.add("Line", "0", bus0="11", bus1="13", x=0.1, r=0.01, s_nom=100.0)
    network.add("Transformer", "T13-central", bus0="13", bus1="Central AC",
                x=0.1, r=0.01, s_nom=100.0)
    network.add("Link", "electrolyser-0", bus0="Central AC", bus1="Hydrogen", p_nom=10.0)
    asset = tmp_path / "names.nc"
    network.export_to_netcdf(asset)
    payload = asset.read_bytes()
    entry = model_library.OfficialModel(
        "pypsa-example/names", "Names", "names",
        "https://data.pypsa.org/networks/examples/v1.3.0/names.nc",
        len(payload), hashlib.sha256(payload).hexdigest(), "component names",
    )
    monkeypatch.setattr(model_library, "get_official_example", lambda _: entry)
    monkeypatch.setenv("CAPSTONE_PYPSA_MODEL_LIBRARY_DIR", str(tmp_path))
    workspace = tmp_path / "authority"
    opened = execute("model.open", {"catalog_id": entry.catalog_id}, workspace, run_id="names")
    arguments = {"model_ref": opened["model_ref"]}
    topology = execute("model.topology", arguments, workspace, run_id="names")
    diagram = execute("operator.diagram", arguments, workspace, run_id="names")

    assert {bus["id"]: bus["label"] for bus in diagram["buses"]} == {
        bus["id"]: bus["id"] for bus in topology["buses"]
    }
    assert {branch["id"]: branch["label"] for branch in diagram["branches"]} == {
        "line:0": "0", "transformer:T13-central": "T13-central",
        "link:electrolyser-0": "electrolyser-0",
    }
