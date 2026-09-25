from __future__ import annotations

import json
from pathlib import Path

import pytest


def _authority():
    from pypsa_model_authority.operations import ModelCapabilityError, execute
    from pypsa_model_authority.store import ModelStore

    return ModelCapabilityError, execute, ModelStore


def test_open_derive_and_inspect_real_network_without_mutating_parent(tmp_path: Path) -> None:
    _, execute, ModelStore = _authority()
    root = tmp_path / "authority"
    opened = execute("model.open", {"catalog_id": "two-bus"}, root, run_id="run-one")
    assert opened["model_ref"].startswith("pypsa-model:sha256:")
    assert opened["result_ref"].startswith("pypsa-result:sha256:")
    assert len(opened["evidence_refs"]) == 1

    store = ModelStore(root, run_id="run-one")
    original = store.load_network(opened["model_ref"])
    assert type(original).__module__.startswith("pypsa")
    assert len(original.buses) == 2
    assert original.loads.at["demand", "p_set"] == 40.0

    derived = execute(
        "model.derive",
        {"model_ref": opened["model_ref"], "load_id": "demand", "p_set_mw": 55.0},
        root,
        run_id="run-one",
    )
    assert derived["model_ref"] != opened["model_ref"]
    assert store.load_model(derived["model_ref"])["parent_ref"] == opened["model_ref"]
    assert store.load_network(opened["model_ref"]).loads.at["demand", "p_set"] == 40.0
    assert store.load_network(derived["model_ref"]).loads.at["demand", "p_set"] == 55.0

    inspected = execute(
        "model.inspect", {"model_ref": derived["model_ref"]}, root, run_id="run-one"
    )
    assert inspected["component_counts"] == {"Bus": 2, "Load": 1, "Generator": 1, "Line": 1}
    assert inspected["load_p_set_mw"] == {"demand": 55.0}


def test_current_run_and_document_digest_are_required(tmp_path: Path) -> None:
    ModelCapabilityError, execute, ModelStore = _authority()
    root = tmp_path / "authority"
    opened = execute("model.open", {"catalog_id": "two-bus"}, root, run_id="run-one")
    with pytest.raises(ModelCapabilityError, match="current run"):
        execute(
            "model.inspect", {"model_ref": opened["model_ref"]}, root, run_id="run-two"
        )

    path = ModelStore(root, run_id="run-one").model_path(opened["model_ref"])
    document = json.loads(path.read_text())
    document["components"]["loads"][0]["p_set_mw"] = 999.0
    path.write_text(json.dumps(document))
    with pytest.raises(ModelCapabilityError, match="integrity"):
        execute(
            "model.inspect", {"model_ref": opened["model_ref"]}, root, run_id="run-one"
        )


def test_only_registered_catalog_and_typed_edits_are_accepted(tmp_path: Path) -> None:
    ModelCapabilityError, execute, _ = _authority()
    root = tmp_path / "authority"
    with pytest.raises(ModelCapabilityError, match="registered"):
        execute("model.open", {"catalog_id": "../../outside"}, root, run_id="run-one")
    opened = execute("model.open", {"catalog_id": "two-bus"}, root, run_id="run-one")
    with pytest.raises(ModelCapabilityError, match="arguments"):
        execute(
            "model.derive",
            {"model_ref": opened["model_ref"], "load_id": "demand", "p_set_mw": 50.0,
             "path": "/outside"},
            root,
            run_id="run-one",
        )


def test_typed_snapshot_demand_derivation_and_validation(tmp_path: Path) -> None:
    _, execute, ModelStore = _authority()
    root = tmp_path / "authority"
    opened = execute("model.open", {"catalog_id": "unit-commitment"}, root, run_id="series-run")
    derived = execute("model.derive_series", {
        "model_ref": opened["model_ref"], "load_id": "demand",
        "p_set_mw": [30.0, 50.0],
    }, root, run_id="series-run")
    store = ModelStore(root, run_id="series-run")
    assert store.load_model(derived["model_ref"])["parent_ref"] == opened["model_ref"]
    assert store.load_network(derived["model_ref"]).loads_t.p_set["demand"].tolist() == [30.0, 50.0]
    assert store.load_network(opened["model_ref"]).loads_t.p_set["demand"].tolist() == [20.0, 60.0]
    validated = execute("model.validate", {"model_ref": derived["model_ref"]}, root, run_id="series-run")
    assert validated["valid"] is True
    assert validated["total_demand_mw"] == [30.0, 50.0]
    assert store.load(validated["evidence_refs"][0], "evidence")["result_ref"] == validated["result_ref"]
    scenario = execute("model.open", {"catalog_id": "capacity-scenarios"}, root, run_id="series-run")
    scenario_check = execute("model.validate", {"model_ref": scenario["model_ref"]}, root, run_id="series-run")
    assert scenario_check["scenario_total_demand_mw"] == {"low": [20.0], "high": [40.0]}
