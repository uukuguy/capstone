#!/usr/bin/env python3
"""Run one registered pandapower application fixture through the real Kernel."""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from validation.run import execute_application_case  # noqa: E402


CASES = frozenset({"pandapower-scripted-task", "pandapower-scripted-test"})


def run_case(case_id: str, instructions: tuple[str, ...]) -> dict[str, object]:
    if case_id not in CASES:
        raise ValueError("pandapower demo case is not registered")
    source = ROOT / "validation" / "application" / f"{case_id}.json"
    document = json.loads(source.read_text(encoding="utf-8"))
    expected = tuple(question["text"] for question in document["questions"])
    if instructions != expected:
        raise ValueError("pandapower demo instructions changed")
    document["run_id"] = f"capstone-pp-{uuid.uuid4().hex[:16]}"
    execution = execute_application_case(document, runs_root=ROOT / "runs" / "capstone-client")
    if execution.outcome.status != "completed" or not isinstance(execution.outcome.rendered, str):
        raise RuntimeError("pandapower application did not complete")
    result = json.loads(execution.outcome.rendered)
    if result.get("schema") != "capability-agent-output/1.0":
        raise RuntimeError("pandapower application returned the wrong output contract")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True)
    parser.add_argument("--instructions", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        instructions = tuple(
            line.strip() for line in args.instructions.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
        result = run_case(args.case, instructions)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"pandapower demo error: {type(exc).__name__}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
