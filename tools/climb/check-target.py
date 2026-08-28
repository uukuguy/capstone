#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _state_dir() -> Path:
    raw = os.environ.get("CLIMB_STATE_DIR")
    if raw:
        path = Path(raw)
        return path if path.is_absolute() else ROOT / path
    return ROOT / "docs/status/climb"


def _target_value(target_path: Path) -> float | None:
    in_block = False
    for line in target_path.read_text(encoding="utf-8").splitlines():
        if "TARGET-BEGIN" in line:
            in_block = True
            continue
        if "TARGET-END" in line:
            break
        if in_block and line.startswith("target_value:"):
            raw = line.split(":", 1)[1].strip()
            return float(raw) if raw else None
    return None


def main() -> int:
    state_dir = _state_dir()
    runs_path = state_dir / "runs.csv"
    session_path = state_dir / "session-state.json"
    target = _target_value(state_dir / "session-target.md")
    current = None
    if runs_path.is_file():
        with runs_path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                raw = row.get("local_score")
                if raw:
                    value = float(raw)
                    current = value if current is None else max(current, value)
    session = json.loads(session_path.read_text(encoding="utf-8")) if session_path.is_file() else {}
    release_closed = session.get("phase") == "complete"
    met = target is not None and current is not None and current >= target and release_closed
    print(
        json.dumps(
            {
                "has_target": target is not None,
                "metric": "local",
                "current": current,
                "target": target,
                "met": met,
                "reason": (
                    "release gate met"
                    if met
                    else "local score met; release closure pending"
                    if target is not None and current is not None and current >= target
                    else "continue Workstream B package extraction"
                ),
            },
            sort_keys=True,
        )
    )
    return 10 if met else 0


if __name__ == "__main__":
    raise SystemExit(main())
