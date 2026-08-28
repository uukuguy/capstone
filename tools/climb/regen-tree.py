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


def main() -> None:
    state_dir = _state_dir()
    config = json.loads((state_dir / "config.yaml").read_text(encoding="utf-8"))
    hypothesis_document = json.loads((state_dir / "hypotheses.yaml").read_text(encoding="utf-8"))
    hypotheses = hypothesis_document["hypotheses"]
    effective_status = {item["id"]: item["status"] for item in hypotheses}
    for event in hypothesis_document.get("events", []):
        effective_status[event["hypothesis_id"]] = event["status"]
    session = json.loads((state_dir / "session-state.json").read_text(encoding="utf-8"))
    with (state_dir / "runs.csv").open(newline="", encoding="utf-8") as handle:
        runs = list(csv.DictReader(handle))
    active = [item for item in hypotheses if effective_status[item["id"]] in {"pending", "in-flight"}]
    confirmed = [item for item in hypotheses if effective_status[item["id"]] == "confirmed"]
    falsified = [item for item in hypotheses if effective_status[item["id"]] == "falsified"]
    tree = {
        "schema_version": 1,
        "session": config["session"],
        "score_name": config["score_name"],
        "score_weights": config["score_weights"],
        "generated_from_runs": len(runs),
        "active": [item["id"] for item in active],
        "confirmed": [item["id"] for item in confirmed],
        "falsified": [item["id"] for item in falsified],
        "next_hypothesis": session.get("next_hypothesis", "none"),
    }
    (state_dir / "research-tree.json").write_text(json.dumps(tree, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# Research Tree — Workstream B Package Extraction",
        "",
        f"> Generated deterministically from {len(runs)} climb runs.",
        "",
        f"**Session:** {config['session']}",
        "",
        "**Target:** 100% package extraction score with all release gates closed.",
        "",
        "## Score Contract",
        "",
    ]
    lines.extend(f"- {key}: {float(value):g}" for key, value in config["score_weights"].items())
    lines.extend(
        [
            "",
            "## In-flight",
            "",
            f"- Phase: {session.get('phase', 'unknown')}",
            f"- Last cycle: {session.get('last_cycle', 0)}",
            f"- Next hypothesis: {session.get('next_hypothesis', 'none')}",
            f"- Next action: {session.get('next_action', 'none')}",
            "",
            "## Runs",
            "",
        ]
    )
    if runs:
        lines.extend(f"- {row['run_id']}: {row['local_score']}% — {row['verdict']}" for row in runs)
    else:
        lines.append("- No scored cycle yet.")
    lines.extend(["", "## Active hypotheses", ""])
    if active:
        lines.extend(f"- **{item['id']}**: {item['description']}" for item in active)
    else:
        lines.append("- None.")
    lines.extend(["", "## Confirmed", ""])
    if confirmed:
        lines.extend(f"- **{item['id']}**: {item['description']}" for item in confirmed)
    else:
        lines.append("- None.")
    lines.extend(["", "## Negative cache", ""])
    falsified_routes = session.get("falsified_routes", [])
    if falsified_routes:
        lines.extend(f"- {item}" for item in falsified_routes)
    else:
        lines.append("- None.")
    (state_dir / "research-tree.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
