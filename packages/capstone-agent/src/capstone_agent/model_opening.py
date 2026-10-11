"""Application-owned initialization shared by every new model entry point."""

from __future__ import annotations

import secrets
from typing import Any, Callable

from capstone_model_capability_spi import ModelCapabilitySelection

from .thread_protocol import ModelContextSnapshot


def initialize_model_context(
    descriptor: Any,
    capability_catalog: Any = None,
    selection: ModelCapabilitySelection | None = None,
    *,
    family_available: Callable[[str], bool] | None = None,
    context_id: str | None = None,
) -> ModelContextSnapshot:
    """Bind a pinned identity once; restoring a context does not call this."""
    if not descriptor.available:
        raise ValueError(descriptor.unavailable_reason or "model_unavailable")
    if family_available is not None and not family_available(descriptor.implementation_family):
        raise ValueError("worker_unavailable")
    resolved = (
        capability_catalog.resolve(descriptor, selection)
        if capability_catalog is not None
        else (ModelCapabilitySelection.empty() if selection is None else selection)
    )
    return ModelContextSnapshot(
        id=context_id or "ctx_" + secrets.token_hex(10),
        model_id=descriptor.model_id,
        model_revision=descriptor.model_revision,
        implementation_family=descriptor.implementation_family,
        selection_revision="sel_0",
        enabled_profiles=resolved.enabled_profiles,
    )
