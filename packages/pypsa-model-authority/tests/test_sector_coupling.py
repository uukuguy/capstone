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
