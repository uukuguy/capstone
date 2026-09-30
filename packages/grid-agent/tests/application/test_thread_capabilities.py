from __future__ import annotations

from capstone_agent.model_capability import CapstoneModelCapabilityCatalog
from capstone_agent.model_capability_context import ModelCapabilityContextOwner
from capstone_agent.thread_protocol import AttemptSnapshot, ModelContextSnapshot
from capstone_agent.thread_service import AttemptClaim
from capstone_model_capability_spi import ModelCapabilityRegistry
from grid_agent.application.thread_capabilities import (
    PANDAPOWER_PROFILE_DESCRIPTOR,
    register_pandapower_capability,
)


def _claim() -> AttemptClaim:
    context = ModelContextSnapshot(
        "ctx_grid", "ieee39", "revision:sha256:" + "a" * 64,
        "pandapower", "sel_1", (PANDAPOWER_PROFILE_DESCRIPTOR.reference,),
    )
    return AttemptClaim(
        "thr_grid", "run_grid", AttemptSnapshot("turn_1", "attempt_1", "running", "ctx_grid"),
        "send_professional", "inspect", "ctx_grid", "sel_1", "lease_1", context,
    )


def test_pandapower_migration_root_registers_existing_application_profile():
    registry = ModelCapabilityRegistry()
    catalog = CapstoneModelCapabilityCatalog(registry)
    owner = ModelCapabilityContextOwner(catalog)
    register_pandapower_capability(catalog, owner)
    registry.seal()
    owner.seal()
    context = owner.prepare(_claim())
    contribution = context.contributions[0]
    assert contribution.descriptor == PANDAPOWER_PROFILE_DESCRIPTOR
    assert contribution.profile.manifest.application_id == "pandapower-static-analysis"
    owner.close()
