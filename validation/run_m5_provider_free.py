#!/usr/bin/env python3
"""Run one registered Authority through the provider-free Thread host."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from validation.thread.m5_matrix import run_application_matrix
from validation.thread.provider_free_host import ProviderFreeThreadHost


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--application", required=True, choices=("pandapower-static-analysis", "pypsa-business-cases"))
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    args.root.mkdir(mode=0o700, parents=True, exist_ok=True)
    with ProviderFreeThreadHost(args.application, args.root) as session:
        checks = run_application_matrix(args.application, session, timeout_seconds=60)
    document = {
        "schema": "capstone-m5-provider-free/1",
        "application_id": args.application,
        "checks": [check.to_document() for check in checks],
    }
    print(json.dumps(document, ensure_ascii=False, indent=2))
    return 1 if any(check.status == "failed" for check in checks) else 0


if __name__ == "__main__":
    raise SystemExit(main())
