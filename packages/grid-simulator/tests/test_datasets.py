from __future__ import annotations

import json

import pytest


def test_dataset_list_covers_all_nonempty_static_element_tables(grid, context_ref: str) -> None:
    response = grid.call("model.dataset.list", {"context_ref": context_ref})
    by_name = {item["dataset"]: item for item in response["datasets"]}

    assert {
        "network.buses",
        "network.branches",
        "network.bus",
        "network.line",
        "network.trafo",
        "network.ext_grid",
        "network.gen",
        "network.load",
        "network.poly_cost",
    } <= set(by_name)
    assert by_name["network.ext_grid"]["row_count"] == 1
    assert all(not name.startswith("network.res_") for name in by_name)


def test_context_overview_returns_sourced_input_totals_without_calculation(grid, context_ref: str) -> None:
    response = grid.call("context.get", {"context_ref": context_ref, "include_overview": True})
    overview = {item["dataset"]: item for item in response["overview"]}
    assert grid.engine.ac_run_count == 0
    assert "network.res_bus" not in overview
    for dataset in ["network.load", "network.gen"]:
        source = grid.call("model.dataset.query", {"context_ref": context_ref,
            "dataset": dataset, "select": ["p_mw"], "where": {"in_service": True},
            "aggregations": [{"field": "p_mw", "operator": "sum"}]})
        item = overview[dataset]
        assert item["dataset_ref"] == source["dataset_ref"]
        assert item["in_service_count"] == source["row_count"]
        actual = next(aggregate for aggregate in item["aggregates"]
                      if aggregate["field"] == "p_mw" and aggregate["operator"] == "sum")
        assert actual == source["aggregates"][0]
    assert "overview" not in grid.call("context.get", {"context_ref": context_ref})


def test_generic_dataset_describe_reports_typed_fields_and_units(grid, context_ref: str) -> None:
    response = grid.call(
        "model.dataset.describe",
        {"context_ref": context_ref, "dataset": "network.ext_grid"},
    )
    fields = {item["name"]: item for item in response["fields"]}

    assert {"asset_ref", "kind", "index", "alias", "bus", "vm_pu", "in_service"} <= set(fields)
    assert fields["index"]["type"] == "integer"
    assert fields["vm_pu"]["unit"] == "p.u."
    assert isinstance(fields["vm_pu"]["nullable"], bool)


def test_bus_type_metadata_describes_physical_construction(grid, context_ref: str) -> None:
    response = grid.call("model.dataset.describe", {
        "context_ref": context_ref, "dataset": "network.bus",
    })
    field = next(item for item in response["fields"] if item["name"] == "type")
    assert "b=busbar" in field["meaning"]
    assert "n=node" in field["meaning"]
    assert "m=muff" in field["meaning"]
    assert "not the power-flow PQ/PV/reference classification" in field["meaning"]
    assert field["provenance"] == "net.bus.type"


def test_overview_ignores_unrelated_objects_and_keeps_input_scaling_explicit():
    import pandas as pd
    import pandapower as pp
    from grid_simulator.operations import _model_input_overview
    net = pp.create_empty_network()
    bus = pp.create_bus(net, vn_kv=20)
    pp.create_load(net, bus, p_mw=4, scaling=0.5)
    pp.create_load(net, bus, p_mw=9, in_service=False)
    net.load["private_object"] = [object(), object()]
    net.load["q_mvar"] = pd.Series([pd.NA, 2.0], dtype="Float64")
    overview = {item["dataset"]: item for item in _model_input_overview(net, "revision:sha256:" + "a" * 64)}
    load = overview["network.load"]
    assert load["row_count"] == 2 and load["in_service_count"] == 1
    assert load["aggregation_scope"] == "in_service"
    totals = {item["field"]: item for item in load["aggregates"] if item["operator"] == "sum"}
    assert totals["p_mw"]["value"] == 4  # input field, not scaled injection
    assert totals["q_mvar"]["value"] is None
    assert totals["q_mvar"]["null_count"] == 1
    json.dumps(list(overview.values()), allow_nan=False)


def test_generic_dataset_query_is_bounded_schema_driven_and_pageable(grid, context_ref: str) -> None:
    response = grid.call(
        "model.dataset.query",
        {
            "context_ref": context_ref,
            "dataset": "network.load",
            "select": ["index", "bus", "p_mw", "q_mvar", "in_service"],
            "where": {"in_service": True},
            "sort": {"field": "index", "direction": "ascending"},
            "offset": 1,
            "limit": 2,
        },
    )

    assert response["row_count"] > response["returned_row_count"]
    assert response["returned_row_count"] == 2
    assert response["offset"] == 1
    assert response["next_offset"] == 3
    assert [row["index"] for row in response["rows"]] == [1, 2]
    json.dumps(response["rows"])


