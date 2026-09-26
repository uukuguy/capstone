"""Open one registered grid case model for the operator's pre-run diagram."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

from capstone_agent.network_diagram import normalize_network_diagram
from grid_agent.network_view import build_grid_network_view
from grid_agent.simulator.client import GridctlExecutor
from grid_agent.simulator.locator import GridctlLocator


ROOT = Path(__file__).resolve().parents[4]
CASES = frozenset({"pandapower-scripted-task", "pandapower-scripted-test"})


def open_case_diagram(case_id: str) -> dict[str, object]:
    if case_id not in CASES:
        raise ValueError("grid case is not registered")
    with tempfile.TemporaryDirectory(prefix="capstone-grid-preview-") as directory:
        executor = GridctlExecutor(
            executable=GridctlLocator(ROOT).resolve(), workspace=Path(directory),
        )
        opened = executor.invoke("context.open", {"model_id": "ieee39"})
        context_ref = opened["context_ref"]
        if not isinstance(context_ref, str):
            raise ValueError("grid authority returned an invalid context")
        view = build_grid_network_view(executor, context_ref, 1, case_id, (), ())
        return normalize_network_diagram(view["diagram"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=sorted(CASES), required=True)
    args = parser.parse_args()
    try:
        diagram = open_case_diagram(args.case)
    except Exception:
        print("registered grid case diagram unavailable", file=sys.stderr)
        return 1
    print(json.dumps(diagram, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
