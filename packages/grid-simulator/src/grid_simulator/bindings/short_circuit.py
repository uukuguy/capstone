from __future__ import annotations

from math import isfinite
from typing import Any

from pandapower.shortcircuit import calc_sc

from grid_simulator.bindings.base import AnalysisImplementationError, AnalysisOperation, AnalysisOutcome, AnalysisPrerequisiteError, closed_schema, effective, enum, number


DEFAULTS = {
    "bus": None,
    "fault": "3ph",
    "case": "max",
    "lv_tol_percent": 10,
    "topology": "auto",
    "ip": False,
    "ith": False,
    "tk_s": 1.0,
    "kappa_method": "C",
    "r_fault_ohm": 0.0,
    "x_fault_ohm": 0.0,
    "branch_results": False,
    "check_connectivity": True,
    "return_all_currents": False,
    "inverse_y": True,
    "use_pre_fault_voltage": False,
}
SCHEMA = closed_schema(
    {
        "bus": {
            "anyOf": [
                {"type": "null"},
                {"type": "integer", "minimum": 0},
                {"type": "array", "minItems": 1, "maxItems": 10000, "items": {"type": "integer", "minimum": 0}},
            ]
        },
        "fault": enum("3ph", "2ph", "1ph"),
        "case": enum("max", "min"),
        "lv_tol_percent": {"type": "integer", "enum": [6, 10]},
        "topology": enum("auto", "meshed", "radial"),
        "ip": {"type": "boolean"},
        "ith": {"type": "boolean"},
        "tk_s": number(exclusive_minimum=0),
        "kappa_method": enum("B", "C"),
        "r_fault_ohm": number(minimum=0),
        "x_fault_ohm": number(minimum=0),
        "branch_results": {"type": "boolean"},
        "check_connectivity": {"type": "boolean"},
        "return_all_currents": {"type": "boolean"},
        "inverse_y": {"type": "boolean"},
        "use_pre_fault_voltage": {"type": "boolean"},
    }
)


def run(engine: Any, net: Any, options: dict[str, Any]) -> AnalysisOutcome:
    selected = effective(DEFAULTS, options)
    gaps = []
    case = selected["case"]
    for index, source in net.ext_grid.loc[net.ext_grid.in_service].iterrows():
        for field in (f"s_sc_{case}_mva", f"rx_{case}"):
            value = source.get(field)
            try:
                numeric = float(value)
                valid = isfinite(numeric) and (numeric > 0 if field.startswith("s_sc_") else numeric >= 0)
            except (TypeError, ValueError):
                valid = False
            if not valid:
                gaps.append({"element_kind": "ext_grid", "index": int(index), "field": field})
    if gaps:
        raise AnalysisPrerequisiteError(
            "Short-circuit analysis requires finite external-grid short-circuit capacity and R/X data "
            "for the selected case. Missing or invalid inputs are listed in parameter_gaps; "
            "no solver result was produced.", parameter_gaps=gaps,
        )
    try:
        calc_sc(net, **selected)
    except AttributeError as exc:
        if selected["check_connectivity"] is False and "_is_elements_final" in str(exc):
            raise AnalysisImplementationError(
                "pandapower 3.4.0 short-circuit conversion failed to initialize internal element selection "
                "with check_connectivity=false. This is an implementation failure, not a physical network conclusion. "
                "A separate attempt with connectivity checking enabled may be considered; the requested option was not changed.",
                implementation="pandapower-3.4.0",
                option="check_connectivity",
                requested_value=False,
                exception_type=type(exc).__name__,
                exception_message=str(exc),
            ) from exc
        raise
    return AnalysisOutcome(
        "short_circuit.iec60909",
        "succeeded",
        selected,
        {"fault": selected["fault"], "case": selected["case"]},
    )


OPERATIONS = (
    AnalysisOperation(
        "short_circuit.iec60909",
        "IEC 60909 short-circuit calculation",
        "calc_sc",
        SCHEMA,
        run,
    ),
)
