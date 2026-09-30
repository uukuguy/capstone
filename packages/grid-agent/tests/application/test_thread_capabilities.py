from __future__ import annotations

from capstone_agent.model_capability import CapstoneModelCapabilityCatalog
from capstone_agent.model_capability_context import ModelCapabilityContextOwner
from capstone_agent.kernel_capability_preparation import (
    AuthorityModelBinding, KernelApplicationProfilePreparer,
)
from capstone_agent.thread_protocol import AttemptSnapshot, ModelContextSnapshot
from capstone_agent.thread_service import AttemptClaim
from capstone_model_capability_spi import ModelCapabilityRegistry
from grid_agent.application.thread_capabilities import (
    PANDAPOWER_PROFILE_DESCRIPTOR,
    register_pandapower_capability,
)
from grid_simulator.engine import Pandapower340Engine
from grid_simulator.models import ModelRegistry


def _claim(revision: str = "revision:sha256:" + "a" * 64) -> AttemptClaim:
    context = ModelContextSnapshot(
        "ctx_grid", "ieee39", revision,
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


def test_pandapower_profile_prepares_real_grid_authority_before_context_activation(tmp_path):
    authority_models = ModelRegistry(Pandapower340Engine())
    revision = authority_models.trusted_revision_ref("ieee39")
    calls = []

    def bind(prepared, context):
        executor = prepared.bindings["grid"].runtime.executor
        opened = executor.invoke("context.open", {"model_id": context.model_id})
        calls.append(opened)
        return AuthorityModelBinding(
            "grid", context.model_id, opened["revision_ref"],
            context.implementation_family, opened["context_ref"],
        )

    preparer = KernelApplicationProfilePreparer(
        workspace_root=tmp_path, model_binder=bind,
    )
    registry = ModelCapabilityRegistry()
    catalog = CapstoneModelCapabilityCatalog(registry)
    owner = ModelCapabilityContextOwner(catalog)
    register_pandapower_capability(catalog, owner, prepare_profile=preparer)
    registry.seal()
    owner.seal()
    context = owner.prepare(_claim(revision))
    assert calls[0]["model"] == "ieee39"
    assert calls[0]["revision_ref"] == revision
    assert context.contributions[0].prepared.model_binding.model_revision == revision
    owner.close()
