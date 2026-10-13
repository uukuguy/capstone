"""Capstone hosted composition root for the registered pandapower authority.

The neutral capstone CLI accepts an application-owned model catalog. This
entry point supplies the catalog from the registered grid simulator authority
without making capstone-agent import a domain implementation.
"""

from __future__ import annotations

import os
import re
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Mapping

from capstone_agent.hosted import run_hosted_api
from capstone_agent.application import EmptyCredentialBroker
from capstone_agent.hosted_validation import select_validation_builder
from capstone_agent.kernel_capability_preparation import AuthorityModelBinding
from capstone_agent.kernel_pi_session import PreparedKernelPiRpcSessionBuilder
from capstone_agent.runtime import build_runtime_host, load_runtime_environment, resolve_harness_llm
from capstone_agent.thread_service import ThreadModelDescriptor
from capstone_agent.thread_catalog import AuthorityThreadModelCatalog
from capstone_model_capability_spi import ModelCapabilitySelection
from grid_simulator.engine import Pandapower340Engine
from grid_simulator.models import ModelRegistry

from grid_agent.application.profile import build_pandapower_application_profile
from grid_agent.application.thread_capabilities import (
    PANDAPOWER_PROFILE_DESCRIPTOR,
    build_pandapower_thread_application,
)
from grid_agent.thread_binding import bind_thread_tool_catalog
from grid_agent.thread_model_metadata import model_display_name


class RegisteredPandapowerThreadCatalog:
    """Resolve exact model revisions from the registered simulator catalog."""

    default_model_id = "ieee39"

    def __init__(self) -> None:
        self._registry = ModelRegistry(Pandapower340Engine())

    def resolve(self, model_id: str | None) -> ThreadModelDescriptor:
        selected = self.default_model_id if model_id is None else model_id
        model = self._registry.get(selected)
        return ThreadModelDescriptor(
            model_id=model.model_id,
            model_revision=self._registry.trusted_revision_ref(model.model_id),
            implementation_family=model.engine,
        )


def _read_model_metadata(executor: Any, *, model_id: str, revision_ref: str,
                         context_ref: str,
                         opened_metadata: Mapping[str, object] | None = None) -> Mapping[str, object]:
    if (opened_metadata is not None and opened_metadata.get('model') == model_id
        and opened_metadata.get('revision_ref') == revision_ref
        and opened_metadata.get('context_ref') == context_ref
        and isinstance(opened_metadata.get('overview'), list)):
        return opened_metadata
    try:
        metadata = executor.invoke("context.get", {"context_ref": context_ref, "include_overview": True})
    except Exception:
        # Optional preparation data must not prevent later task execution.
        return {"status": "unavailable", "reason": "model_metadata_lookup_failed"}
    if (not isinstance(metadata, Mapping) or metadata.get("model") != model_id
        or metadata.get("revision_ref") != revision_ref or metadata.get("context_ref") != context_ref):
        return {"status": "unavailable", "reason": "model_metadata_identity_mismatch"}
    return metadata


def _warm_runtime_catalog() -> None:
    """Verify and retain immutable capabilities before accepting model requests."""
    profile = build_pandapower_application_profile()
    with TemporaryDirectory(prefix='capstone-capability-check-') as directory:
        for binding in profile.domains:
            provisioner = binding.profile.provisioner
            if provisioner is None:
                raise RuntimeError('registered capability provisioner is unavailable')
            endpoint = provisioner.prepare(binding=binding, workspace=Path(directory) / binding.binding_id,
                credentials=EmptyCredentialBroker().issue(binding_id=binding.binding_id, scope=binding.credential_scope))
            try:
                description = endpoint.executor.invoke('environment.describe', {})
                binding.profile.manifest.assert_environment_compatible(description)
            finally:
                endpoint.close()


