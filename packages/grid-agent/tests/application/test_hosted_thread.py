from __future__ import annotations

from grid_agent.hosted import build_registered_pandapower_thread_application


def test_hosted_pandapower_thread_assembly_registers_default_profile():
    assembly = build_registered_pandapower_thread_application()
    try:
        descriptor = assembly.catalog.resolve("ieee39")
        assert descriptor.implementation_family == "pandapower"
        assert assembly.capability_catalog is not None
        selected = assembly.capability_catalog.resolve(descriptor)
        assert selected.enabled_profiles == (("pandapower-static-analysis", "1.0.1"),)
        assert callable(assembly.runtime_factory)
    finally:
        if assembly.capability_context_owner is not None:
            assembly.capability_context_owner.close()
