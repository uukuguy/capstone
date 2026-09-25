"""Real fixed-model operations keep source revisions and target evidence separate."""

from __future__ import annotations

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
    assert result["objective"] > 0
    assert ModelStore(target, run_id="regional-run").load(result["evidence_refs"][0], "evidence")["result_ref"] == result["result_ref"]
