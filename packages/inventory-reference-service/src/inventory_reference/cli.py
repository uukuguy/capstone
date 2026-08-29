from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from inventory_reference.models import CapabilityRequest
from inventory_reference.operations import InventoryCapabilityError, execute


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="inventoryctl")
    subparsers = parser.add_subparsers(dest="command", required=True)
    request_parser = subparsers.add_parser("request")
    request_parser.add_argument("--workspace", type=Path, required=True)
    options = parser.parse_args(argv)

    raw: Any = None
    request_id = "unknown"
    try:
        lines = sys.stdin.read().splitlines()
        if len(lines) != 1:
            raise ValueError("stdin must contain exactly one JSON request")
        raw = json.loads(lines[0])
        if isinstance(raw, dict) and isinstance(raw.get("request_id"), str):
            request_id = raw["request_id"]
        request = CapabilityRequest.model_validate(raw)
    except (ValueError, json.JSONDecodeError, ValidationError) as exc:
        _write_response(
            request_id,
            ok=False,
            error={
                "code": "invalid_request",
                "message": str(exc),
                "recovery": "Send one inventory-capability/1.0 JSON request.",
            },
        )
        return 0

    try:
        result = execute(request.capability, request.arguments, options.workspace)
    except InventoryCapabilityError as exc:
        _write_response(request.request_id, ok=False, error=exc.as_dict())
        return 0
    except Exception as exc:
        print(f"inventoryctl internal error: {exc}", file=sys.stderr)
        _write_response(
            request.request_id,
            ok=False,
            error={
                "code": "internal_error",
                "message": "inventory service could not complete the request",
                "recovery": "Retry in a fresh workspace and inspect stderr diagnostics.",
            },
        )
        return 1
    _write_response(request.request_id, ok=True, result=result)
    return 0


def _write_response(
    request_id: str,
    *,
    ok: bool,
    result: dict[str, object] | None = None,
    error: dict[str, object] | None = None,
) -> None:
    document: dict[str, object] = {
        "protocol": "inventory-capability",
        "protocol_version": "1.0",
        "request_id": request_id,
        "ok": ok,
    }
    if ok:
        document["result"] = result or {}
    else:
        document["error"] = error or {}
    print(
        json.dumps(
            document,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
