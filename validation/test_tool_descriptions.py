"""Regression checks for tool descriptions used by the five runnable demo cases."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

CASE_TOOL_DEFINITIONS = {
    "packages/grid-simulator/src/grid_simulator/capabilities/definitions/context.open.json",
    "packages/grid-simulator/src/grid_simulator/capabilities/definitions/topology.branch.endpoints.get.json",
    "packages/grid-simulator/src/grid_simulator/capabilities/definitions/analysis.powerflow.ac.run.json",
    "packages/grid-simulator/src/grid_simulator/capabilities/definitions/result.branches.rank.json",
    "packages/grid-simulator/src/grid_simulator/capabilities/definitions/model.constraints.describe.json",
    "packages/grid-simulator/src/grid_simulator/capabilities/definitions/model.element.get.json",
    "packages/grid-simulator/src/grid_simulator/capabilities/definitions/analysis.contingency.n_minus_one.run.json",
    "packages/pypsa-network-modeling-domain-pack/src/pypsa_network_modeling/resources/capabilities/model.open.json",
    "packages/pypsa-network-modeling-domain-pack/src/pypsa_network_modeling/resources/capabilities/model.inspect.json",
    "packages/pypsa-network-modeling-domain-pack/src/pypsa_network_modeling/resources/capabilities/model.topology.json",
    "packages/pypsa-network-modeling-domain-pack/src/pypsa_network_modeling/resources/capabilities/model.derive_series.json",
    "packages/pypsa-power-operations-domain-pack/src/pypsa_power_operations/resources/capabilities/operations.dispatch.json",
}


def test_runnable_case_tools_describe_every_required_input_field() -> None:
    for relative_path in sorted(CASE_TOOL_DEFINITIONS):
        document = json.loads((ROOT / relative_path).read_text(encoding="utf-8"))
        schema = document["input_schema"]
        properties = schema["properties"]
        missing = [
            field
            for field in schema["required"]
            if not isinstance(properties.get(field), dict)
            or not isinstance(properties[field].get("description"), str)
            or not properties[field]["description"].strip()
        ]
        assert not missing, f"{document['id']} lacks required input descriptions: {missing}"
