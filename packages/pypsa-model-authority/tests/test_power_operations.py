"""Real fixed-model operations keep source revisions and target evidence separate."""

from __future__ import annotations

import hashlib
import json

import pytest

from pypsa_model_authority.operations import execute
from pypsa_model_authority.power_operations import OperationError, execute_operation
from pypsa_model_authority.references import verify_model
from pypsa_model_authority.store import ModelStore


def test_registered_dispatch_commitment_security_and_ac_validation(tmp_path) -> None:
    source = tmp_path / "runs" / "ops-run" / "domains" / "model"
    target = source.parent / "operations"
    refs = {}
    for catalog_id in ("two-bus", "unit-commitment", "security-triangle"):
        refs[catalog_id] = execute(
            "model.open", {"catalog_id": catalog_id}, source, run_id="ops-run"
        )["model_ref"]

    dispatch = execute_operation(
        "operations.dispatch", {"model_ref": refs["two-bus"]},
        target, source, run_id="ops-run",
    )
    assert dispatch["status"] == "ok"
    assert dispatch["condition"] == "optimal"
    assert dispatch["objective_kind"] == "operating_cost"
    assert dispatch["objective"] == pytest.approx(800.0)
    assert dispatch["generator_dispatch_mw"] == {"supply": [40.0]}

    ac = execute_operation(
        "operations.ac_validate", {
            "model_ref": refs["two-bus"], "dispatch_result_ref": dispatch["result_ref"],
        }, target, source, run_id="ops-run",
    )
    assert ac["converged"] is True
    assert ac["dispatch_result_ref"] == dispatch["result_ref"]
    assert ac["bus_voltage_pu"]["south"][0] == pytest.approx(1.0, abs=0.01)

    commitment = execute_operation(
        "operations.commitment", {"model_ref": refs["unit-commitment"]},
        target, source, run_id="ops-run",
    )
    assert commitment["condition"] == "optimal"
    assert commitment["commitment_status"]["cheap"] == [1, 1]
    assert commitment["generator_dispatch_mw"]["expensive"] == pytest.approx([0, 10])

    security = execute_operation(
        "operations.security_dispatch", {
            "model_ref": refs["security-triangle"], "outage_set_id": "triangle-l3",
        }, target, source, run_id="ops-run",
    )
    assert security["condition"] == "optimal"
    assert security["outage_set_id"] == "triangle-l3"
    assert security["generator_dispatch_mw"]["southgen"][0] == pytest.approx(10.0)

    store = ModelStore(target, run_id="ops-run")
    for result in (dispatch, ac, commitment, security):
        assert store.load(result["result_ref"], "result")["model_ref"] == result["model_ref"]
        assert store.load(result["evidence_refs"][0], "evidence")["result_ref"] == result["result_ref"]
    assert verify_model(source, "ops-run", refs["two-bus"]).document["parent_ref"] is None


def test_invalid_source_and_infeasible_solve_never_publish_success(tmp_path) -> None:
    source = tmp_path / "runs" / "ops-run" / "domains" / "model"
    target = source.parent / "operations"
    opened = execute("model.open", {"catalog_id": "two-bus"}, source, run_id="ops-run")

    with pytest.raises(OperationError, match="current run|unavailable"):
        execute_operation(
            "operations.dispatch", {"model_ref": opened["model_ref"]},
            tmp_path / "runs" / "other" / "domains" / "operations",
            tmp_path / "runs" / "other" / "domains" / "model", run_id="other",
        )
    with pytest.raises(OperationError, match="outage set"):
        execute_operation(
            "operations.security_dispatch", {
                "model_ref": opened["model_ref"], "outage_set_id": "unregistered",
            }, target, source, run_id="ops-run",
        )
    overloaded = execute("model.derive", {
        "model_ref": opened["model_ref"], "load_id": "demand", "p_set_mw": 200.0,
    }, source, run_id="ops-run")
    with pytest.raises(OperationError, match="warning/infeasible"):
        execute_operation(
            "operations.dispatch", {"model_ref": overloaded["model_ref"]},
            target, source, run_id="ops-run",
        )
    assert not (target / "results").exists()


def test_registered_rolling_horizon_preserves_storage_dispatch(tmp_path) -> None:
    source = tmp_path / "runs" / "rolling-run" / "domains" / "model"
    target = source.parent / "operations"
    opened = execute("model.open", {"catalog_id": "rolling-storage"}, source, run_id="rolling-run")
    result = execute_operation(
        "operations.rolling_dispatch", {"model_ref": opened["model_ref"]},
        target, source, run_id="rolling-run",
    )
    assert result["condition"] == "optimal"
    assert result["horizon_snapshots"] == 2
    assert result["generator_dispatch_mw"]["cheap"] == pytest.approx([40.0, 0.0, 0.0])
    assert result["generator_dispatch_mw"]["backup"] == pytest.approx([0.0, 0.0, 20.0])
    assert result["store_energy_mwh"]["battery"] == pytest.approx([20.0, 0.0, 0.0])
    assert result["objective"] == pytest.approx(1000.0)
    assert ModelStore(target, run_id="rolling-run").load(result["evidence_refs"][0], "evidence")["result_ref"] == result["result_ref"]


