"""Write a bounded, private receipt for remote provider-free Thread acceptance."""
from __future__ import annotations

import json
import os
from pathlib import Path
import uuid

from capstone_agent.thread_http import HttpThreadSession

from validation.thread.m11_matrix import run_matrix


def main() -> int:
    origin = os.environ.get("CAPSTONE_M11_API_ORIGIN", "")
    token = os.environ.get("CAPSTONE_M11_OPERATOR_TOKEN", "")
    if not origin or not token:
        print("M11 configuration is missing; validation was not run.")
        return 2
    receipt: dict[str, object] = {"schema": "capstone-m11-validation/1",
        "runtime_mode": "m11-provider-free", "provider_validation": "not_run"}
    try:
        session = HttpThreadSession(origin, token)
    except ValueError:
        print("M11 configuration is invalid; validation was not run.")
        return 2
    code = 0
    with session:
        try:
            checks = run_matrix(session)
        except Exception as error:
            # Fixed error categories exclude server response bodies and credentials.
            checks = [{"id": "remote-matrix", "status": "failed",
                       "details": {"error_type": type(error).__name__}}]
            code = 1
            if session.thread_id is not None:
                try:
                    snapshot = session.snapshot()
                    if snapshot.current_attempt is not None:
                        session.command("cancel_live_attempt", {})
                except Exception:
                    pass
        receipt.update({"api_origin": session.api_origin, "thread_id": session.thread_id,
                        "run_id": session.run_id, "checks": checks})
    if len(checks) > 64:
        raise ValueError("M11 receipt check limit exceeded")
    content = json.dumps(receipt, ensure_ascii=False, indent=2).encode()
    if len(content) > 256 * 1024:
        raise ValueError("M11 receipt size limit exceeded")
    directory = Path(os.environ.get("CAPSTONE_M11_RECEIPT_DIR", "runs/capstone-m11"))
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = directory / f"m11-{uuid.uuid4().hex[:16]}.json"
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as stream:
        stream.write(content)
    print(f"M11 {'passed' if code == 0 else 'failed'}; receipt: {path}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
