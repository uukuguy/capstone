from __future__ import annotations

from grid_agent.hosted import build_registered_pandapower_thread_application
from grid_agent import hosted_worker
from grid_simulator.model_catalog import load_model_catalog


def test_hosted_pandapower_thread_assembly_registers_default_profile():
    assembly = build_registered_pandapower_thread_application()
    try:
        descriptor = assembly.catalog.resolve("ieee39")
        assert descriptor.implementation_family == "pandapower"
        assert assembly.capability_catalog is not None
        selected = assembly.capability_catalog.resolve(descriptor)
        assert selected.enabled_profiles == (("pandapower-static-analysis", "1.0.1"),)
        assert callable(assembly.runtime_factory)
        assert set(assembly.catalog.list_model_ids()) == {model["model_id"] for model in load_model_catalog()}
        rts = assembly.catalog.resolve("case24_ieee_rts")
        assert rts.authority_model_ref == "gridctl:case24_ieee_rts"
        assert rts.diagram_provider_id == "gridctl"
    finally:
        if assembly.capability_context_owner is not None:
            assembly.capability_context_owner.close()


def test_grid_hosted_worker_delegates_factory_to_capstone_host(monkeypatch) -> None:
    assembly = object()
    seen = []

    monkeypatch.setattr(
        hosted_worker,
        "build_registered_pandapower_thread_application",
        lambda: assembly,
    )
    monkeypatch.setattr(
        hosted_worker,
        "run_hosted_worker",
        lambda factory: seen.append(factory) or 37,
    )

    assert hosted_worker.main() == 37
    assert seen == [hosted_worker.build_worker_application]
