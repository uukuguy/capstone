"""Domain-owned runtime provisioning contracts."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from capability_agent.domain.execution import CapabilityExecutor

if TYPE_CHECKING:
    from capability_agent.application.profile import DomainBinding


class CredentialLease(Protocol):
    scope_id: str
    credentials: Mapping[str, str]


class PreparedDomainEndpoint(Protocol):
    executor: CapabilityExecutor
    metadata: Mapping[str, object]

    def close(self) -> None: ...


class DomainRuntimeProvisioner(Protocol):
    def prepare(
        self,
        *,
        binding: DomainBinding,
        workspace: Path,
        credentials: CredentialLease,
    ) -> PreparedDomainEndpoint: ...


__all__ = [
    "CredentialLease",
    "DomainRuntimeProvisioner",
    "PreparedDomainEndpoint",
]
