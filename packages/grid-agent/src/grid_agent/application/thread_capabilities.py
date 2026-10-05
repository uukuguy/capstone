"""Explicit migration registration for the existing pandapower application.

This module is an application composition hook only.  The compatibility CLI
does not call it implicitly; a future Capstone composition root may opt in.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import cast

from capstone_agent.kernel_capability_preparation import (
    AuthorityModelBinding,
    KernelApplicationProfilePreparer,
)
from capstone_agent.kernel_pi_session import (
    PreparedKernelPiRpcSessionBuilder,
    PreparedKernelPiSessionFactory,
    PreparedKernelSessionBuilder,
)
from capstone_agent.model_capability import CapstoneModelCapabilityCatalog, ModelCapabilityProfileInfo
from capstone_agent.model_capability_context import (
    ModelCapabilityContextOwner,
    register_application_profile,
)
from capstone_model_capability_spi import ModelCapabilityDescriptor
from capstone_model_capability_spi import ModelCapabilityRegistry, ModelCapabilitySelection
from capstone_agent.thread_protocol import ModelContextSnapshot
from capstone_agent.thread_application import ThreadApplicationAssembly
from capstone_agent.thread_service import ThreadModelCatalog

from .profile import build_pandapower_application_profile
from ..thread_network_view import build_pandapower_thread_network_provider


PANDAPOWER_PROFILE_DESCRIPTOR = ModelCapabilityDescriptor(
    "pandapower-static-analysis", "1.0.1",
)
PANDAPOWER_PROFILE_INFO = ModelCapabilityProfileInfo(
    descriptor=PANDAPOWER_PROFILE_DESCRIPTOR,
    display_name="Pandapower Static Analysis",
    implementation_families=("pandapower",),
)


def build_pandapower_thread_application(
    *,
    default_model_id: str,
    model_resolver: Callable[[str], Mapping[str, object]],
    workspace_root: Path,
    model_binder: Callable[[object, ModelContextSnapshot], AuthorityModelBinding],
    session_builder: PreparedKernelSessionBuilder,
    model_catalog: ThreadModelCatalog | None = None,
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
        model_catalog=model_catalog,
        capability_catalog=catalog,
        capability_context_owner=owner,
        session_factory=factory,
        runtime_mode=runtime_mode,
        network_projection_factory=lambda _claim, context: build_pandapower_thread_network_provider(context),
    )


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
    "PreparedKernelPiRpcSessionBuilder",
    "PreparedKernelPiSessionFactory",
    "build_pandapower_thread_application",
    "register_pandapower_capability",
]
