#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _state_dir() -> Path:
    raw = os.environ.get("CLIMB_STATE_DIR")
    if raw:
        path = Path(raw)
        return path if path.is_absolute() else ROOT / path
    return ROOT / "docs/status/climb"


def _load_config(state_dir: Path) -> dict[str, object]:
    return json.loads((state_dir / "config.yaml").read_text(encoding="utf-8"))


def _resolve_artifact_dir(config: dict[str, object]) -> Path:
    raw = os.environ.get("CLIMB_ARTIFACT_DIR") or str(config.get("artifact_dir", "runs/climb"))
    path = Path(raw)
    return path if path.is_absolute() else ROOT / path


def _stable_manifest_path(run_dir: Path, config: dict[str, object]) -> str:
    manifest_path = (run_dir / "manifest.json").resolve()
    try:
        return manifest_path.relative_to(ROOT).as_posix()
    except ValueError:
        pass
    artifact_dir = _resolve_artifact_dir(config).resolve()
    try:
        return manifest_path.relative_to(artifact_dir).as_posix()
    except ValueError:
        return f"{run_dir.name}/manifest.json"


def _stable_path(path: Path, config: dict[str, object]) -> str:
    resolved = path.resolve()
    for base in (ROOT.resolve(), _resolve_artifact_dir(config).resolve(), _state_dir().resolve()):
        try:
            return resolved.relative_to(base).as_posix()
        except ValueError:
            continue
    return path.name


def _score_evidence_links(score: dict[str, object], config: dict[str, object]) -> list[dict[str, object]]:
    links: list[dict[str, object]] = []
    for key in config.get("subscores", config["score_weights"]):
        evidence = score.get("gate_evidence", {}).get(key, {})
        if not isinstance(evidence, dict):
            evidence = {}
        links.append(
            {
                "artifact_path": str(evidence.get("artifact_path") or ""),
                "command": [str(part) for part in evidence.get("command", [])],
                "returncode": evidence.get("returncode"),
                "score_key": key,
                "source": str(evidence.get("status", "unknown")),
            }
        )
    return links


def _update_manifest(run_dir: Path, eval_json: Path, decision_json: Path, score: dict[str, object], config: dict[str, object]) -> None:
    manifest_path = run_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "decision_artifact_path": _stable_path(decision_json, config),
            "local_eval_artifact_path": _stable_path(eval_json, config),
            "local_score": score["total"],
            "per_task": score["per_task"],
            "release_blockers": score.get("release_blockers", []),
            "release_ready": bool(score.get("release_ready")),
            "score_evidence": _score_evidence_links(score, config),
        }
    )
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("hypothesis_id")
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("eval_json", type=Path)
    parser.add_argument("decision_json", type=Path)
    args = parser.parse_args()

    state_dir = _state_dir()
    config = _load_config(state_dir)
    score_keys = list(config["score_weights"])
    hypotheses_path = state_dir / "hypotheses.yaml"
    document = json.loads(hypotheses_path.read_text(encoding="utf-8"))
    hypotheses = document["hypotheses"]
    known = {item["id"]: item for item in hypotheses}
    if args.hypothesis_id not in known:
        raise SystemExit(f"unknown hypothesis: {args.hypothesis_id}")

    score = json.loads(args.eval_json.read_text(encoding="utf-8"))
    decision = json.loads(args.decision_json.read_text(encoding="utf-8"))
    _update_manifest(args.run_dir, args.eval_json, args.decision_json, score, config)
    gate_evidence = score.get("gate_evidence", {})
    focused_gate = str(score.get("focused_gate") or known[args.hypothesis_id].get("focused_gate", ""))
    focused_status = gate_evidence.get(focused_gate, {}).get("status")
    if score.get("hypothesis_gate_passed") and focused_status == "passed":
        status = "confirmed"
        verdict = "confirmed: owned deterministic Workstream B gate passed"
    else:
        status = "falsified"
        verdict = str(decision.get("reason", "owned deterministic Workstream B gate failed"))

    now = datetime.now(timezone.utc).astimezone()
    run_id = args.run_dir.name
    events = list(document.get("events", []))
    if any(event.get("run_id") == run_id for event in events):
        raise SystemExit(f"run already synchronized: {run_id}")
    events.append(
        {
            "hypothesis_id": args.hypothesis_id,
            "run_id": run_id,
            "status": status,
            "recorded_at": now.isoformat(timespec="seconds"),
            "local_score": score["total"],
            "per_task": score["per_task"],
            "gate_evidence": gate_evidence,
            "verdict": verdict,
        }
    )
    document["events"] = events
    hypotheses_path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    runs_path = state_dir / "runs.csv"
    with runs_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if any(row["run_id"] == run_id for row in rows):
        raise SystemExit(f"run already recorded: {run_id}")
    cycle = max((int(row["cycle"]) for row in rows if row.get("cycle")), default=0) + 1
    parent_run = rows[-1]["run_id"] if rows else ""
    row = {
        "run_id": run_id,
        "cycle": cycle,
        "session": config["session"],
        "hypothesis_id": args.hypothesis_id,
        "paradigm": known[args.hypothesis_id]["parent_paradigm"],
        "parent_run": parent_run,
        "pushed_at": now.isoformat(timespec="seconds") if decision.get("decision") == "PUSH" else "",
        "lb_landed_at": now.isoformat(timespec="seconds"),
        "local_score": score["total"],
        **{f"local_{name}": score["per_task"].get(name, 0.0) for name in score_keys},
        "online_score": score["total"] if decision.get("decision") == "PUSH" else "",
        "gap": 0.0 if decision.get("decision") == "PUSH" else "",
        "push_decision": decision["decision"],
        "decision_reason": decision["reason"],
        "verdict": verdict,
        "train_cost_h": 0.0,
        "manifest_path": _stable_manifest_path(args.run_dir, config),
    }
    with runs_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or row)
    with runs_path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writerow({key: row.get(key, "") for key in fieldnames})

    effective = {item["id"]: item["status"] for item in hypotheses}
    for event in events:
        effective[event["hypothesis_id"]] = event["status"]
    remaining = [item["id"] for item in hypotheses if effective[item["id"]] in {"pending", "in-flight"}]
    session_path = state_dir / "session-state.json"
    session = json.loads(session_path.read_text(encoding="utf-8"))
    session.update(
        {
            "phase": "complete" if not remaining and score.get("release_ready") else (f"{remaining[0]} implementation" if remaining else "release closure"),
            "last_cycle": cycle,
            "next_hypothesis": remaining[0] if remaining else "none",
            "in_flight": None,
            "next_action": (
                "Target met; proceed with integration review and mainline closure."
                if not remaining
                else f"Execute {remaining[0]} through the deterministic local gate."
            ),
        }
    )
    session_path.write_text(json.dumps(session, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")

    with (state_dir / "adjudicator-log.md").open("a", encoding="utf-8") as handle:
        handle.write(
            f"\n## Cycle {cycle} — {args.hypothesis_id}\n\n"
            f"- Verdict: {status.upper()}.\n"
            f"- Local score: {score['total']:.2f}; subscores: {json.dumps(score['per_task'], sort_keys=True)}.\n"
            f"- Decision: {decision['decision']} — {decision['reason']}.\n"
        )
    env = os.environ.copy()
    env["CLIMB_STATE_DIR"] = str(state_dir)
    subprocess.run([str(ROOT / "tools/climb/regen-tree.py")], check=True, env=env)
    target = subprocess.run([str(ROOT / "tools/climb/check-target.py")], check=False, env=env)
    return 0 if target.returncode in {0, 10} else target.returncode


if __name__ == "__main__":
    raise SystemExit(main())
