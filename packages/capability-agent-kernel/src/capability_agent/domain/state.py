"""Namespaced domain-state contracts."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from capability_agent.domain.projection import DomainStateDelta


class DomainContextView(Protocol):
    def model_dump(self, *, mode: str = "python") -> dict[str, object]: ...


class DomainStateAdapter(Protocol):
    def validate(self, *, binding_id: str, state: Mapping[str, object]) -> None: ...

    def merge(
        self,
        *,
        binding_id: str,
        state: Mapping[str, object],
        delta: DomainStateDelta,
    ) -> Mapping[str, object]: ...

    def build_context(
        self, *, binding_id: str, state: Mapping[str, object]
    ) -> DomainContextView: ...


__all__ = ["DomainContextView", "DomainStateAdapter"]
