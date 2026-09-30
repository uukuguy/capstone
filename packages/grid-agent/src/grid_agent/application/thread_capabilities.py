"""Explicit migration registration for the existing pandapower application.

This module is an application composition hook only.  The compatibility CLI
does not call it implicitly; a future Capstone composition root may opt in.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import cast

from capstone_agent.harness import PiPromptSession
from capstone_agent.kernel_capability_preparation import (
    AuthorityModelBinding,
    KernelApplicationProfilePreparer,
    PreparedKernelApplicationProfile,
)
from capstone_agent.model_capability import CapstoneModelCapabilityCatalog, ModelCapabilityProfileInfo
from capstone_agent.model_capability_context import (
    ModelCapabilityContextOwner,
    PreparedModelCapabilityContext,
    register_application_profile,
)
from capstone_model_capability_spi import ModelCapabilityDescriptor
from capstone_model_capability_spi import ModelCapabilityRegistry, ModelCapabilitySelection
from capstone_agent.thread_protocol import ModelContextSnapshot
from capstone_agent.thread_application import ThreadApplicationAssembly
from capstone_agent.thread_service import AttemptClaim

from .profile import build_pandapower_application_profile


PANDAPOWER_PROFILE_DESCRIPTOR = ModelCapabilityDescriptor(
    "pandapower-static-analysis", "1.0.1",
)
PANDAPOWER_PROFILE_INFO = ModelCapabilityProfileInfo(
    descriptor=PANDAPOWER_PROFILE_DESCRIPTOR,
    display_name="Pandapower Static Analysis",
    implementation_families=("pandapower",),
)


PreparedKernelSessionBuilder = Callable[
    [AttemptClaim, PreparedModelCapabilityContext,
     tuple[PreparedKernelApplicationProfile, ...]],
    PiPromptSession,
]


class PreparedKernelPiSessionFactory:
    """Validate prepared Kernel contributions before constructing a Pi session.

    This adapter belongs to the application composition root.  It is the only
    migration layer that knows the legacy Kernel preparation result shape;
    Thread and Harness receive only the returned Pi-compatible session.  The
    builder can materialize the Kernel runtime descriptor and start Pi using
    the selected binding's tool catalog and Authority endpoint.
    """

    def __init__(self, builder: PreparedKernelSessionBuilder) -> None:
        if not callable(builder):
            raise TypeError("builder must be callable")
        self._builder = builder

    def __call__(
        self,
        claim: AttemptClaim,
        context: PreparedModelCapabilityContext,
    ) -> PiPromptSession:
        if not isinstance(claim, AttemptClaim):
            raise TypeError("claim must be an AttemptClaim")
        if not isinstance(context, PreparedModelCapabilityContext):
            raise TypeError("context must be a PreparedModelCapabilityContext")
        if context.model_context != claim.model_context:
            raise ValueError("prepared Kernel context does not match Attempt snapshot")
        prepared = tuple(
            _require_prepared_kernel_profile(contribution, claim.model_context)
            for contribution in context.contributions
        )
        session = self._builder(claim, context, prepared)
        if not callable(getattr(session, "start", None)) or not callable(
            getattr(session, "prompt_and_wait", None)
        ) or not callable(getattr(session, "stop", None)):
            raise TypeError("prepared Kernel session builder returned an invalid session")
        return session


def build_pandapower_thread_application(
    *,
    default_model_id: str,
    model_resolver: Callable[[str], Mapping[str, object]],
    workspace_root: Path,
    model_binder: Callable[[object, ModelContextSnapshot], AuthorityModelBinding],
    session_builder: PreparedKernelSessionBuilder,
    default_selection: ModelCapabilitySelection | None = None,
    runtime_mode: str = "capstone",
) -> ThreadApplicationAssembly:
    """Build an opt-in Thread assembly for the existing pandapower profile.

    The compatibility application never calls this helper implicitly.  The
    caller supplies the Authority model resolver/binder and the final Pi
    session builder, so credentials, provider selection, and runtime asset
    locations remain application-owned.  An optional family default keeps the
    empty-profile assembly useful for preparation diagnostics.
    """

    if not isinstance(workspace_root, Path):
        raise TypeError("workspace_root must be a Path")
    if default_selection is not None and not isinstance(
        default_selection, ModelCapabilitySelection
    ):
        raise TypeError("default_selection must be a ModelCapabilitySelection")
    registry = ModelCapabilityRegistry()
    catalog = CapstoneModelCapabilityCatalog(registry)
    owner = ModelCapabilityContextOwner(catalog)
    preparer = KernelApplicationProfilePreparer(
        workspace_root=workspace_root, model_binder=model_binder,
    )
    register_pandapower_capability(
        catalog,
        owner,
        prepare_profile=cast(
            Callable[[object, ModelContextSnapshot], object], preparer,
        ),
    )
    if default_selection is not None:
        catalog.set_family_default("pandapower", default_selection)
    registry.seal()
    owner.seal()
    factory = PreparedKernelPiSessionFactory(session_builder)
    return ThreadApplicationAssembly.from_prepared_authority(
        default_model_id=default_model_id,
        model_resolver=model_resolver,
        capability_catalog=catalog,
        capability_context_owner=owner,
        session_factory=factory,
        runtime_mode=runtime_mode,
    )


def _require_prepared_kernel_profile(
    contribution: object, model_context: ModelContextSnapshot,
) -> PreparedKernelApplicationProfile:
    prepared = getattr(contribution, "prepared", None)
    if not isinstance(prepared, PreparedKernelApplicationProfile):
        raise TypeError("Thread capability contribution is not Kernel-prepared")
    if prepared.closed:
        raise RuntimeError("Kernel-prepared profile is already closed")
    if prepared.model_binding.model_id != model_context.model_id:
        raise ValueError("Kernel-prepared model does not match Thread snapshot")
    if prepared.model_binding.model_revision != model_context.model_revision:
        raise ValueError("Kernel-prepared revision does not match Thread snapshot")
    if prepared.model_binding.implementation_family != model_context.implementation_family:
        raise ValueError("Kernel-prepared family does not match Thread snapshot")
    bindings = getattr(prepared.prepared_application, "bindings", None)
    if not isinstance(bindings, Mapping):
        raise TypeError("Kernel-prepared application bindings are unavailable")
    binding = bindings.get(prepared.model_binding.binding_id)
    if binding is None:
        raise ValueError("Kernel-prepared Authority binding is unavailable")
    runtime = getattr(binding, "runtime", None)
    for name in ("tool_catalog_path", "guide_index_path"):
        path = getattr(runtime, name, None)
        if not isinstance(path, Path) or not path.is_file():
            raise RuntimeError(f"Kernel-prepared {name} is unavailable")
    endpoint = getattr(binding, "endpoint", None)
    if not callable(getattr(getattr(endpoint, "executor", None), "invoke", None)):
        raise RuntimeError("Kernel-prepared Authority endpoint is unavailable")
    return prepared


def register_pandapower_capability(
    catalog: CapstoneModelCapabilityCatalog,
    owner: ModelCapabilityContextOwner,
    *,
    prepare_profile: Callable[[object, ModelContextSnapshot], object] | None = None,
) -> None:
    """Register the current trusted profile for an explicit app assembly."""

    register_application_profile(
        owner,
        catalog,
        PANDAPOWER_PROFILE_INFO,
        build_pandapower_application_profile,
        trust_source="grid-agent-migration-assembly",
        prepare_profile=prepare_profile,
    )


__all__ = [
    "PANDAPOWER_PROFILE_DESCRIPTOR",
    "PANDAPOWER_PROFILE_INFO",
    "PreparedKernelPiSessionFactory",
    "build_pandapower_thread_application",
    "register_pandapower_capability",
]
