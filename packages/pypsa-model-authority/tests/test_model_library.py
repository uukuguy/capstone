"""Pinned official example assets are discoverable and installed only after verification."""

from __future__ import annotations

import hashlib
import io

import pandas as pd
import pypsa
import pytest

from pypsa_model_authority import model_library
from pypsa_model_authority.catalog import list_registered_models
from pypsa_model_authority.operations import execute
from pypsa_model_authority.power_operations import execute_operation
from pypsa_model_authority.store import ModelStore, ModelStoreError


def test_official_examples_cover_pinned_pypsa_network_api() -> None:
    entries = model_library.list_official_examples()
    assert {entry.catalog_id for entry in entries} == {
        "pypsa-example/ac_dc_meshed", "pypsa-example/storage_hvdc",
        "pypsa-example/scigrid_de", "pypsa-example/model_energy",
        "pypsa-example/stochastic_network", "pypsa-example/carbon_management",
    }
    assert all(entry.source_url.startswith("https://data.pypsa.org/networks/examples/v1.3.0/") for entry in entries)
    assert all(len(entry.sha256) == 64 and entry.size_bytes > 0 for entry in entries)
    catalog = list_registered_models()
    assert len(catalog) == 21
    assert len({item["catalog_id"] for item in catalog}) == 21
    assert all(item["source_kind"] == "official-pypsa-netcdf" for item in catalog[-6:])
    with pytest.raises(model_library.ModelLibraryError, match="not registered"):
        model_library.get_official_example("pypsa-example/unknown")


def test_installer_rejects_bad_bytes_and_symlink_without_publishing(tmp_path, monkeypatch) -> None:
    payload = b"sample-network"
    entry = model_library.OfficialModel(
        "pypsa-example/sample", "Sample", "sample",
        "https://data.pypsa.org/networks/examples/v1.3.0/sample.nc",
        len(payload), hashlib.sha256(payload).hexdigest(), "sample",
    )
    monkeypatch.setattr(model_library, "get_official_example", lambda _: entry)
    monkeypatch.setattr(model_library, "urlopen", lambda _: io.BytesIO(b"wrong-network"))
    with pytest.raises(model_library.ModelLibraryError, match="digest|size"):
        model_library.install_official_example(entry.catalog_id, root=tmp_path)
    assert not model_library.asset_path(entry, root=tmp_path).exists()

    target = tmp_path / "outside.nc"
    target.write_bytes(payload)
    model_library.asset_path(entry, root=tmp_path).symlink_to(target)
    monkeypatch.setattr(model_library, "urlopen", lambda _: io.BytesIO(payload))
    with pytest.raises(model_library.ModelLibraryError, match="unsafe"):
        model_library.install_official_example(entry.catalog_id, root=tmp_path)
    assert target.read_bytes() == payload
    model_library.asset_path(entry, root=tmp_path).unlink()
    installed = model_library.install_official_example(entry.catalog_id, root=tmp_path)
    assert installed.read_bytes() == payload
    assert model_library.verified_asset_path(entry.catalog_id, root=tmp_path) == installed


