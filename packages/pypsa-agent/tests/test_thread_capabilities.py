from __future__ import annotations

from capstone_agent.model_capability import CapstoneModelCapabilityCatalog
from capstone_agent.model_capability_context import ModelCapabilityContextOwner
from capstone_agent.kernel_capability_preparation import AuthorityModelBinding
from capstone_agent.thread_service import InMemoryThreadService
from capstone_agent.thread_worker import run_pending_attempt
from capstone_agent.thread_protocol import AttemptSnapshot, ModelContextSnapshot
from capstone_agent.thread_application import ThreadApplicationAssembly
from capstone_agent.thread_service import AttemptClaim
from capstone_model_capability_spi import ModelCapabilityRegistry
from pypsa_agent.thread_capabilities import (
    PYPSA_PROFILE_DESCRIPTOR,
    build_pypsa_thread_application,
    register_pypsa_capability,
)


class _Session:
    def start(self) -> None:
        return None

    def prompt_and_wait(self, question: str, **kwargs: object) -> str:
        del question, kwargs
        return "answer"

    def stop(self) -> None:
        return None


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
    assert getattr(getattr(contribution, "profile"), "manifest").application_id == "pypsa-business-cases"
    owner.close()


def test_pypsa_thread_application_is_an_explicit_opt_in_composition_root(tmp_path):
    assembly = build_pypsa_thread_application(
        default_model_id="scigrid",
        model_resolver=lambda model_id: {
            "model_id": model_id,
            "revision_ref": "revision:sha256:" + "a" * 64,
            "implementation_family": "pypsa",
        },
        workspace_root=tmp_path,
        model_binder=lambda _prepared, _context: AuthorityModelBinding(
            "grid", "scigrid", "revision:sha256:" + "a" * 64,
            "pypsa", "context:scigrid",
        ),
        session_builder=lambda _claim, _context, _profiles: _Session(),
    )
    assert isinstance(assembly, ThreadApplicationAssembly)
    assert assembly.catalog.default_model_id == "scigrid"
    assert assembly.capability_context_owner is not None
    assembly.capability_context_owner.close()


def test_pypsa_prepared_profile_runs_through_shared_thread_worker(tmp_path):
    prepared_profiles = []

    def build_session(_claim, _context, profiles):
        prepared_profiles.append(profiles)
        return _Session()

    revision = "revision:sha256:" + "a" * 64
    assembly = build_pypsa_thread_application(
        default_model_id="scigrid",
        model_resolver=lambda model_id: {
            "model_id": model_id,
            "revision_ref": revision,
            "implementation_family": "pypsa",
        },
        workspace_root=tmp_path,
        model_binder=lambda _prepared, context: AuthorityModelBinding(
            "source", context.model_id, context.model_revision,
            context.implementation_family, "context:scigrid",
        ),
        session_builder=build_session,
        default_selection=None,
    )
    service = InMemoryThreadService.from_document({
        "schema": "capstone-thread-snapshot/1", "thread_id": "thr_pypsa",
        "run": {"run_id": "run_pypsa", "state": "open"},
        "active_model_context": _claim().model_context.to_document(),
        "active_grid_page_id": "page_scigrid", "current_attempt": None,
        "last_event_seq": 0, "base_event_seq": 0,
    })
    service.submit_command({
        "schema": "capstone-command/1", "command_id": "cmd_pypsa_1",
        "idempotency_key": "idem_pypsa_1", "thread_id": "thr_pypsa",
        "run_id": "run_pypsa", "kind": "send_ordinary", "expected_event_seq": 0,
        "payload": {"text": "inspect registered model"},
    })
    result = run_pending_attempt(service, assembly.runtime_factory, worker_id="pypsa-fixture")
    assert result is not None and result.status == "completed"
    assert result.answer == "answer"
    assert len(prepared_profiles) == 1
    assert len(prepared_profiles[0]) == 1
    assert prepared_profiles[0][0].descriptor == PYPSA_PROFILE_DESCRIPTOR
    assert assembly.capability_context_owner is not None
    assembly.capability_context_owner.close()
