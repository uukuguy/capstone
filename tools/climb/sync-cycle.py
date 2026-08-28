#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from climb_evidence import JsonObject, as_object, load_json_object


ROOT = Path(__file__).resolve().parents[2]


def _state_dir() -> Path:
    raw = os.environ.get("CLIMB_STATE_DIR")
    if raw:
        path = Path(raw)
        return path if path.is_absolute() else ROOT / path
    return ROOT / "docs/status/climb"


def _load_config(state_dir: Path) -> JsonObject:
    return load_json_object(state_dir / "config.yaml")


def _resolve_artifact_dir(config: JsonObject) -> Path:
    raw = os.environ.get("CLIMB_ARTIFACT_DIR") or str(config.get("artifact_dir", "runs/climb"))
    path = Path(raw)
    return path if path.is_absolute() else ROOT / path


def _stable_manifest_path(run_dir: Path, config: JsonObject) -> str:
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


def _stable_path(path: Path, config: JsonObject) -> str:
    resolved = path.resolve()
    for base in (ROOT.resolve(), _resolve_artifact_dir(config).resolve(), _state_dir().resolve()):
        try:
            return resolved.relative_to(base).as_posix()
        except ValueError:
            continue
    return path.name


def _score_keys(config: JsonObject) -> list[str]:
    weights = as_object(config.get("score_weights"), "score_weights")
    raw_subscores = config.get("subscores")
    if raw_subscores is None:
        return [str(key) for key in weights]
    if not isinstance(raw_subscores, list):
        raise SystemExit("subscores must be a list")
    return [str(key) for key in raw_subscores]


def _score_evidence_links(score: JsonObject, config: JsonObject) -> list[JsonObject]:
    links: list[JsonObject] = []
    gate_evidence = as_object(score.get("gate_evidence"), "gate_evidence")
    for key in _score_keys(config):
        evidence = gate_evidence.get(key)
        if not isinstance(evidence, dict):
            evidence = {}
        link: JsonObject = {
                "artifact_path": str(evidence.get("artifact_path") or ""),
                "command": [str(part) for part in evidence.get("command", [])],
                "output_artifact_path": str(evidence.get("output_artifact_path") or ""),
                "output_sha256": str(evidence.get("output_sha256") or ""),
                "receipt_digest": str(evidence.get("receipt_digest") or ""),
                "release_source_revision": str(evidence.get("release_source_revision") or ""),
                "release_source_tree_sha256": str(evidence.get("release_source_tree_sha256") or ""),
                "returncode": evidence.get("returncode"),
                "score_key": key,
                "source": str(evidence.get("status", "unknown")),
                "attestation_id": str(evidence.get("attestation_id") or ""),
                "closure_digest": str(evidence.get("closure_digest") or ""),
                "policy_sha256": str(evidence.get("policy_sha256") or ""),
                "stderr_sha256": str(evidence.get("stderr_sha256") or ""),
                "stdout_sha256": str(evidence.get("stdout_sha256") or ""),
            }
        prerequisites = evidence.get("prerequisite_receipts")
        if isinstance(prerequisites, dict):
            link["prerequisite_receipts"] = [
                {
                    "artifact_path": str(item.get("artifact_path") or ""),
                    "attestation_id": str(item.get("attestation_id") or ""),
                    "closure_digest": str(item.get("closure_digest") or ""),
                    "command": [str(part) for part in item.get("command", [])],
                    "output_artifact_path": str(item.get("output_artifact_path") or ""),
                    "output_sha256": str(item.get("output_sha256") or ""),
                    "policy_sha256": str(item.get("policy_sha256") or ""),
                    "receipt_digest": str(item.get("receipt_digest") or ""),
                    "receipt_key": str(prerequisite_key),
                    "release_source_revision": str(item.get("release_source_revision") or ""),
                    "release_source_tree_sha256": str(item.get("release_source_tree_sha256") or ""),
                    "returncode": item.get("returncode"),
                    "source": str(item.get("status", "unknown")),
                    "stderr_sha256": str(item.get("stderr_sha256") or ""),
                    "stdout_sha256": str(item.get("stdout_sha256") or ""),
                }
                for prerequisite_key, item in prerequisites.items()
                if isinstance(item, dict)
            ]
        links.append(link)
    return links


def _update_manifest(run_dir: Path, eval_json: Path, decision_json: Path, score: JsonObject, config: JsonObject) -> None:
    manifest_path = run_dir / "manifest.json"
    manifest = load_json_object(manifest_path)
    manifest.update(
        {
            "decision_artifact_path": _stable_path(decision_json, config),
            "local_eval_artifact_path": _stable_path(eval_json, config),
            "local_score": score["total"],
            "per_task": score["per_task"],
            "release_blockers": score.get("release_blockers", []),
            "release_ready": bool(score.get("release_ready")),
            "release_source_revision": str(score.get("release_source_revision") or ""),
            "release_source_tree_sha256": str(score.get("release_source_tree_sha256") or ""),
            "policy_sha256": str(score.get("policy_sha256") or ""),
            "closure_artifact_path": str(score.get("closure_artifact_path") or ""),
            "closure_digest": str(score.get("closure_digest") or ""),
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
    score_keys = _score_keys(config)
    hypotheses_path = state_dir / "hypotheses.yaml"
    document = load_json_object(hypotheses_path)
    raw_hypotheses = document.get("hypotheses")
    if not isinstance(raw_hypotheses, list):
        raise SystemExit("hypotheses must be a list")
    hypotheses = [as_object(item, "hypothesis") for item in raw_hypotheses]
    known = {str(item["id"]): item for item in hypotheses}
    if args.hypothesis_id not in known:
        raise SystemExit(f"unknown hypothesis: {args.hypothesis_id}")

    score = load_json_object(args.eval_json)
    decision = load_json_object(args.decision_json)
    _update_manifest(args.run_dir, args.eval_json, args.decision_json, score, config)
    gate_evidence = as_object(score.get("gate_evidence"), "gate_evidence")
    focused_gate = str(score.get("focused_gate") or known[args.hypothesis_id].get("focused_gate", ""))
    focused_evidence = gate_evidence.get(focused_gate)
    if not isinstance(focused_evidence, dict):
        focused_evidence = {}
    focused_status = focused_evidence.get("status")
    if score.get("hypothesis_gate_passed") and focused_status in {"passed", "closure-passed"}:
        status = "confirmed"
        verdict = "confirmed: owned deterministic Workstream B gate passed"
    else:
        status = "falsified"
        verdict = str(decision.get("reason", "owned deterministic Workstream B gate failed"))

    now = datetime.now(timezone.utc).astimezone()
    run_id = args.run_dir.name
    raw_events = document.get("events", [])
    if not isinstance(raw_events, list):
        raise SystemExit("events must be a list")
    events = list(raw_events)
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
    per_task = as_object(score.get("per_task"), "per_task")
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
        **{f"local_{name}": per_task.get(name, 0.0) for name in score_keys},
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

    effective = {str(item["id"]): item["status"] for item in hypotheses}
    for event in events:
        if isinstance(event, dict):
            effective[str(event["hypothesis_id"])] = event["status"]
    remaining = [str(item["id"]) for item in hypotheses if effective[str(item["id"])] in {"pending", "in-flight"}]
    session_path = state_dir / "session-state.json"
    session = load_json_object(session_path)
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
