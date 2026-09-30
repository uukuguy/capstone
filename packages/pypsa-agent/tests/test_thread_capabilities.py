from __future__ import annotations

from capstone_agent.model_capability import CapstoneModelCapabilityCatalog
from capstone_agent.model_capability_context import ModelCapabilityContextOwner
from capstone_agent.thread_protocol import AttemptSnapshot, ModelContextSnapshot
from capstone_agent.thread_service import AttemptClaim
from capstone_model_capability_spi import ModelCapabilityRegistry
from pypsa_agent.thread_capabilities import (
    PYPSA_PROFILE_DESCRIPTOR,
    register_pypsa_capability,
)


def _claim() -> AttemptClaim:
    context = ModelContextSnapshot(
        "ctx_pypsa", "scigrid", "revision:sha256:" + "a" * 64,
        "pypsa", "sel_1", (PYPSA_PROFILE_DESCRIPTOR.reference,),
    )
    return AttemptClaim(
        "thr_pypsa", "run_pypsa", AttemptSnapshot("turn_1", "attempt_1", "running", "ctx_pypsa"),
        "send_professional", "inspect", "ctx_pypsa", "sel_1", "lease_1", context,
    )


def test_pypsa_migration_root_registers_existing_application_profile():
    registry = ModelCapabilityRegistry()
    catalog = CapstoneModelCapabilityCatalog(registry)
    owner = ModelCapabilityContextOwner(catalog)
    register_pypsa_capability(catalog, owner)
    registry.seal()
    owner.seal()
    context = owner.prepare(_claim())
    contribution = context.contributions[0]
    assert contribution.descriptor == PYPSA_PROFILE_DESCRIPTOR
    assert contribution.profile.manifest.application_id == "pypsa-business-cases"
    owner.close()
