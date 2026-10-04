"""Explicit migration registration for the existing PyPSA application."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import cast

from capstone_agent.kernel_capability_preparation import (
    AuthorityModelBinding,
    KernelApplicationProfilePreparer,
)
from capstone_agent.kernel_pi_session import (
    PreparedKernelPiSessionFactory,
    PreparedKernelSessionBuilder,
)
from capstone_agent.model_capability import CapstoneModelCapabilityCatalog, ModelCapabilityProfileInfo
from capstone_agent.thread_catalog import AuthorityThreadModelCatalog
from capstone_agent.model_capability_context import ModelCapabilityContextOwner, register_application_profile
from capstone_model_capability_spi import ModelCapabilityDescriptor
from capstone_model_capability_spi import ModelCapabilityRegistry, ModelCapabilitySelection
from capstone_agent.thread_protocol import ModelContextSnapshot
from capstone_agent.thread_application import ThreadApplicationAssembly

from .profile import build_profile
from .network_view import build_pypsa_thread_network_provider
from pypsa_model_authority.catalog import list_registered_models


PYPSA_PROFILE_DESCRIPTOR = ModelCapabilityDescriptor("pypsa-business-cases", "1.0.0")
PYPSA_PROFILE_INFO = ModelCapabilityProfileInfo(
    descriptor=PYPSA_PROFILE_DESCRIPTOR,
    display_name="PyPSA Business Cases",
    implementation_families=("pypsa",),
)


def build_pypsa_thread_model_catalog(
    *,
    model_resolver: Callable[[str], Mapping[str, object]],
    default_model_id: str = "regional-six-bus",
) -> AuthorityThreadModelCatalog:
    """Expose the Authority's real catalog IDs to the Capstone Thread seam."""

    model_ids = tuple(
        cast(str, entry["catalog_id"]) for entry in list_registered_models()
        if isinstance(entry.get("catalog_id"), str)
    )
    if default_model_id not in model_ids:
        raise ValueError("default_model_id is not a registered PyPSA model")
    return AuthorityThreadModelCatalog(
        default_model_id=default_model_id,
        model_ids=model_ids,
        resolver=model_resolver,
    )


def register_pypsa_capability(
    catalog: CapstoneModelCapabilityCatalog,
    owner: ModelCapabilityContextOwner,
    *,
    prepare_profile: Callable[[object, ModelContextSnapshot], object] | None = None,
) -> None:
    """Register the current trusted two-binding profile for app assembly."""

    register_application_profile(
        owner,
        catalog,
        PYPSA_PROFILE_INFO,
        build_profile,
        trust_source="pypsa-agent-migration-assembly",
        prepare_profile=prepare_profile,
    )


def build_pypsa_thread_application(
    *,
    default_model_id: str,
    model_resolver: Callable[[str], Mapping[str, object]],
    workspace_root: Path,
    model_binder: Callable[[object, ModelContextSnapshot], AuthorityModelBinding],
    session_builder: PreparedKernelSessionBuilder,
    default_selection: ModelCapabilitySelection | None = None,
    runtime_mode: str = "capstone",
) -> ThreadApplicationAssembly:
    """Build an opt-in Thread assembly for the existing PyPSA profile.

    PyPSA model identifiers and Authority binding stay application-owned.  The
    helper only wires the registered profile into the neutral prepared Context
    and Pi session seam; it does not alter the existing PyPSA application path.
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
    register_pypsa_capability(
        catalog,
        owner,
        prepare_profile=cast(
            Callable[[object, ModelContextSnapshot], object], preparer,
        ),
    )
    if default_selection is not None:
        catalog.set_family_default("pypsa", default_selection)
    registry.seal()
    owner.seal()
    model_catalog = build_pypsa_thread_model_catalog(
        model_resolver=model_resolver,
        default_model_id=default_model_id,
    )
    return ThreadApplicationAssembly.from_prepared_authority(
        default_model_id=default_model_id,
        model_resolver=model_resolver,
        model_catalog=model_catalog,
        capability_catalog=catalog,
        capability_context_owner=owner,
        session_factory=PreparedKernelPiSessionFactory(session_builder),
        runtime_mode=runtime_mode,
        network_projection_factory=lambda _claim, context: build_pypsa_thread_network_provider(context),
    )


__all__ = [
    "PYPSA_PROFILE_DESCRIPTOR",
    "PYPSA_PROFILE_INFO",
    "build_pypsa_thread_model_catalog",
    "build_pypsa_thread_application",
    "register_pypsa_capability",
]
