"""Explicit domain-profile registration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from capability_agent.application.errors import DomainRegistrationError
from capability_agent.application.profile import DomainBinding
from capability_agent.domain.profile import DomainRuntimeProfile


DomainProfileFactory = Callable[[], DomainRuntimeProfile]


class DomainRegistry:
    """Resolve domain profiles only by an explicitly registered exact version."""

    def __init__(self) -> None:
        self._factories: dict[tuple[str, str], DomainProfileFactory] = {}

    def register(
        self, domain_id: str, version: str, factory: DomainProfileFactory
    ) -> None:
        key = (domain_id, version)
        if key in self._factories:
            raise DomainRegistrationError(
                f"domain {domain_id!r} version {version!r} is already registered"
            )
        self._factories[key] = factory

    def resolve(self, domain_id: str, version: str) -> DomainRuntimeProfile:
        key = (domain_id, version)
        factory = self._factories.get(key)
        if factory is None:
            raise DomainRegistrationError(
                f"domain {domain_id!r} version {version!r} is not registered"
            )
        profile = factory()
        manifest = profile.manifest
        if (manifest.domain_id, manifest.version) != key:
            raise DomainRegistrationError(
                "registered domain factory manifest does not match its registration"
            )
        return profile

    def resolve_binding(self, binding: DomainBinding) -> DomainBinding:
        """Return a binding backed by its explicitly registered profile."""
        manifest = binding.profile.manifest
        profile = self.resolve(manifest.domain_id, manifest.version)
        return replace(binding, profile=profile)


__all__ = ["DomainProfileFactory", "DomainRegistry"]