def test_dataset_aggregation_uses_all_filtered_rows_before_pagination(grid, context_ref: str) -> None:
    rows = grid.call("model.dataset.query", {"context_ref": context_ref,
        "dataset": "network.load", "select": ["p_mw"], "where": {"in_service": True}})
    response = grid.call("model.dataset.query", {"context_ref": context_ref,
        "dataset": "network.load", "select": ["p_mw"], "where": {"in_service": True},
        "limit": 1, "aggregations": [{"field": "p_mw", "operator": "sum"}]})
    assert response["returned_row_count"] == 1
    aggregate = response["aggregates"][0]
    assert aggregate == {"field": "p_mw", "operator": "sum", "unit": "MW",
        "value": pytest.approx(sum(row["p_mw"] for row in rows["rows"])),
        "valid_count": rows["row_count"], "null_count": 0}


def test_dataset_aggregation_rejects_text_arithmetic(grid, context_ref: str) -> None:
    error = grid.call_error("model.dataset.query", {"context_ref": context_ref,
        "dataset": "network.bus", "select": ["name"],
        "aggregations": [{"field": "name", "operator": "sum"}]})
    assert error.code == "dataset_query_invalid"


def test_dataset_aggregation_empty_selection_does_not_claim_zero_power(grid, context_ref: str) -> None:
    response = grid.call("model.dataset.query", {"context_ref": context_ref,
        "dataset": "network.load", "select": ["p_mw"],
        "filters": [{"field": "p_mw", "operator": "lt", "value": -1e20}],
        "aggregations": [{"field": "p_mw", "operator": "sum"},
                         {"field": "p_mw", "operator": "count"}]})
    assert response["aggregates"][0]["value"] is None
    assert response["aggregates"][1]["value"] == 0
    assert response["aggregates"][1]["unit"] is None


def test_aggregation_reports_nulls_and_numeric_range_without_coercion():
    from grid_simulator.operations import _aggregate_model_rows
    metadata = [{"name": "value", "type": "number", "unit": "MW"}]
    result = _aggregate_model_rows([{"value": 3.0}, {"value": None}, {"value": -2.0}], metadata,
        [{"field": "value", "operator": operator} for operator in ["sum", "min", "max", "count"]])
    assert [item["value"] for item in result] == [1.0, -2.0, 3.0, 2]
    assert all(item["valid_count"] == 2 and item["null_count"] == 1 for item in result)


def test_generic_dataset_query_rejects_undescribed_fields(grid, context_ref: str) -> None:
    error = grid.call_error(
        "model.dataset.query",
        {
            "context_ref": context_ref,
            "dataset": "network.ext_grid",
            "select": ["index", "res_p_mw"],
        },
    )

    assert error.code == "field_unavailable"
    assert "res_p_mw" in error.details["fields"]
    assert "vm_pu" in error.details["allowed_fields"]


@pytest.mark.parametrize(
    "field,operator,value",
    [
        ("vn_kv", "gt", "100.0"),
        ("vn_kv", "in", 110),
        ("in_service", "gt", False),
    ],
)
def test_model_dataset_query_rejects_incompatible_predicates(
    grid, context_ref: str, field: str, operator: str, value: object
) -> None:
    error = grid.call_error(
        "model.dataset.query",
        {
            "context_ref": context_ref,
            "dataset": "network.bus",
            "select": ["index", field],
            "filters": [{"field": field, "operator": operator, "value": value}],
        },
    )

    assert error.code == "dataset_query_invalid"
    assert error.phase == "validate"
    assert error.allowed_recovery_actions == ("describe_dataset", "correct_query")


def test_element_resolution_covers_all_schema_described_element_tables(grid, context_ref: str) -> None:
    response = grid.call(
        "model.element.get",
        {
            "context_ref": context_ref,
            "kind": "ext_grid",
            "namespace": "pandapower_index",
            "identifier": "0",
        },
    )

    assert response["asset_ref"].startswith("asset:ext_grid:sha256:")
    assert response["element"]["kind"] == "ext_grid"
    assert response["element"]["index"] == 0
    assert response["element"]["bus"] == 30
    assert response["element"]["in_service"] is True