def test_congested_opf_exposes_line_flow_and_nodal_prices(tmp_path) -> None:
    source = tmp_path / "runs" / "congestion-run" / "domains" / "model"
    target = source.parent / "operations"
    opened = execute("model.open", {"catalog_id": "congested-two-bus"}, source, run_id="congestion-run")
    result = execute_operation(
        "operations.congested_opf", {"model_ref": opened["model_ref"]},
        target, source, run_id="congestion-run",
    )
    assert result["condition"] == "optimal"
    assert result["generator_dispatch_mw"] == {"cheap": [20.0], "local": [20.0]}
    assert result["line_flow_mw"]["corridor"] == pytest.approx([20.0])
    assert result["bus_marginal_price"]["north"] == pytest.approx([10.0])
    assert result["bus_marginal_price"]["south"] == pytest.approx([30.0])
    assert result["objective"] == pytest.approx(800.0)
    assert ModelStore(target, run_id="congestion-run").load(result["evidence_refs"][0], "evidence")["result_ref"] == result["result_ref"]


def test_registered_regional_network_dispatches_across_three_snapshots(tmp_path) -> None:
    source = tmp_path / "runs" / "regional-run" / "domains" / "model"
    target = source.parent / "operations"
    opened = execute("model.open", {"catalog_id": "regional-six-bus"}, source, run_id="regional-run")
    inspected = execute("model.inspect", {"model_ref": opened["model_ref"]}, source, run_id="regional-run")
    assert inspected["component_counts"] == {"Bus": 6, "Load": 3, "Generator": 3, "Line": 7}
    result = execute_operation(
        "operations.dispatch", {"model_ref": opened["model_ref"]},
        target, source, run_id="regional-run",
    )
    assert result["condition"] == "optimal"
    assert [sum(values[index] for values in result["generator_dispatch_mw"].values()) for index in range(3)] == pytest.approx([40.0, 50.0, 55.0])
    assert result["top_line_loading"]
    assert all(item["max_loading_pct"] >= 0 for item in result["top_line_loading"])
    assert result["omitted_line_count"] == 0
    assert result["objective"] > 0
    assert ModelStore(target, run_id="regional-run").load(result["evidence_refs"][0], "evidence")["result_ref"] == result["result_ref"]


def test_regional_ac_validation_uses_saved_dispatch_in_each_snapshot(tmp_path, monkeypatch) -> None:
    import pypsa

    source = tmp_path / "runs" / "regional-ac-run" / "domains" / "model"
    target = source.parent / "operations"
    run_id = "regional-ac-run"
    base = execute("model.open", {"catalog_id": "regional-six-bus"}, source, run_id=run_id)
    growth = execute("model.derive_series", {
        "model_ref": base["model_ref"], "load_id": "central-demand",
        "p_set_mw": [30.0, 35.0, 40.0],
    }, source, run_id=run_id)
    solved = []
    original_pf = pypsa.Network.pf

    def observe_actual_ac(network, *args, **kwargs):
        report = original_pf(network, *args, **kwargs)
        solved.append({
            "generation": network.generators_t.p.copy(),
            "slack": network.generators.index[network.generators.control == "Slack"].tolist(),
            "losses": (network.lines_t.p0 + network.lines_t.p1).sum(axis=1).tolist(),
        })
        return report

    monkeypatch.setattr(pypsa.Network, "pf", observe_actual_ac)
    dispatches = []
    for model in (base, growth):
        dispatch = execute_operation("operations.dispatch", {"model_ref": model["model_ref"]},
                                     target, source, run_id=run_id)
        dispatches.append(dispatch)
        ac = execute_operation("operations.ac_validate", {
            "model_ref": model["model_ref"], "dispatch_result_ref": dispatch["result_ref"],
        }, target, source, run_id=run_id)
        assert ac["condition"] == "converged"
        assert ac["dispatch_result_ref"] == dispatch["result_ref"]

    for dispatch, actual in zip(dispatches, solved, strict=True):
        # Verify real PF output, not the adapter's assignment. Only slack may
        # change active generation to balance nonlinear transmission losses.
        schedule = dispatch["generator_dispatch_mw"]
        assert actual["slack"] == ["northwest-supply"]
        for name, values in schedule.items():
            expected = ([value + loss for value, loss in zip(values, actual["losses"], strict=True)]
                        if name in actual["slack"] else values)
            assert actual["generation"][name].tolist() == pytest.approx(expected, abs=1e-6)
    south_delta = solved[1]["generation"]["southern-backup"] - solved[0]["generation"]["southern-backup"]
    assert south_delta.tolist() == pytest.approx([0.0, 0.0, 10.0])
    store = ModelStore(source, run_id=run_id)
    assert store.load_model(growth["model_ref"])["parent_ref"] == base["model_ref"]
    assert store.load_network(base["model_ref"]).loads_t.p_set["central-demand"].tolist() == [20.0, 25.0, 30.0]


