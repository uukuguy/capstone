#!/usr/bin/env python3
"""Run the bounded provider-free HTTP portion of the M5 acceptance matrix."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from validation.thread.http_runner import HttpThreadSession
from validation.thread.m5_contract import M5CheckResult, M5RunSummary
from validation.thread.m5_matrix import run_application_matrix


def main() -> int:
    origin = os.environ.get("CAPSTONE_M5_API_ORIGIN")
    token = os.environ.get("CAPSTONE_M5_OPERATOR_TOKEN")
    application_id = os.environ.get("CAPSTONE_M5_APPLICATION", "pandapower-static-analysis")
    if not origin or not token:
        checks = (M5CheckResult(
            "live_thread_matrix", "skipped",
            {"reason": "CAPSTONE_M5_API_ORIGIN and CAPSTONE_M5_OPERATOR_TOKEN are required"},
        ),)
        report_origin = origin or "http://not-configured"
    else:
        try:
            with HttpThreadSession(origin, token) as session:
                checks = run_application_matrix(application_id, session)
            report_origin = origin
        except Exception as error:
            checks = (M5CheckResult("live_thread_matrix", "failed", {"reason": type(error).__name__}),)
            report_origin = origin
    summary = M5RunSummary(application_id=application_id, api_origin=report_origin, checks=checks)
    report_dir = Path(os.environ.get("CAPSTONE_M5_REPORT_DIR", "runs/capstone-m5"))
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"m5-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    report_path.write_text(json.dumps(summary.to_document(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"M5 validation report: {report_path}", file=sys.stderr)
    if any(check.status == "failed" for check in checks):
        return 1
    if any(check.status == "skipped" for check in checks):
        # A missing live credential is an environment/setup failure.  An
        # explicit opt-in is available for local report generation, but the
        # Make target must never turn an unexecuted matrix into a green gate.
        return 0 if os.environ.get("CAPSTONE_M5_ALLOW_SKIP") == "1" else 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
