#!/usr/bin/env python3
"""Run one registered Authority through the provider-free Thread host."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from validation.thread.m5_matrix import run_application_matrix
from validation.thread.m5_contract import M5CheckResult
from validation.thread.provider_free_host import ProviderFreeThreadHost


def _write_summary(root: Path, application_id: str, checks: tuple[M5CheckResult, ...]) -> Path:
    document = {
        "schema": "capstone-m5-provider-free/1",
        "application_id": application_id,
        "artifact_root": str(root),
        "check_counts": {
            "total": len(checks),
            "passed": sum(check.status == "passed" for check in checks),
            "skipped": sum(check.status == "skipped" for check in checks),
            "failed": sum(check.status == "failed" for check in checks),
        },
        "checks": [check.to_document() for check in checks],
    }
    path = root / "m5-provider-free-summary.json"
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    path.chmod(0o600)
    return path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--application", required=True, choices=("pandapower-static-analysis", "pypsa-business-cases"))
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    args.root.mkdir(mode=0o700, parents=True, exist_ok=True)
    with ProviderFreeThreadHost(args.application, args.root) as session:
        checks = run_application_matrix(args.application, session, timeout_seconds=60)
    report_path = _write_summary(args.root, args.application, checks)
    print(f"M5 provider-free summary: {report_path}", file=sys.stderr)
    document = json.loads(report_path.read_text(encoding="utf-8"))
    print(json.dumps(document, ensure_ascii=False, indent=2))
    return 1 if any(check.status == "failed" for check in checks) else 0


if __name__ == "__main__":
    raise SystemExit(main())