def test_official_network_opens_as_current_run_revision_and_rechecks_asset(tmp_path, monkeypatch) -> None:
    library = tmp_path / "library"
    library.mkdir()
    network = pypsa.Network()
    network.set_snapshots(pd.date_range("2026-01-01", periods=2, freq="h"))
    network.add("Bus", "service-area")
    network.add("Load", "demand", bus="service-area", p_set=10.0)
    network.add("Generator", "supply", bus="service-area", p_nom=20.0, marginal_cost=5.0)
    asset = library / "sample.nc"
    network.export_to_netcdf(asset)
    original = asset.read_bytes()
    entry = model_library.OfficialModel(
        "pypsa-example/sample", "Sample", "sample",
        "https://data.pypsa.org/networks/examples/v1.3.0/sample.nc",
        len(original), hashlib.sha256(original).hexdigest(), "service area",
    )
    monkeypatch.setattr(model_library, "get_official_example", lambda _: entry)
    monkeypatch.setenv("CAPSTONE_PYPSA_MODEL_LIBRARY_DIR", str(library))
    workspace = tmp_path / "runs" / "example-run" / "domains" / "model"
    opened = execute("model.open", {"catalog_id": entry.catalog_id}, workspace, run_id="example-run")
    inspected = execute("model.inspect", {"model_ref": opened["model_ref"]}, workspace, run_id="example-run")
    validated = execute("model.validate", {"model_ref": opened["model_ref"]}, workspace, run_id="example-run")
    assert inspected["component_counts"]["Bus"] == 1
    assert inspected["snapshot_count"] == 2
    assert validated["valid"] is True
    assert validated["checked_rules"] == ["unknown_buses", "time_series", "shapes"]
    assert ModelStore(workspace, run_id="example-run").load_model(opened["model_ref"])["source_sha256"] == entry.sha256
    with pytest.raises(ModelStoreError, match="current run|unavailable"):
        ModelStore(tmp_path / "runs" / "other-run" / "domains" / "model", run_id="other-run").load_model(opened["model_ref"])
    asset.write_bytes(original + b"tampered")
    with pytest.raises(ModelStoreError, match="asset|digest"):
        ModelStore(workspace, run_id="example-run").load_network(opened["model_ref"])


def test_topology_result_is_bounded_and_backed_by_current_run(tmp_path) -> None:
    workspace = tmp_path / "runs" / "topology-run" / "domains" / "model"
    opened = execute("model.open", {"catalog_id": "two-bus"}, workspace, run_id="topology-run")
    topology = execute("model.topology", {"model_ref": opened["model_ref"]}, workspace, run_id="topology-run")
    assert topology["buses"][0]["id"] == "north"
    assert topology["lines"][0]["from_bus"] == "north"
    assert topology["lines"][0]["to_bus"] == "south"
    assert topology["coordinate_status"] == "schematic-required"
    assert topology["omitted_counts"] == {"buses": 0, "lines": 0, "links": 0, "transformers": 0}
    assert ModelStore(workspace, run_id="topology-run").load(topology["result_ref"], "result")["model_ref"] == opened["model_ref"]


def test_large_dispatch_returns_carrier_and_line_summary_instead_of_generator_table(tmp_path, monkeypatch) -> None:
    library = tmp_path / "library"
    library.mkdir()
    network = pypsa.Network()
    network.set_snapshots(pd.date_range("2026-01-01", periods=1, freq="h"))
    network.add("Carrier", "thermal")
    network.add("Bus", "area")
    network.add("Load", "demand", bus="area", p_set=40.0)
    for index in range(60):
        network.add("Generator", f"unit-{index}", bus="area", carrier="thermal", p_nom=1.0, marginal_cost=float(index + 1))
    asset = library / "sample.nc"
    network.export_to_netcdf(asset)
    payload = asset.read_bytes()
    entry = model_library.OfficialModel(
        "pypsa-example/sample", "Sample", "sample",
        "https://data.pypsa.org/networks/examples/v1.3.0/sample.nc",
        len(payload), hashlib.sha256(payload).hexdigest(), "dispatch",
    )
    monkeypatch.setattr(model_library, "get_official_example", lambda _: entry)
    monkeypatch.setenv("CAPSTONE_PYPSA_MODEL_LIBRARY_DIR", str(library))
    source = tmp_path / "runs" / "dispatch-run" / "domains" / "model"
    target = source.parent / "operations"
    opened = execute("model.open", {"catalog_id": entry.catalog_id}, source, run_id="dispatch-run")
    result = execute_operation("operations.dispatch", {"model_ref": opened["model_ref"]}, target, source, run_id="dispatch-run")
    assert result["condition"] == "optimal"
    assert "generator_dispatch_mw" not in result
    assert result["generation_by_carrier_mw"]["thermal"] == pytest.approx([40.0])
    assert result["generator_count"] == 60
    assert ModelStore(target, run_id="dispatch-run").load(result["result_ref"], "result")["details"]["generator_count"] == 60
