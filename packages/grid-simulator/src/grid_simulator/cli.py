from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from pydantic import ValidationError

from grid_simulator.operations import dispatch
from grid_simulator.protocol import CapabilityError, GridCapabilityRequest, GridCapabilityResponse


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gridctl")
    subparsers = parser.add_subparsers(dest="command", required=True)
    request_parser = subparsers.add_parser("request")
    request_parser.add_argument("--workspace", type=Path, required=True)
    request_parser.add_argument('--bound-context')
    args = parser.parse_args(argv)
    if args.command != "request":
        return 2

    try:
        raw = json.loads(sys.stdin.read())
        request = GridCapabilityRequest.model_validate(raw)
    except (json.JSONDecodeError, ValidationError) as exc:
        response = GridCapabilityResponse(
            request_id="invalid-request",
            ok=False,
            error=CapabilityError(
                code="invalid_request",
                phase="parse",
                message="Request must be a valid grid-capability 1.0 JSON object",
                retryable=False,
                allowed_recovery_actions=("correct_request",),
            ),
        )
        _write_response(response)
        print(f"gridctl: invalid request: {exc}", file=sys.stderr)
        return 2

    scope_ref = args.bound_context
    scope_path = args.workspace / 'thread-model-scope.json'
    try:
        if scope_path.exists() or scope_path.is_symlink():
            descriptor = os.open(scope_path, os.O_RDONLY | os.O_NOFOLLOW)
            try:
                payload = os.read(descriptor, 4097)
            finally:
                os.close(descriptor)
            scope = json.loads(payload)
            if (len(payload) > 4096 or set(scope) != {'schema', 'base_context_ref'}
                or scope['schema'] != 'grid-thread-model-scope/1'
                or not isinstance(scope['base_context_ref'], str)
                or scope_ref is not None and scope_ref != scope['base_context_ref']):
                raise ValueError('invalid scope')
            scope_ref = scope['base_context_ref']
    except (OSError, ValueError, TypeError):
        _write_response(GridCapabilityResponse(request_id=request.request_id, ok=False,
            error=CapabilityError(code='model_scope_invalid', phase='validate',
                                  message='The application model scope is unavailable or invalid', retryable=False)))
        return 0
    _write_response(dispatch(request, args.workspace, bound_context_ref=scope_ref))
    return 0


def _write_response(response: GridCapabilityResponse) -> None:
    sys.stdout.write(json.dumps(response.model_dump(mode="json"), ensure_ascii=False, separators=(",", ":")) + "\n")
