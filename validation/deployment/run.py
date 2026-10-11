"""Run authorized business samples through the deployed production Thread API."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import time
import uuid

from capstone_agent.thread_http import HttpThreadSession
from validation.deployment.checks import check_answer


def _validate_cases(manifest):
    cases = manifest.get("cases", [])
    if not cases or len({case["id"] for case in cases}) != len(cases) or any(not case["turns"] for case in cases):
        raise ValueError("sample_cases_invalid")


def load_samples(path):
    raw = path.read_bytes()
    manifest = json.loads(raw)
    hashes = {path.name: sha256(raw).hexdigest()}
    if manifest.get("schema") != "capstone-deployment-samples/2":
        raise ValueError("sample_schema_invalid")
    if manifest.get("suite_kind") == "update":
        corpus_path = path.parent / manifest["corpus"]
        corpus_raw = corpus_path.read_bytes()
        corpus = json.loads(corpus_raw)
        if corpus.get("schema") != "capstone-deployment-samples/2" or corpus.get("suite_kind") != "overall":
            raise ValueError("update_requires_overall_corpus")
        _validate_cases(corpus)
        selected = manifest["case_ids"]
        cases = {case["id"]: case for case in corpus["cases"]}
        if not selected or len(set(selected)) != len(selected) or any(key not in cases for key in selected):
            raise ValueError("update_case_selection_invalid")
        manifest = {**corpus, **manifest, "cases": [cases[key] for key in selected]}
        hashes[corpus_path.name] = sha256(corpus_raw).hexdigest()
    elif manifest.get("suite_kind") != "overall":
        raise ValueError("sample_scope_invalid")
    _validate_cases(manifest)
    return manifest, hashes


def run_turn(session, turn, manifest, *, timeout=180):
    before = session.snapshot()
    receipt = session.command("send_auto", {"text": turn["text"], "enabled_profiles": [{
        "profile_id": manifest["profile_id"], "profile_version": manifest["profile_version"]}]})
    if receipt.status != "accepted" or not receipt.target or "attempt_id" not in receipt.target:
        raise ValueError("sample_command_rejected")
    attempt = receipt.target["attempt_id"]
    active = session.snapshot().active_model_context
    deadline, cursor = time.monotonic() + timeout, before.last_event_seq
    while time.monotonic() < deadline:
        page = session.events(after=cursor)
        cursor = page.next_event_seq
        for event in page.events:
            if event.attempt_id != attempt:
                continue
            if event.model_context_id != active.id or event.selection_revision != active.selection_revision:
                raise ValueError("sample_context_changed")
            if event.event_type not in {"attempt_completed", "attempt_failed", "attempt_cancelled", "attempt_interrupted"}:
                continue
            failed = [event.event_type] if event.event_type != "attempt_completed" else check_answer(turn["expect"], event.payload)
            snapshot = session.snapshot()
            results = event.payload.get("result_refs", [])
            evidence = event.payload.get("evidence_refs", [])
            projections = [p for p in snapshot.result_projections if p.attempt_id == attempt]
            for ref in results:
                matching = [p for p in projections if p.result_ref == ref]
                if not matching or any(p.model_revision != active.model_revision or
                    p.model_context_id != active.id or not set(p.evidence_refs) <= set(evidence) for p in matching):
                    failed.append("current_run_projection_missing")
            return {"instruction": turn["text"], "expectation": turn["expect"], "attempt_id": attempt,
                "thread_id": session.thread_id, "model_revision": active.model_revision,
                "terminal": event.event_type, "payload": event.payload, "failures": failed,
                "status": "failed" if failed else "passed"}
        time.sleep(0.5)
    session.command("cancel_live_attempt", {})
    raise TimeoutError("sample_deadline_exceeded")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-provider", action="store_true", help="Run only after explicit authorization for Provider calls")
    parser.add_argument("--samples", type=Path, required=True, help="Explicit overall corpus or upgrade-specific selection")
    parser.add_argument("--receipt-dir", type=Path, default=Path("runs/deployment-samples"))
    args = parser.parse_args(argv)
    if not args.allow_provider:
        parser.error("Provider samples are not authorized; use --allow-provider only after explicit approval")
    origin = os.environ.get("CAPSTONE_SAMPLE_API_ORIGIN", "")
    token = os.environ.get("CAPSTONE_SAMPLE_OPERATOR_TOKEN", "")
    if not origin or not token:
        parser.error("Sample API origin or protected operator token is missing")
    manifest, hashes = load_samples(args.samples)
    report = {"schema": "capstone-deployment-sample-receipt/2", "sample_hashes": hashes,
        "suite_id": manifest["suite_id"], "suite_kind": manifest["suite_kind"],
        "api_origin": origin, "mode": "deployed-api-screening", "provider_execution_identity": "unverified", "checks": [],
        "deployment_acceptance": "pending_identity_browser_and_update_checks"}
    for sample in manifest["cases"]:
        with HttpThreadSession(origin, token) as session:
            try:
                session.create(manifest["model_id"])
                for turn in sample["turns"]:
                    check = run_turn(session, turn, manifest)
                    report["checks"].append({"sample": sample["id"], **check})
                    if check["status"] != "passed":
                        break
            except Exception as error:
                # Exception messages may contain transport or configuration details.
                report["checks"].append({"sample": sample["id"], "status": "failed", "error_type": type(error).__name__})
    passed = len(report["checks"]) == sum(len(s["turns"]) for s in manifest["cases"]) and all(c["status"] == "passed" for c in report["checks"])
    report["automated_screening"] = "passed" if passed else "failed"
    report["business_samples"] = "pending_semantic_and_execution_identity_review" if passed else "failed"
    args.receipt_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = args.receipt_dir / ("provider-" + uuid.uuid4().hex[:16] + ".json")
    with os.fdopen(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), "w") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    print(f"Automated screening {'passed' if passed else 'failed'}; business acceptance pending or blocked; receipt: {path}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
