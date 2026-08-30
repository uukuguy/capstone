"""Legacy RPC transport seam backed by the generic Pi RPC client."""

from __future__ import annotations

from typing import Any

from capability_agent.runtime.rpc import (
    CAPTURE_FATAL_EXIT_CODE,
    CAPTURE_FATAL_MARKER,
    CaptureAdapter,
    PiCaptureIntegrityError,
    PiProtocolError,
    PiRpcClient as _PiRpcClient,
    RpcWorkspace,
    SemanticEventCallback,
    TRACEABLE_RPC_TYPES,
)
from grid_agent.trajectory.capture import CaptureIntegrityError


class PiRpcClient(_PiRpcClient):
    """Preserve the historical capture exception while sharing transport code."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("capture_error_type", CaptureIntegrityError)
        super().__init__(*args, **kwargs)


__all__ = [
    "CAPTURE_FATAL_EXIT_CODE",
    "CAPTURE_FATAL_MARKER",
    "CaptureAdapter",
    "PiCaptureIntegrityError",
    "PiProtocolError",
    "PiRpcClient",
    "RpcWorkspace",
    "SemanticEventCallback",
    "TRACEABLE_RPC_TYPES",
]
