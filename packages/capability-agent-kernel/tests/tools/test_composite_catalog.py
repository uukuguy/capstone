from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from capability_agent.tools.catalog import (
    BoundDomainCatalog,
    CapabilityKey,
    CompositeToolCatalog,
    CoreToolCatalog,
    ToolCatalog,
    ToolCatalogError,
    ToolDocument,
)


def _contract(
    *,
    capability_id: str = "context.open",
    tool_name: str = "grid_context_open",
) -> dict[str, object]:
    return {
        "id": capability_id,
        "tool_name": tool_name,
        "availability": "published",
        "context_effect": {
            "requires_state": [],
            "consumes_state": [],
            "produces_state": [],
            "invalidates_state": [],
            "result_kind": "context",
            "projector": "context",
        },
        "purpose": "Open bounded domain context.",
        "applies_to": ["domain context"],
        "not_for": ["arbitrary file access"],
        "input_schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {},
        },
        "requires": [],
        "produces": ["bounded context"],
        "common_next": [],
        "recovery": {},
    }


def _domain(
    binding_id: str,
    namespace: str,
    *,
    capability_id: str = "context.open",
    tool_name: str | None = None,
    guide_tool_name: str | None = None,
    context_tool_name: str | None = None,
) -> BoundDomainCatalog:
    return BoundDomainCatalog.fixture(
        binding_id,
        namespace,
        (
            _contract(
                capability_id=capability_id,
                tool_name=tool_name or f"{namespace}context_open",
            ),
        ),
        authority_id=f"{binding_id}-authority",
        protocol=f"{binding_id}-capability",
        protocol_version="1.0",
        guide_tool_name=guide_tool_name,
        context_tool_name=context_tool_name,
    )


def test_tool_catalog_does_not_create_a_domain_decision_tool() -> None:
    catalog = ToolCatalog.from_documents((_contract(),), tool_name_prefix="grid_")

    assert [tool.name for tool in catalog.tools] == ["grid_context_open"]


def test_generic_core_catalog_requires_the_agent_namespace() -> None:
    with pytest.raises(ToolCatalogError, match="agent_"):
        CoreToolCatalog.default(namespace="grid_")


def test_composite_catalog_rejects_a_directly_constructed_non_agent_core() -> None:
    core = CoreToolCatalog(
        namespace="grid_",
        tools=(
            ToolDocument(
                name="grid_record_decision",
                capability="grid_record_decision",
                description="Legacy alias must not enter the generic core.",
                input_schema={"type": "object"},
            ),
        ),
    )

    with pytest.raises(ToolCatalogError, match="agent_"):
        CompositeToolCatalog.build(core=core, domains=(_domain("grid", "grid_"),))


def test_composite_catalog_rejects_non_agent_tools_in_the_generic_core() -> None:
    core = CoreToolCatalog(
        namespace="agent_",
        tools=(
            ToolDocument(
                name="grid_record_decision",
                capability="grid_record_decision",
                description="Legacy alias must not enter the generic core.",
                input_schema={"type": "object"},
            ),
        ),
    )

    with pytest.raises(ToolCatalogError, match="agent_"):
        CompositeToolCatalog.build(core=core, domains=(_domain("grid", "grid_"),))


def test_composite_catalog_keeps_core_tools_out_of_domain_catalog() -> None:
    catalog = CompositeToolCatalog.build(
        core=CoreToolCatalog.default(namespace="agent_"),
        domains=(_domain("grid", "grid_"),),
    )

    assert [tool.name for tool in catalog.core_tools] == [
        "agent_context_get",
        "agent_record_decision",
    ]
    assert [tool.name for tool in catalog.domain_tools] == ["grid_context_open"]
    bound = catalog.require("grid_context_open")
    assert bound.key == CapabilityKey("grid", "context.open")
    assert bound.authority_id == "grid-authority"
    assert bound.protocol == "grid-capability"
    assert bound.protocol_version == "1.0"


