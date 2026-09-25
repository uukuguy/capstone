"""Fixed JSON endpoint for registered PyPSA sector coupling."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

os.environ.setdefault("POLARS_MAX_THREADS", "4")

from pypsa_model_authority.sector_coupling import (
    SectorError, PUBLISHED_SECTOR, execute_sector,
)


class SectorRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    protocol: Literal["pypsa-sector-capability"]
    protocol_version: Literal["1.0"]
    request_id: str = Field(min_length=1, max_length=200)
    capability: str = Field(min_length=1, max_length=100)
    arguments: dict[str, Any]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pypsasectorctl")
    command = parser.add_subparsers(dest="command", required=True)
    request_parser = command.add_parser("request")
    request_parser.add_argument("--workspace", type=Path, required=True)
    request_parser.add_argument("--source-workspace", type=Path, required=True)
    request_parser.add_argument("--run-id", required=True)
    options = parser.parse_args(argv)

    request_id = "unknown"
    try:
        raw = sys.stdin.read(65_537)
        if len(raw) > 65_536 or len(raw.splitlines()) != 1:
            raise ValueError("stdin must contain exactly one bounded JSON request")
        document = json.loads(raw)
        if isinstance(document, dict) and isinstance(document.get("request_id"), str):
            request_id = document["request_id"][:200]
        request = SectorRequest.model_validate(document)
    except (ValueError, ValidationError) as exc:
        _respond(request_id, ok=False, error={"code": "invalid_request", "message": str(exc)})
        return 0

    try:
        if request.capability == "environment.describe":
            if request.arguments:
                raise SectorError("invalid_arguments", "environment.describe takes no arguments")
            result = {
                "protocol": "pypsa-sector-capability", "protocol_version": "1.0",
                "service": "pypsa-model-authority", "service_version": "0.1.0",
                "executable_capabilities": [{"id": name} for name in PUBLISHED_SECTOR],
            }
        else:
            result = execute_sector(
                request.capability, request.arguments,
                options.workspace, options.source_workspace, run_id=options.run_id,
            )
    except SectorError as exc:
        _respond(request.request_id, ok=False, error=exc.as_dict())
        return 0
    except Exception:
        print("pypsasectorctl internal error", file=sys.stderr)
        _respond(request.request_id, ok=False, error={
            "code": "internal_error", "message": "PyPSA sector authority could not complete the request",
        })
        return 1
    _respond(request.request_id, ok=True, result=result)
    return 0


def _respond(
    request_id: str, *, ok: bool, result: dict[str, object] | None = None,
    error: dict[str, str] | None = None,
) -> None:
    payload: dict[str, object] = {
        "protocol": "pypsa-sector-capability", "protocol_version": "1.0",
        "request_id": request_id, "ok": ok,
    }
    payload["result" if ok else "error"] = result if ok else error
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    raise SystemExit(main())
