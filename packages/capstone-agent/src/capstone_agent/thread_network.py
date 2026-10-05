"""Neutral Thread topology projection boundary."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, runtime_checkable

from .network_diagram import normalize_network_projection
from .thread_service import AttemptClaim


class NetworkProjectionUnavailable(RuntimeError):
    """Safe application diagnostic; raw authority exceptions stay server-side."""

    def __init__(self, code: str) -> None:
        if code not in {"diagram_limit", "projection_source_unavailable", "projection_invalid", "projection_model_mismatch"}:
            raise ValueError("network projection failure code is invalid")
        self.code = code
        super().__init__(code)


@runtime_checkable
class ThreadNetworkProjectionProvider(Protocol):
    """Application-owned provider for one claimed model context."""

    def project(
        self,
        claim: AttemptClaim,
        result_refs: tuple[str, ...],
        evidence_refs: tuple[str, ...],
        tool_events: tuple[Mapping[str, object], ...],
    ) -> Mapping[str, object] | None: ...


@runtime_checkable
class ThreadNetworkRuntimeObserver(Protocol):
    """Optional application observer; native facts stay private until admission."""

    def observe_runtime_event(self, event: Mapping[str, object]) -> None: ...


def normalize_thread_network_projection(
    value: object,
    claim: AttemptClaim,
    admitted_refs: tuple[str, ...],
) -> dict[str, object] | None:
    """Normalize a provider result and bind it to the claimed model context."""

    try:
        normalized = normalize_network_projection(value, admitted_refs=admitted_refs)
    except (TypeError, ValueError):
        return None
    model = normalized["diagram"].get("model")
    if not isinstance(model, Mapping):
        return None
    if (
        model.get("id") != claim.model_context.model_id
        or model.get("revision") != claim.model_context.model_revision
    ):
        return None
    return {
        "schema": normalized["schema"],
        "ordinal": normalized["ordinal"],
        "diagram": normalized["diagram"],
        "layer": normalized["layer"],
    }


__all__ = [
    "ThreadNetworkProjectionProvider",
    "ThreadNetworkRuntimeObserver",
    "normalize_thread_network_projection",
]
