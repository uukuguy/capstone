from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class VerifiedInvocation:
    capability: str
    projector_id: str
    result_kind: str | None
    result: Mapping[str, Any]
    arguments: Mapping[str, Any]
    turn_id: str
    result_paths: Mapping[str, str]
    active_revision_ref: str | None


class DomainStateDelta(Protocol):
    def model_dump(self, *, mode: str = "python") -> dict[str, Any]: ...


class DomainProjector(Protocol):
    projector_id: str

    def project(self, invocation: VerifiedInvocation) -> DomainStateDelta: ...


class DomainProjectorRegistry(Protocol):
    def require(self, projector_id: str) -> DomainProjector: ...