def test_composite_catalog_routes_two_bindings_by_unique_tool_name() -> None:
    inventory = _domain(
        "inventory",
        "inventory_",
        capability_id="asset.list",
        tool_name="inventory_asset_list",
        guide_tool_name="inventory_guide_open",
    )
    grid = _domain(
        "grid",
        "grid_",
        tool_name="grid_analysis_powerflow_ac",
        guide_tool_name="grid_guide_open",
    )

    catalog = CompositeToolCatalog.build(
        core=CoreToolCatalog.default(namespace="agent_"),
        domains=(inventory, grid),
    )

    assert catalog.require("inventory_asset_list").key.binding_id == "inventory"
    assert catalog.require("grid_analysis_powerflow_ac").key.binding_id == "grid"
    assert catalog.guide_tool_bindings == {
        "inventory_guide_open": "inventory",
        "grid_guide_open": "grid",
    }
    assert [tool.name for tool in catalog.core_tools] == [
        "agent_context_get",
        "agent_record_decision",
    ]
    assert [tool.name for tool in catalog.domain_tools] == [
        "grid_analysis_powerflow_ac",
        "inventory_asset_list",
    ]


def test_composite_catalog_requires_a_domain_binding() -> None:
    with pytest.raises(ToolCatalogError, match="at least one domain binding"):
        CompositeToolCatalog.build(
            core=CoreToolCatalog.default(namespace="agent_"),
            domains=(),
        )


def test_composite_catalog_identifies_registered_auxiliary_tools() -> None:
    catalog = CompositeToolCatalog.build(
        core=CoreToolCatalog.default(namespace="agent_"),
        domains=(
            _domain(
                "grid",
                "grid_",
                guide_tool_name="grid_guide_open",
                context_tool_name="grid_analysis_context_get",
            ),
        ),
    )

    assert catalog.is_auxiliary("grid_guide_open")
    assert catalog.is_auxiliary("grid_analysis_context_get")
    assert not catalog.is_auxiliary("grid_context_open")


def test_bound_domain_catalog_uses_prepared_binding_controller_metadata() -> None:
    manifest = SimpleNamespace(
        authority_id="inventory-api",
        protocol="inventory-capability",
        protocol_version="1.0",
    )
    profile = SimpleNamespace(manifest=manifest, tool_description_builder=None)
    prepared = SimpleNamespace(
        binding=SimpleNamespace(
            binding_id="inventory",
            tool_namespace="inventory_",
            profile=profile,
        ),
        runtime=SimpleNamespace(
            authority=SimpleNamespace(authority_id="inventory-api"),
            capability_documents=(
                _contract(capability_id="asset.list", tool_name="inventory_asset_list"),
            ),
            environment_description={
                "protocol": "inventory-capability",
                "protocol_version": "1.0",
                "executable_capabilities": [{"id": "asset.list"}],
            },
        ),
    )

    catalog = BoundDomainCatalog.from_prepared(prepared)

    assert catalog.binding_id == "inventory"
    assert catalog.tools[0].key == CapabilityKey("inventory", "asset.list")
    assert catalog.tools[0].authority_id == "inventory-api"
    assert catalog.tools[0].protocol == "inventory-capability"
    assert catalog.guide_tool_name == "inventory_guide_open"


@pytest.mark.parametrize(
    ("runtime_authority", "runtime_protocol", "runtime_protocol_version"),
    [
        ("other-api", "inventory-capability", "1.0"),
        ("inventory-api", "other-capability", "1.0"),
        ("inventory-api", "inventory-capability", "2.0"),
    ],
)
def test_bound_domain_catalog_rejects_prepared_routing_metadata_disagreement(
    runtime_authority: str,
    runtime_protocol: str,
    runtime_protocol_version: str,
) -> None:
    manifest = SimpleNamespace(
        authority_id="inventory-api",
        protocol="inventory-capability",
        protocol_version="1.0",
    )
    profile = SimpleNamespace(manifest=manifest, tool_description_builder=None)
    prepared = SimpleNamespace(
        binding=SimpleNamespace(
            binding_id="inventory",
            tool_namespace="inventory_",
            profile=profile,
        ),
        runtime=SimpleNamespace(
            authority=SimpleNamespace(authority_id=runtime_authority),
            capability_documents=(
                _contract(capability_id="asset.list", tool_name="inventory_asset_list"),
            ),
            environment_description={
                "protocol": runtime_protocol,
                "protocol_version": runtime_protocol_version,
                "executable_capabilities": [{"id": "asset.list"}],
            },
        ),
    )

    with pytest.raises(ToolCatalogError, match="routing metadata"):
        BoundDomainCatalog.from_prepared(prepared)


