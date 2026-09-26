"""Operator-only diagrams preserve complete registered topology."""

from __future__ import annotations

import hashlib

import pandas as pd
import pypsa

from pypsa_model_authority import model_library
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
