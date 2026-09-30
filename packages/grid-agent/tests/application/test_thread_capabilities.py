from __future__ import annotations

from capstone_agent.model_capability import CapstoneModelCapabilityCatalog
from capstone_agent.model_capability_context import ModelCapabilityContextOwner
from capability_agent.runtime.environment import RuntimeHost
from capability_agent.runtime.models import ResolvedLLM, ResolvedLLMConfig, SecretValue
from capability_agent.runtime.lock import PiCommand, PiRuntimeIdentity
from capstone_agent.kernel_capability_preparation import (
    AuthorityModelBinding, KernelApplicationProfilePreparer,
)
from capstone_agent.thread_protocol import AttemptSnapshot, ModelContextSnapshot
from capstone_agent.thread_service import AttemptClaim
from capstone_model_capability_spi import ModelCapabilityRegistry
from capstone_model_capability_spi import ModelCapabilitySelection
from grid_agent.application.thread_capabilities import (
    PANDAPOWER_PROFILE_DESCRIPTOR,
    PreparedKernelPiRpcSessionBuilder,
    PreparedKernelPiSessionFactory,
    build_pandapower_thread_application,
    register_pandapower_capability,
)
from grid_simulator.engine import Pandapower340Engine
from grid_simulator.models import ModelRegistry


class _Session:
    def start(self) -> None:
        return None

    def prompt_and_wait(self, question: str, **kwargs: object) -> str:
        del question, kwargs
        return "answer"

    def stop(self) -> None:
        return None


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


def test_prepared_kernel_pi_factory_exposes_only_prepared_profile_inputs(tmp_path):
    authority_models = ModelRegistry(Pandapower340Engine())
    revision = authority_models.trusted_revision_ref("ieee39")
    calls = []

    def bind(prepared, context):
        executor = prepared.bindings["grid"].runtime.executor
        opened = executor.invoke("context.open", {"model_id": context.model_id})
        return AuthorityModelBinding(
            "grid", context.model_id, opened["revision_ref"],
            context.implementation_family, opened["context_ref"],
        )

    def build_session(claim, context, profiles):
        calls.append((claim, context, profiles))
        assert len(profiles) == 1
        prepared = profiles[0]
        binding = prepared.prepared_application.bindings["grid"]
        assert binding.runtime.tool_catalog_path.is_file()
        assert binding.runtime.guide_index_path.is_file()
        assert prepared.model_binding.context_ref.startswith("context:")
        return _Session()

    assembly = build_pandapower_thread_application(
        default_model_id="ieee39",
        model_resolver=lambda model_id: {
            "model_id": model_id,
            "revision_ref": revision,
            "implementation_family": "pandapower",
        },
        workspace_root=tmp_path,
        model_binder=bind,
        session_builder=build_session,
        default_selection=ModelCapabilitySelection(
            (PANDAPOWER_PROFILE_DESCRIPTOR.reference,)
        ),
    )
    claim = _claim(revision)
    runtime = assembly.runtime_factory(claim)
    runtime.start()
    assert runtime.prompt("inspect", on_event=lambda _event: None) == "answer"
    runtime.stop()
    assert calls[0][0].model_context == claim.model_context
    assembly.capability_context_owner.close()


def test_kernel_pi_rpc_builder_materializes_descriptor_before_process_start(tmp_path):
    authority_models = ModelRegistry(Pandapower340Engine())
    revision = authority_models.trusted_revision_ref("ieee39")

    def bind(prepared, context):
        opened = prepared.bindings["grid"].runtime.executor.invoke(
            "context.open", {"model_id": context.model_id}
        )
        return AuthorityModelBinding(
            "grid", context.model_id, opened["revision_ref"],
            context.implementation_family, opened["context_ref"],
        )

    resolved = ResolvedLLM(
        config=ResolvedLLMConfig(
            provider="openai", model="gpt-5.5", base_url="https://api.openai.com/v1",
            auth_kind="api_key_env", credential_reference="OPENAI_API_KEY",
            timeout_seconds=60, max_retries=0, pi_provider="openai",
            compatibility_profile="openai-responses", descriptor_version="test",
            public_headers={}, field_sources={}, supports_tools=True,
        ),
        secret=SecretValue("test-secret"),
    )
    host = RuntimeHost(
        command=PiCommand(
            argv=("pi",),
            identity=PiRuntimeIdentity(
                path=tmp_path / "pi", source="fixture", package_version="1.0",
                lock_sha256="fixture",
            ),
        ),
        project_pi_dir=tmp_path / "project-pi",
        extension_path=tmp_path / "extension.mjs",
    )
    assembly = build_pandapower_thread_application(
        default_model_id="ieee39",
        model_resolver=lambda model_id: {
            "model_id": model_id, "revision_ref": revision,
            "implementation_family": "pandapower",
        },
        workspace_root=tmp_path / "workspaces",
        model_binder=bind,
        session_builder=PreparedKernelPiRpcSessionBuilder(
            runtime_host=host, resolved_llm=resolved,
            base_environment={"PATH": "/bin", "HOME": "/tmp"},
        ),
        default_selection=ModelCapabilitySelection(
            (PANDAPOWER_PROFILE_DESCRIPTOR.reference,)
        ),
    )
    runtime = assembly.runtime_factory(_claim(revision))
    session = runtime._session  # type: ignore[attr-defined]
    assert session.command.argv[0] == "pi"
    assert "test-secret" not in session.command.argv
    assert session.command.environment["OPENAI_API_KEY"] == "test-secret"
    descriptor = next(
        (path for path in (tmp_path / "workspaces").rglob("runtime-descriptor.json")),
        None,
    )
    assert descriptor is not None and descriptor.is_file()
    runtime.stop()
    assembly.capability_context_owner.close()
