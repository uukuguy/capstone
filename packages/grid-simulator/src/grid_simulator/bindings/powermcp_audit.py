"""Published structural preflight over an Authority-owned PowerMCP sidecar."""
from __future__ import annotations

from typing import Any
import pandas as pd

from grid_simulator.bindings.base import AnalysisOperation, AnalysisOutcome, AnalysisPrerequisiteError, closed_schema


def run(engine: Any, net: Any, options: dict[str, Any]) -> AnalysisOutcome:
    from grid_simulator.powermcp_runner import audit_network
    try:
        rows, metadata = audit_network(engine, net)
    except AnalysisPrerequisiteError:
        raise
    except Exception as exc:
        # Private client errors can contain snapshot paths. Only this bounded
        # execution failure crosses the public protocol.
        raise ValueError("PowerMCP structural audit could not complete") from exc
    net["res_structural_audit"] = pd.DataFrame(rows).reindex(
        columns=("severity", "code", "message", "element_kind", "element_index", "subject_asset_ref"))
    return AnalysisOutcome("diagnostic.structural", "succeeded", {}, metadata)


OPERATIONS = (AnalysisOperation("diagnostic.structural", "Structural network audit", "powermcp.audit_network", closed_schema({}), run),)
