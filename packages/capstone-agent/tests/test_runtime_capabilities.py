from __future__ import annotations

import pytest

from capstone_agent.runtime_capabilities import RuntimeCapabilityDescriptor, RuntimeCapabilityRegistry


def test_runtime_capability_registry_keeps_pi_surface_separate_from_domain_profiles() -> None:
    registry = RuntimeCapabilityRegistry()
    registry.register(RuntimeCapabilityDescriptor("web.search", "mcp", "1", "app://search"))
    registry.register(RuntimeCapabilityDescriptor("document-summary", "skill", "2", "project"))
    registry.register(RuntimeCapabilityDescriptor("vendor/plugin", "plugin", "0.1", "package"))

    assert [item.capability_id for item in registry.snapshot()] == [
        "document-summary", "vendor/plugin", "web.search",
    ]
    assert registry.contains("web.search")
    registry.seal()
    with pytest.raises(RuntimeError, match="sealed"):
        registry.register(RuntimeCapabilityDescriptor("another", "skill", "1", "project"))
