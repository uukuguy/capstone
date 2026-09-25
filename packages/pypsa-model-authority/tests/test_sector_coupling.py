"""A registered cross-carrier solve admits only current-run target evidence."""

from __future__ import annotations

import pytest

from pypsa_model_authority.operations import execute
from pypsa_model_authority.sector_coupling import SectorError, execute_sector
from pypsa_model_authority.references import verify_sector_evidence, verify_sector_result


def test_electricity_to_hydrogen_balance_uses_real_solver(tmp_path) -> None:
    source = tmp_path / "runs" / "sector-run" / "domains" / "model"
    target = source.parent / "sector"
    opened = execute("model.open", {"catalog_id": "electricity-hydrogen"}, source, run_id="sector-run")
    result = execute_sector(
        "sector.hydrogen_balance", {"model_ref": opened["model_ref"]},
        target, source, run_id="sector-run",
    )
    assert result["condition"] == "optimal"
    assert result["electricity_generation_mwh"] == pytest.approx(50.0)
    assert result["conversion_input_mwh"] == pytest.approx(50.0)
    assert result["hydrogen_delivered_mwh"] == pytest.approx(40.0)
    assert result["conversion_loss_mwh"] == pytest.approx(10.0)
    assert result["objective"] == pytest.approx(1000.0)
    assert verify_sector_result(target, source, "sector-run", result["result_ref"]).document["model_ref"] == opened["model_ref"]
    assert verify_sector_evidence(target, source, "sector-run", result["evidence_refs"][0]).document["result_ref"] == result["result_ref"]


def test_foreign_sector_reference_creates_no_target_result(tmp_path) -> None:
    source = tmp_path / "runs" / "sector-run" / "domains" / "model"
    opened = execute("model.open", {"catalog_id": "electricity-hydrogen"}, source, run_id="sector-run")
    target = tmp_path / "runs" / "other" / "domains" / "sector"
    with pytest.raises(SectorError, match="current run|unavailable"):
        execute_sector(
            "sector.hydrogen_balance", {"model_ref": opened["model_ref"]},
            target, target.parent / "model", run_id="other",
        )
    assert not (target / "results").exists()


def test_registered_heat_pump_balance_and_model_scope(tmp_path) -> None:
    source = tmp_path / "runs" / "heat-run" / "domains" / "model"
    target = source.parent / "sector"
    opened = execute("model.open", {"catalog_id": "electricity-heat-pump"}, source, run_id="heat-run")
    result = execute_sector(
        "sector.heat_balance", {"model_ref": opened["model_ref"]},
        target, source, run_id="heat-run",
    )
    assert result["condition"] == "optimal"
    assert result["electricity_input_mwh"] == pytest.approx(10.0)
    assert result["heat_delivered_mwh"] == pytest.approx(30.0)
    assert result["coefficient_of_performance"] == pytest.approx(3.0)
    assert result["objective"] == pytest.approx(200.0)
    assert verify_sector_result(target, source, "heat-run", result["result_ref"]).document["capability"] == "sector.heat_balance"
    assert verify_sector_evidence(target, source, "heat-run", result["evidence_refs"][0]).document["model_ref"] == opened["model_ref"]

    hydrogen = execute("model.open", {"catalog_id": "electricity-hydrogen"}, source, run_id="heat-run")
    existing = len(list((target / "results").glob("*.json")))
    with pytest.raises(SectorError, match="registered model"):
        execute_sector(
            "sector.heat_balance", {"model_ref": hydrogen["model_ref"]},
            target, source, run_id="heat-run",
        )
    assert len(list((target / "results").glob("*.json"))) == existing


def test_registered_hydrogen_store_shifts_delivery_between_snapshots(tmp_path) -> None:
    source = tmp_path / "runs" / "store-run" / "domains" / "model"
    target = source.parent / "sector"
    opened = execute("model.open", {"catalog_id": "hydrogen-storage"}, source, run_id="store-run")
    result = execute_sector(
        "sector.hydrogen_storage", {"model_ref": opened["model_ref"]},
        target, source, run_id="store-run",
    )
    assert result["condition"] == "optimal"
    assert result["hydrogen_store_energy_mwh"] == pytest.approx([40.0, 0.0])
    assert result["hydrogen_delivered_mwh"] == pytest.approx([0.0, 40.0])
    assert result["electricity_input_mwh"] == pytest.approx([50.0, 0.0])
    assert result["objective"] == pytest.approx(1000.0)
    assert verify_sector_evidence(target, source, "store-run", result["evidence_refs"][0]).document["result_ref"] == result["result_ref"]


def test_registered_multiport_chp_supplies_hydrogen_and_heat(tmp_path) -> None:
    source = tmp_path / "runs" / "chp-run" / "domains" / "model"
    target = source.parent / "sector"
    opened = execute("model.open", {"catalog_id": "chp-hydrogen-heat"}, source, run_id="chp-run")
    result = execute_sector(
        "sector.multiport_balance", {"model_ref": opened["model_ref"]},
        target, source, run_id="chp-run",
    )
    assert result["condition"] == "optimal"
    assert result["gas_input_mwh"] == pytest.approx(100.0)
    assert result["electricity_delivered_mwh"] == pytest.approx(30.0)
    assert result["heat_delivered_mwh"] == pytest.approx(50.0)
    assert result["hydrogen_delivered_mwh"] == pytest.approx(20.0)
    assert result["objective"] == pytest.approx(1000.0)
    assert verify_sector_result(target, source, "chp-run", result["result_ref"]).document["model_ref"] == opened["model_ref"]


def test_registered_heat_store_uses_snapshot_cop_profile(tmp_path) -> None:
    source = tmp_path / "runs" / "heat-store-run" / "domains" / "model"
    target = source.parent / "sector"
    opened = execute("model.open", {"catalog_id": "heat-pump-storage"}, source, run_id="heat-store-run")
    result = execute_sector(
        "sector.heat_storage", {"model_ref": opened["model_ref"]},
        target, source, run_id="heat-store-run",
    )
    assert result["condition"] == "optimal"
    assert result["coefficient_of_performance"] == pytest.approx([4.0, 2.0])
    assert result["ambient_temperature_c"] == pytest.approx([10.0, 0.0])
    assert result["electricity_input_mwh"] == pytest.approx([10.0, 0.0])
    assert result["heat_store_energy_mwh"] == pytest.approx([40.0, 0.0])
    assert result["heat_delivered_mwh"] == pytest.approx([0.0, 40.0])
    assert result["objective"] == pytest.approx(200.0)
    assert verify_sector_evidence(target, source, "heat-store-run", result["evidence_refs"][0]).document["result_ref"] == result["result_ref"]
