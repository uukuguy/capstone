"""Open one registered PyPSA model for the operator's pre-run diagram."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

from capstone_agent.network_diagram import normalize_network_diagram
from pypsa_agent.network_view import build_pypsa_network_view
from pypsa_network_modeling.execution import ModelctlExecutor


ROOT = Path(__file__).resolve().parents[4]
CASES = frozenset({"regional-demand-stress", "scigrid-dispatch", "ac-dc-interconnection"})


def open_case_diagram(case_id: str) -> dict[str, object]:
    if case_id not in CASES:
        raise ValueError("PyPSA case is not registered")
    document = json.loads((ROOT / "validation" / "pypsa-cases" / "cases.json").read_text(
        encoding="utf-8",
    ))
    case = next((item for item in document["cases"] if item["id"] == case_id and
                 item["status"] == "runnable"), None)
    if case is None:
        raise ValueError("PyPSA case is unavailable")
    executable = Path(sys.executable).parent / "pypsamodelctl"
    with tempfile.TemporaryDirectory(prefix="capstone-pypsa-preview-") as directory:
        workspace = Path(directory) / "run-preview" / "domains" / "source"
        workspace.mkdir(parents=True)
        executor = ModelctlExecutor(executable=executable, workspace=workspace,
                                    timeout_seconds=180.0)
        opened = executor.invoke("model.open", {"catalog_id": case["model_id"]})
        model_ref = opened["model_ref"]
        if not isinstance(model_ref, str):
            raise ValueError("PyPSA authority returned an invalid model")
        view = build_pypsa_network_view(
            executor, model_ref, str(case["model_id"]), 1, case_id, None, (),
        )
        return normalize_network_diagram(view["diagram"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=sorted(CASES), required=True)
    args = parser.parse_args()
    try:
        diagram = open_case_diagram(args.case)
    except Exception:
        print("registered PyPSA case diagram unavailable", file=sys.stderr)
        return 1
    print(json.dumps(diagram, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