def test_element_resolution_rejects_unavailable_tables_with_recovery(grid, context_ref: str) -> None:
    error = grid.call_error(
        "model.element.get",
        {
            "context_ref": context_ref,
            "kind": "arbitrary_python",
            "namespace": "pandapower_index",
            "identifier": "0",
        },
    )

    assert error.code == "unknown_element_kind"
    assert "ext_grid" in error.details["allowed_kinds"]
    assert error.allowed_recovery_actions == ("list_datasets",)


def test_missing_bus_voltage_is_described_as_uncomputed_not_a_physical_state(grid, context_ref):
    derived = grid.call("model.revision.derive", {"context_ref": context_ref,
        "patches": [{"operation": "in_service", "kind": "bus",
                     "selector": {"indices": [0]}, "value": False}]})
    result = grid.call("analysis.powerflow.ac.run", {"context_ref": derived["context_ref"]})
    description = grid.call("result.dataset.describe", {"result_ref": result["result_ref"],
                                                         "dataset": "result.res_bus"})
    voltage = next(field for field in description["fields"] if field["name"] == "vm_pu")
    assert voltage["nullable"] is True
    assert "no computed value" in voltage["meaning"]
    assert "not establish" in voltage["meaning"]


def test_branch_dataset_schema_enumerates_every_queryable_field(grid, context_ref: str) -> None:
    description = grid.call("model.dataset.describe", {"context_ref": context_ref, "dataset": "network.branches"})
    fields = {item["name"] for item in description["fields"]}

    assert {"asset_ref", "kind", "name", "from_bus_ref", "to_bus_ref", "in_service"} <= fields
    assert all({"name", "type", "unit", "meaning", "provenance"} <= set(item) for item in description["fields"])


def test_bus_dataset_query_selects_and_sorts_declared_fields(grid, context_ref: str) -> None:
    response = grid.call(
        "model.dataset.query",
        {
            "context_ref": context_ref,
            "dataset": "network.buses",
            "select": ["name", "vn_kv", "asset_ref"],
            "where": {"name": "6"},
            "sort": {"field": "name", "direction": "ascending"},
            "limit": 5,
        },
    )

    assert response["dataset"] == "network.buses"
    assert response["row_count"] == 1
    assert response["returned_row_count"] == 1
    assert response["rows"] == [{"name": "6", "vn_kv": 345.0, "asset_ref": response["rows"][0]["asset_ref"]}]
    assert response["rows"][0]["asset_ref"].startswith("asset:bus:sha256:")


def test_branch_dataset_query_filters_by_kind_and_asset_ref(grid, context_ref: str) -> None:
    resolved = grid.call(
        "model.element.get",
        {"context_ref": context_ref, "kind": "line", "namespace": "pandapower_index", "identifier": "11"},
    )
    response = grid.call(
        "model.dataset.query",
        {
            "context_ref": context_ref,
            "dataset": "network.branches",
            "select": ["asset_ref", "kind", "alias", "from_bus_ref", "to_bus_ref", "in_service"],
            "where": {"asset_ref": resolved["asset_ref"], "kind": "line"},
            "sort": {"field": "alias", "direction": "descending"},
            "limit": 10,
        },
    )

    assert response["row_count"] == 1
    assert response["rows"] == [
        {
            "asset_ref": resolved["asset_ref"],
            "kind": "line",
            "alias": "pandapower:line:11",
            "from_bus_ref": resolved["element"]["from_bus_ref"],
            "to_bus_ref": resolved["element"]["to_bus_ref"],
            "in_service": True,
        }
    ]


def test_unknown_query_field_returns_allowed_fields(grid, context_ref: str) -> None:
    error = grid.call_error(
        "model.dataset.query",
        {"context_ref": context_ref, "dataset": "network.branches", "select": ["mystery"]},
    )

    assert error.code == "field_unavailable"
    assert "allowed_fields" in error.details
    assert error.allowed_recovery_actions == ("describe_dataset",)


def test_sort_field_must_be_selected(grid, context_ref: str) -> None:
    error = grid.call_error(
        "model.dataset.query",
        {
            "context_ref": context_ref,
            "dataset": "network.buses",
            "select": ["name"],
            "sort": {"field": "vn_kv", "direction": "ascending"},
        },
    )

    assert error.code == "sort_field_unselected"
    assert error.allowed_recovery_actions == ("select_sort_field",)
