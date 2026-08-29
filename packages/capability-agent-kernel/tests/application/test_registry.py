from __future__ import annotations

import pytest

from capability_agent import DomainRegistrationError, DomainRegistry


def test_domain_registry_resolves_only_exact_registration(inventory_profile) -> None:
    profile, _ = inventory_profile
    registry = DomainRegistry()
    registry.register("inventory-readonly", "1.0.0", lambda: profile)

    assert registry.resolve("inventory-readonly", "1.0.0") is profile


def test_domain_registry_rejects_duplicate_registration(inventory_profile) -> None:
    profile, _ = inventory_profile
    registry = DomainRegistry()
    registry.register("inventory-readonly", "1.0.0", lambda: profile)

    with pytest.raises(DomainRegistrationError, match="already registered"):
        registry.register("inventory-readonly", "1.0.0", lambda: profile)


def test_domain_registry_rejects_factory_with_different_identity(
    inventory_profile,
) -> None:
    profile, _ = inventory_profile
    registry = DomainRegistry()
    registry.register("different-domain", "1.0.0", lambda: profile)

    with pytest.raises(DomainRegistrationError, match="manifest does not match"):
        registry.resolve("different-domain", "1.0.0")


@pytest.mark.parametrize(
    ("domain_id", "version"),
    [("missing", "1.0.0"), ("inventory-readonly", "2.0.0")],
)
def test_domain_registry_rejects_missing_exact_registration(
    inventory_profile, domain_id: str, version: str
) -> None:
    profile, _ = inventory_profile
    registry = DomainRegistry()
    registry.register("inventory-readonly", "1.0.0", lambda: profile)

    with pytest.raises(DomainRegistrationError, match="not registered"):
        registry.resolve(domain_id, version)