def build_registered_pandapower_thread_application():
    """Build the hosted pandapower Thread catalog and Pi Harness seam."""

    root = Path(__file__).resolve().parents[4]
    models = ModelRegistry(Pandapower340Engine())
    if re.fullmatch(r'[0-9a-f]{64}', os.environ.get('CAPSTONE_RUNTIME_ARTIFACT_SHA256', '')):
        _warm_runtime_catalog()
    validation_builder = select_validation_builder(os.environ, "pandapower")

    def resolve_model(model_id: str) -> Mapping[str, object]:
        model = models.get(model_id)
        reason = models.operator_diagram_unavailable_reason(model.model_id)
        return {
            "model_id": model.model_id,
            "revision_ref": models.trusted_revision_ref(model.model_id),
            "implementation_family": model.engine,
            "authority_model_ref": f"gridctl:{model.model_id}",
            "display_name": model_display_name(model.title, model.model_id),
            "diagram_provider_id": "gridctl",
            "available": reason is None,
            **({"unavailable_reason": reason} if reason else {}),
        }

    def bind_model(prepared: object, context: Any) -> AuthorityModelBinding:
        bindings = getattr(prepared, "bindings", None)
        if not isinstance(bindings, Mapping) or "grid" not in bindings:
            raise TypeError("prepared application has no grid binding")
        binding = bindings["grid"]
        opened = binding.runtime.executor.invoke(
            "context.open", {"model_id": context.model_id, "include_overview": True},
        )
        model_binding = AuthorityModelBinding(
            "grid", context.model_id, opened["revision_ref"],
            context.implementation_family, opened["context_ref"],
            model_metadata=_read_model_metadata(binding.runtime.executor,
                model_id=context.model_id, revision_ref=opened["revision_ref"], context_ref=opened["context_ref"],
                opened_metadata=opened),
        )
        bind_thread_tool_catalog(binding.runtime.tool_catalog_path, model_binding,
                                authority_workspace=binding.runtime.authority.workspace_root)
        return model_binding

    def build_session(claim, context, profiles):
        if validation_builder is not None:
            return validation_builder(claim, context, profiles)
        environment = load_runtime_environment(root)
        resolved = resolve_harness_llm(root, environment)
        if claim.turn_plan is not None and claim.turn_plan.route == "ordinary":
            resolved = resolve_recognition_llm(root, environment, resolved)
        runtime_host = build_runtime_host(
            root, build_pandapower_application_profile(), environment,
        )
        return PreparedKernelPiRpcSessionBuilder(
            runtime_host=runtime_host, resolved_llm=resolved,
            base_environment=environment,
            research_enabled=os.environ.get("CAPSTONE_AUTONOMOUS_RESEARCH") == "1",
        )(claim, context, profiles)

    workspace_root = Path(
        os.environ.get("CAPSTONE_RUNS_ROOT", str(root / "runs" / "capstone-agent")),
    ) / "thread-workspaces"
    assembly = build_pandapower_thread_application(
        default_model_id="ieee39",
        model_resolver=resolve_model,
        workspace_root=workspace_root,
        retain_context_workspace=os.environ.get("CAPSTONE_AUTONOMOUS_RESEARCH") == "1",
        model_binder=bind_model,
        session_builder=build_session,
        model_catalog=AuthorityThreadModelCatalog(
            default_model_id="ieee39", resolver=resolve_model,
            model_ids=tuple(model.model_id for model in models.list()),
        ),
        default_selection=ModelCapabilitySelection(
            (PANDAPOWER_PROFILE_DESCRIPTOR.reference,),
        ),
    )
    from .thread_model_diagram import model_diagram
    set_diagram_provider = getattr(assembly.catalog, "set_diagram_provider", None)
    if not callable(set_diagram_provider):
        raise TypeError("Thread catalog has no diagram provider registration")
    set_diagram_provider(model_diagram)
    if validation_builder is not None:
        return replace(assembly, ordinary_conversation_enabled=False, turn_router=None)
    if os.environ.get("CAPSTONE_AUTONOMOUS_RESEARCH") == "1":
        from capstone_agent.turn_router import ResearchTurnRouter
        return replace(assembly, turn_router=ResearchTurnRouter())
    from capstone_agent.lightweight_turn_router import build_lightweight_router
    from capstone_agent.runtime import resolve_recognition_llm
    environment = load_runtime_environment(root)
    def recognition_llm():
        return resolve_recognition_llm(root, environment, resolve_harness_llm(root, environment))
    router = build_lightweight_router(
        runtime_host=build_runtime_host(root, build_pandapower_application_profile(), environment),
        resolved_llm_factory=recognition_llm, environment=environment)
    return replace(assembly, turn_router=router)


def main() -> int:
    """Delegate API process control to the Capstone application host."""

    return run_hosted_api(build_registered_pandapower_thread_application)


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "RegisteredPandapowerThreadCatalog",
    "build_registered_pandapower_thread_application",
    "main",
]
