"""Domain-owned output contracts."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from capability_agent.domain.state import DomainContextView


class CommittedAnswer(Protocol):
    @property
    def answer_ref(self) -> str: ...


class DomainOutputContract(Protocol):
    schema_id: str

    def build(
        self,
        *,
        binding_id: str,
        context: DomainContextView,
        committed_answers: tuple[CommittedAnswer, ...],
    ) -> Mapping[str, object]: ...

    def validate(self, payload: Mapping[str, object]) -> None: ...


__all__ = ["CommittedAnswer", "DomainOutputContract"]
