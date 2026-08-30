from __future__ import annotations

import pytest

from capability_agent.application.errors import ApplicationConfigurationError

from grid_agent.application.registry import (
    ApplicationRegistry,
    build_trusted_application_registry,
)


def test_trusted_registry_resolves_only_the_explicit_pandapower_application() -> None:
    registry = build_trusted_application_registry()

    profile = registry.resolve("pandapower-static-analysis")

    assert profile.manifest.application_id == "pandapower-static-analysis"
    assert profile.manifest.version == "1.0.1"
    assert registry.application_ids() == ("pandapower-static-analysis",)


@pytest.mark.parametrize(
    "application_id",
    ("inventory", "unknown", "pandapower-static-analysis/../escape"),
)
def test_trusted_registry_rejects_unregistered_application(application_id: str) -> None:
    registry = build_trusted_application_registry()

    with pytest.raises(ApplicationConfigurationError, match="not registered"):
        registry.resolve(application_id)


def test_registry_rejects_duplicate_exact_registration() -> None:
    registry = ApplicationRegistry()
    factory = build_trusted_application_registry().resolve
    registry.register("pandapower-static-analysis", "1.0.1", lambda: factory("pandapower-static-analysis"))

    with pytest.raises(ApplicationConfigurationError, match="already registered"):
        registry.register("pandapower-static-analysis", "1.0.1", lambda: factory("pandapower-static-analysis"))
