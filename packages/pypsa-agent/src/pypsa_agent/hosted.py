"""PyPSA application assembly for the shared Capstone hosted host.

This module is an Authority/Domain Pack adapter.  API and worker lifecycle
remain owned by :mod:`capstone_agent.hosted`.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping

from capstone_agent.hosted import run_hosted_api
from capstone_agent.hosted_validation import select_validation_builder
from capstone_agent.kernel_capability_preparation import AuthorityModelBinding
from capstone_agent.kernel_pi_session import PreparedKernelPiRpcSessionBuilder
from capstone_agent.runtime import build_runtime_host, load_runtime_environment, resolve_harness_llm
from capstone_agent.thread_service import ThreadModelDescriptor
from capstone_agent.thread_application import ThreadApplicationAssembly
from capstone_model_capability_spi import ModelCapabilitySelection
from pypsa_model_authority.catalog import list_registered_models, load_registered_model
from pypsa_model_authority.store import canonical_bytes

from .profile import build_profile
from .thread_capabilities import PYPSA_PROFILE_DESCRIPTOR, build_pypsa_thread_application
from .thread_binding import bind_thread_tool_catalog, verify_bound_model_reference


ROOT = Path(__file__).resolve().parents[4]
DEFAULT_MODEL_ID = "regional-six-bus"


class RegisteredPyPSAThreadCatalog:
    """Expose only registered PyPSA model identities to the Thread contract."""

    default_model_id = DEFAULT_MODEL_ID

    def __init__(self) -> None:
        self._records = {
            str(item["catalog_id"]): item
            for item in list_registered_models()
            if isinstance(item.get("catalog_id"), str)
        }

    def resolve(self, model_id: str | None) -> ThreadModelDescriptor:
        selected = self.default_model_id if model_id is None else model_id
        record = self._records.get(selected)
        if record is None:
            raise LookupError(f"registered PyPSA model was not found: {selected}")
        source_digest = record.get("source_sha256")
        if not isinstance(source_digest, str):
            source_digest = hashlib.sha256(
                canonical_bytes(load_registered_model(selected))
            ).hexdigest()
        return ThreadModelDescriptor(
            model_id=selected,
            model_revision=f"revision:sha256:{source_digest}",
            implementation_family="pypsa",
            authority_model_ref=f"pypsa:{selected}",
            display_name=str(record.get("display_name") or selected),
            diagram_provider_id="pypsa",
        )


def build_registered_pypsa_thread_application() -> ThreadApplicationAssembly:
    """Build the registered PyPSA Thread assembly for Capstone API/worker."""

    catalog = RegisteredPyPSAThreadCatalog()
    validation_builder = select_validation_builder(os.environ, "pypsa")

    def resolve_model(model_id: str) -> Mapping[str, object]:
        descriptor = catalog.resolve(model_id)
        return {
            "model_id": descriptor.model_id,
            "revision_ref": descriptor.model_revision,
            "implementation_family": descriptor.implementation_family,
            "authority_model_ref": descriptor.authority_model_ref,
            "display_name": descriptor.display_name,
            "diagram_provider_id": descriptor.diagram_provider_id,
        }

    def bind_model(prepared: object, context: Any) -> AuthorityModelBinding:
        bindings = getattr(prepared, "bindings", None)
        if not isinstance(bindings, Mapping) or "source" not in bindings:
            raise RuntimeError("PyPSA source binding is unavailable")
        binding = bindings["source"]
        opened = binding.runtime.executor.invoke(
            "model.open", {"catalog_id": context.model_id},
        )
        model_ref = opened.get("model_ref")
        if not isinstance(model_ref, str):
            raise RuntimeError("PyPSA model authority did not return a model reference")
        bind_thread_tool_catalog(binding.runtime.tool_catalog_path, context.model_id)
        return AuthorityModelBinding(
            "source", context.model_id, context.model_revision,
            context.implementation_family, model_ref,
            model_reference_verifier=lambda reference: verify_bound_model_reference(
                binding.runtime.authority, reference,
                model_id=context.model_id, base_ref=model_ref,
            ),
        )

    def build_session(claim, context, profiles):
        if validation_builder is not None:
            return validation_builder(claim, context, profiles)
        environment = load_runtime_environment(ROOT)
        resolved = resolve_harness_llm(ROOT, environment)
        runtime_host = build_runtime_host(ROOT, build_profile(), environment)
        return PreparedKernelPiRpcSessionBuilder(
            runtime_host=runtime_host, resolved_llm=resolved,
            base_environment=environment,
        )(claim, context, profiles)

    workspace_root = Path(
        os.environ.get("CAPSTONE_RUNS_ROOT", str(ROOT / "runs" / "capstone-agent")),
    ) / "thread-workspaces" / "pypsa"
    assembly = build_pypsa_thread_application(
        default_model_id=catalog.default_model_id,
        model_resolver=resolve_model,
        workspace_root=workspace_root,
        model_binder=bind_model,
        session_builder=build_session,
        default_selection=ModelCapabilitySelection(
            (PYPSA_PROFILE_DESCRIPTOR.reference,),
        ),
    )
    from .thread_model_diagram import model_diagram
    set_diagram_provider = getattr(assembly.catalog, "set_diagram_provider", None)
    if not callable(set_diagram_provider):
        raise TypeError("Thread catalog has no diagram provider registration")
    set_diagram_provider(model_diagram)
    return (replace(assembly, ordinary_conversation_enabled=False, turn_router=None)
            if validation_builder is not None else assembly)


def main() -> int:
    return run_hosted_api(build_registered_pypsa_thread_application)


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["RegisteredPyPSAThreadCatalog", "build_registered_pypsa_thread_application", "main"]
