"""Domain-specific context and report presentation contracts."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from capability_agent.domain.state import DomainContextView


class PresentationProvider(Protocol):
    def render_context(self, context: DomainContextView) -> Mapping[str, object]: ...

    def render_report(self, context: DomainContextView) -> str: ...


__all__ = ["PresentationProvider"]