@pytest.mark.parametrize("defect", ["other_revision", "tampered_result"])
def test_ac_validation_rejects_unbound_or_changed_dispatch(tmp_path, monkeypatch, defect) -> None:
    import pypsa

    source = tmp_path / "runs" / "ac-invalid-run" / "domains" / "model"
    target = source.parent / "operations"
    run_id = "ac-invalid-run"
    opened = execute("model.open", {"catalog_id": "two-bus"}, source, run_id=run_id)
    dispatch = execute_operation("operations.dispatch", {"model_ref": opened["model_ref"]},
                                 target, source, run_id=run_id)
    model_ref = opened["model_ref"]
    if defect == "other_revision":
        model_ref = execute("model.derive", {
            "model_ref": model_ref, "load_id": "demand", "p_set_mw": 41.0,
        }, source, run_id=run_id)["model_ref"]
    else:
        path = ModelStore(target, run_id=run_id).artifact_path(dispatch["result_ref"], "result")
        document = json.loads(path.read_text())
        document["details"]["generator_dispatch_mw"]["supply"] = [41.0]
        path.write_text(json.dumps(document))

    def no_unverified_solve(*_args, **_kwargs):
        pytest.fail("Unbound or modified dispatch must be rejected before AC power flow")

    monkeypatch.setattr(pypsa.Network, "pf", no_unverified_solve)
    with pytest.raises(OperationError, match="dispatch result"):
        execute_operation("operations.ac_validate", {
            "model_ref": model_ref, "dispatch_result_ref": dispatch["result_ref"],
        }, target, source, run_id=run_id)


@pytest.mark.parametrize("component", ["Store", "StorageUnit", "Link", "Process"])
def test_ac_validation_rejects_unrestored_dispatch_components(tmp_path, monkeypatch, component) -> None:
    import pandas as pd
    import pypsa
    from pypsa_model_authority import model_library

    source = tmp_path / "runs" / "ac-scope-run" / "domains" / "model"
    target = source.parent / "operations"
    run_id = "ac-scope-run"
    if component in {"Store", "Link"}:
        catalog_id = "rolling-storage" if component == "Store" else "electricity-hydrogen"
    else:
        # A local hash-bound NetCDF fixture exercises the installed PyPSA
        # components through the same registered-asset Authority path.
        library = tmp_path / "library"
        library.mkdir()
        network = pypsa.Network()
        network.set_snapshots(pd.date_range("2026-01-01", periods=3, freq="h"))
        network.add("Bus", "north", v_nom=110.0)
        network.add("Generator", "supply", bus="north", p_nom=100.0, marginal_cost=20.0)
        if component == "StorageUnit":
            network.add("Load", "demand", bus="north", p_set=[20.0, 40.0, 30.0])
            network.add("StorageUnit", "storage", bus="north", p_nom=10.0,
                        max_hours=2.0, state_of_charge_initial=20.0, marginal_cost=1.0)
        else:
            network.add("Bus", "south", v_nom=110.0)
            network.add("Load", "demand", bus="south", p_set=[20.0, 40.0, 30.0])
            network.add("Process", "transfer", bus0="north", bus1="south",
                        rate0=-1.0, rate1=1.0, p_nom=100.0)
        asset = library / "ac-component.nc"
        network.export_to_netcdf(asset)
        payload = asset.read_bytes()
        entry = model_library.OfficialModel(
            "pypsa-example/ac-component", "AC component", "ac-component",
            "https://data.pypsa.org/networks/examples/v1.3.0/ac-component.nc",
            len(payload), hashlib.sha256(payload).hexdigest(), "dispatch",
        )
        monkeypatch.setattr(model_library, "get_official_example", lambda _: entry)
        monkeypatch.setenv("CAPSTONE_PYPSA_MODEL_LIBRARY_DIR", str(library))
        catalog_id = entry.catalog_id
    opened = execute("model.open", {"catalog_id": catalog_id}, source, run_id=run_id)
    dispatch = execute_operation("operations.dispatch", {"model_ref": opened["model_ref"]},
                                 target, source, run_id=run_id)
    assert dispatch["condition"] == "optimal", "Optimization remains available for these models"
    existing_artifacts = {path for path in target.rglob("*") if path.is_file()}

    def no_incomplete_ac(*_args, **_kwargs):
        pytest.fail("AC must reject component schedules it has not restored")

    monkeypatch.setattr(pypsa.Network, "pf", no_incomplete_ac)
    with pytest.raises(OperationError) as failure:
        execute_operation("operations.ac_validate", {
            "model_ref": opened["model_ref"], "dispatch_result_ref": dispatch["result_ref"],
        }, target, source, run_id=run_id)
    assert failure.value.code == "unsupported_dispatch_components"
    assert component in str(failure.value)
    assert {path for path in target.rglob("*") if path.is_file()} == existing_artifacts