def test_composite_catalog_rejects_duplicate_binding_ids() -> None:
    with pytest.raises(ToolCatalogError, match="binding IDs"):
        CompositeToolCatalog.build(
            core=CoreToolCatalog.default(namespace="agent_"),
            domains=(
                _domain("grid", "grid_"),
                _domain("grid", "backup_", capability_id="asset.list"),
            ),
        )


def test_composite_catalog_rejects_duplicate_tool_namespaces() -> None:
    with pytest.raises(ToolCatalogError, match="tool namespaces"):
        CompositeToolCatalog.build(
            core=CoreToolCatalog.default(namespace="agent_"),
            domains=(
                _domain("primary", "shared_"),
                _domain("secondary", "shared_", capability_id="asset.list"),
            ),
        )


def test_composite_catalog_rejects_duplicate_final_tool_names() -> None:
    first = _domain("primary", "primary_")
    second = _domain("secondary", "secondary_")
    duplicated = replace(second, tools=first.tools)

    with pytest.raises(ToolCatalogError, match="final tool names"):
        CompositeToolCatalog.build(
            core=CoreToolCatalog.default(namespace="agent_"),
            domains=(first, duplicated),
        )


def test_composite_catalog_rejects_duplicate_core_tool_names() -> None:
    core = CoreToolCatalog.default(namespace="agent_")
    duplicated = replace(core, tools=(*core.tools, core.tools[0]))

    with pytest.raises(ToolCatalogError, match="final tool names"):
        CompositeToolCatalog.build(
            core=duplicated,
            domains=(_domain("grid", "grid_"),),
        )


@pytest.mark.parametrize("field", ["guide_tool_name", "context_tool_name"])
def test_composite_catalog_rejects_guide_and_context_name_collisions(
    field: str,
) -> None:
    first = _domain("primary", "primary_", tool_name="primary_context_open")
    second = _domain("secondary", "secondary_")
    second = replace(second, **{field: "primary_context_open"})

    with pytest.raises(ToolCatalogError, match="final tool names"):
        CompositeToolCatalog.build(
            core=CoreToolCatalog.default(namespace="agent_"),
            domains=(first, second),
        )


def test_composite_catalog_rejects_a_guide_context_name_collision() -> None:
    domain = _domain(
        "grid",
        "grid_",
        guide_tool_name="grid_resource_open",
        context_tool_name="grid_resource_open",
    )

    with pytest.raises(ToolCatalogError, match="final tool names"):
        CompositeToolCatalog.build(
            core=CoreToolCatalog.default(namespace="agent_"),
            domains=(domain,),
        )


@pytest.mark.parametrize("field", ["guide_tool_name", "context_tool_name"])
def test_composite_catalog_rejects_duplicate_auxiliary_names_across_bindings(
    field: str,
) -> None:
    first = _domain("primary", "primary_", **{field: "primary_resource_open"})
    second = _domain("secondary", "secondary_", **{field: "secondary_resource_open"})
    second = replace(second, **{field: "primary_resource_open"})

    with pytest.raises(ToolCatalogError, match="final tool names"):
        CompositeToolCatalog.build(
            core=CoreToolCatalog.default(namespace="agent_"),
            domains=(first, second),
        )


def test_composite_catalog_reserves_the_core_namespace_for_core_tools() -> None:
    with pytest.raises(ToolCatalogError, match="reserved core namespace"):
        CompositeToolCatalog.build(
            core=CoreToolCatalog.default(namespace="agent_"),
            domains=(_domain("attacker", "agent_"),),
        )
