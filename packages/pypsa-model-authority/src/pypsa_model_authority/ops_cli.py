"""Fixed JSON endpoint for registered PyPSA power operations."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

os.environ.setdefault("POLARS_MAX_THREADS", "4")

from pypsa_model_authority.power_operations import (
    OperationError, PUBLISHED_OPERATIONS, execute_operation,
)
from pypsa_model_authority.references import verify_model


class OperationsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    protocol: Literal["pypsa-operations-capability"]
    protocol_version: Literal["1.0"]
    request_id: str = Field(min_length=1, max_length=200)
    capability: str = Field(min_length=1, max_length=100)
    arguments: dict[str, Any]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pypsaopsctl")
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
        request = OperationsRequest.model_validate(document)
    except (ValueError, ValidationError) as exc:
        _respond(request_id, ok=False, error={"code": "invalid_request", "message": str(exc)})
        return 0

    try:
        if request.capability == "environment.describe":
            if request.arguments:
                raise OperationError("invalid_arguments", "environment.describe takes no arguments")
            result = {
                "protocol": "pypsa-operations-capability", "protocol_version": "1.0",
                "service": "pypsa-model-authority", "service_version": "0.1.0",
                "executable_capabilities": [{"id": name} for name in PUBLISHED_OPERATIONS],
            }
        else:
            arguments = _authorize_handoff(
                request.capability,
                request.arguments,
                options.workspace,
                options.source_workspace,
                options.run_id,
            )
            result = execute_operation(
                request.capability, arguments,
                options.workspace, options.source_workspace, run_id=options.run_id,
            )
    except OperationError as exc:
        _respond(request.request_id, ok=False, error=exc.as_dict())
        return 0
    except Exception:
        print("pypsaopsctl internal error", file=sys.stderr)
        _respond(request.request_id, ok=False, error={
            "code": "internal_error", "message": "PyPSA operations authority could not complete the request",
        })
        return 1
    _respond(request.request_id, ok=True, result=result)
    return 0


def _authorize_handoff(
    capability: str,
    arguments: dict[str, Any],
    target_workspace: Path,
    source_workspace: Path,
    run_id: str,
) -> dict[str, object]:
    """Validate the application-issued handoff before entering the solver."""
    expected = {"reference", "handoff_ref"}
    if capability == "operations.security_dispatch":
        expected.add("outage_set_id")
    if capability == "operations.ac_validate":
        expected.add("dispatch_result_ref")
    if set(arguments) != expected:
        raise OperationError("invalid_arguments", "operation arguments do not match the contract")
    reference = arguments["reference"]
    handoff_ref = arguments["handoff_ref"]
    if not isinstance(reference, str) or not reference.startswith("pypsa-model:sha256:"):
        raise OperationError("invalid_arguments", "model reference is invalid")
    if not isinstance(handoff_ref, str) or not handoff_ref.startswith("handoff:sha256:"):
        raise OperationError("invalid_arguments", "handoff receipt is invalid")
    receipt = _find_handoff(target_workspace.parent.parent / "core" / "context-events.jsonl", handoff_ref)
    if (
        receipt.get("run_id") != run_id
        or receipt.get("source_binding_id") != source_workspace.name
        or receipt.get("target_binding_id") != target_workspace.name
        or receipt.get("reference") != reference
        or receipt.get("reference_kind") != "model"
        or receipt.get("purpose") != "operations"
        or receipt.get("capability_family") != "operations"
        or receipt.get("authority_id") != "pypsamodelctl"
        or receipt.get("revision_digest") != reference.removeprefix("pypsa-model:sha256:")
    ):
        raise OperationError("invalid_handoff", "handoff receipt does not authorize this operation")
    try:
        verify_model(source_workspace, run_id, reference)
    except Exception as exc:
        raise OperationError("invalid_model_ref", "model reference is unavailable in the current run") from exc
    passed: dict[str, object] = {"model_ref": reference}
    for key in ("outage_set_id", "dispatch_result_ref"):
        if key in arguments:
            passed[key] = arguments[key]
    return passed


def _find_handoff(path: Path, receipt_ref: str) -> dict[str, object]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise OperationError("invalid_handoff", "handoff ledger is unavailable") from exc
    for line in lines:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        payload = event.get("payload") if isinstance(event, dict) else None
        receipt = payload.get("receipt") if isinstance(payload, dict) else None
        if not isinstance(payload, dict) or payload.get("receipt_ref") != receipt_ref or not isinstance(receipt, dict):
            continue
        encoded = (
            json.dumps(receipt, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
        ).encode("utf-8")
        expected = "handoff:sha256:" + hashlib.sha256(encoded).hexdigest()
        if expected != receipt_ref:
            raise OperationError("invalid_handoff", "handoff receipt integrity failed")
        return receipt
    raise OperationError("invalid_handoff", "handoff receipt is unavailable")


def _respond(
    request_id: str, *, ok: bool, result: dict[str, object] | None = None,
    error: dict[str, str] | None = None,
) -> None:
    payload: dict[str, object] = {
        "protocol": "pypsa-operations-capability", "protocol_version": "1.0",
        "request_id": request_id, "ok": ok,
    }
    payload["result" if ok else "error"] = result if ok else error
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    raise SystemExit(main())
