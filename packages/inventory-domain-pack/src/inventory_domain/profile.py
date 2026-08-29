from __future__ import annotations

from capability_agent.domain import DomainManifest, DomainRuntimeProfile

from inventory_domain.authority import InventoryArtifactAuthority
from inventory_domain.capabilities import (
    FilesystemCapabilityContractSource,
    build_inventory_tool_description,
)
from inventory_domain.execution import InventoryctlExecutor
from inventory_domain.projection import InventoryProjectorRegistry
from inventory_domain.resources import InventoryResourceSet


def build_inventory_profile() -> DomainRuntimeProfile:
    resources = InventoryResourceSet.load()
    manifest = DomainManifest(
        domain_id="inventory-readonly",
        version="0.1.0",
        display_name="Read-only Inventory",
        protocol="inventory-capability",
        protocol_version="1.0",
        executable_name="inventoryctl",
        tool_name_prefix="inventory_",
        authority_id="inventoryctl",
        capability_contract_root=resources.capability_contract_root,
        system_policy_path=resources.system_policy_path,
        guide_root=resources.guide_root,
    )
    return DomainRuntimeProfile(
        manifest=manifest,
        contract_source=FilesystemCapabilityContractSource(
            resources.capability_contract_root
        ),
        executor_factory=lambda executable, workspace, timeout: InventoryctlExecutor(
            executable=executable,
            workspace=workspace,
            timeout_seconds=timeout,
        ),
        projector_registry=InventoryProjectorRegistry(),
        authority_factory=InventoryArtifactAuthority,
        tool_description_builder=build_inventory_tool_description,
    )
