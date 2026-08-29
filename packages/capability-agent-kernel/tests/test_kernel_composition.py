from __future__ import annotations

import json
from pathlib import Path

import pytest

from capability_agent.application import (
    ApplicationConfigurationError,
    ApplicationManifest,
    ApplicationProfile,
    CredentialScope,
    DataSharingPolicy,
    DomainBinding,
    DomainRegistry,
    prepare_application,
    prepare_domain_runtime,
)
from capability_agent.tools import GuideIndex, ToolCatalog


def test_inventory_profile_materializes_exact_provider_free_tool_inventory(
    tmp_path: Path,
    inventory_profile,
) -> None:
    profile, executor = inventory_profile
    workspace = tmp_path / "run"

    prepared = prepare_domain_runtime(
        profile,
        executable=tmp_path / "inventoryctl",
        workspace=workspace,
        tool_catalog_path=workspace / "tool-catalog.json",
        guide_index_path=workspace / "guide-index.json",
    )

    assert prepared.executor is executor
    catalog = json.loads(prepared.tool_catalog_path.read_text(encoding="utf-8"))
    assert executor.calls == [("environment.describe", {})]
    assert [tool["name"] for tool in catalog["tools"]] == [
        "inventory_asset_list",
        "inventory_record_decision",
    ]


def test_kernel_helpers_use_neutral_default_schema_ids(
    tmp_path: Path,
    inventory_profile,
) -> None:
    profile, _ = inventory_profile
    prepared = prepare_domain_runtime(
        profile,
        executable=tmp_path / "inventoryctl",
        workspace=tmp_path / "run",
        tool_catalog_path=tmp_path / "run/catalog.json",
        guide_index_path=tmp_path / "run/guides.json",
    )

    catalog_payload = json.loads(
        prepared.tool_catalog_path.read_text(encoding="utf-8")
    )
    guide_payload = json.loads(
        prepared.guide_index_path.read_text(encoding="utf-8")
    )
    assert catalog_payload["protocol"] == "inventory-tool-catalog"
    assert guide_payload["protocol"] == "inventory-guide-index"

    default_catalog = ToolCatalog.from_documents(
        profile.contract_source.load(), tool_name_prefix="inventory_"
    )
    default_catalog_payload = json.loads(
        default_catalog.materialize(tmp_path / "run/default-catalog.json").read_text(
            encoding="utf-8"
        )
    )
    default_guide = GuideIndex.load(profile.manifest.guide_root)
    default_guide_payload = json.loads(
        default_guide.materialize(tmp_path / "run/default-guides.json").read_text(
            encoding="utf-8"
        )
    )
    assert default_catalog_payload["protocol"] == "inventory-tool-catalog"
    assert default_guide_payload["protocol"] == "capability-guide-index"
    assert ToolCatalog.__module__ == "capability_agent.tools.catalog"
    assert GuideIndex.__module__ == "capability_agent.tools.guide"


def test_incomplete_inventory_fixture_remains_low_level_only(
    tmp_path: Path, inventory_profile
) -> None:
    profile, _ = inventory_profile
    workspace = tmp_path / "run"
    low_level = prepare_domain_runtime(
        profile,
        executable=tmp_path / "inventoryctl",
        workspace=workspace,
        tool_catalog_path=workspace / "tool-catalog.json",
        guide_index_path=workspace / "guide-index.json",
    )
    component = object()
    incomplete_application = object.__new__(ApplicationProfile)
    for name, value in {
        "manifest": ApplicationManifest(
            application_id="fixture-agent",
            version="1.0.0",
            display_name="Fixture Agent",
            context_schema="application-context/1.0",
            result_schema="capability-agent-output/1.0",
            artifact_schema="capability-agent-run/1.0",
            core_tool_namespace="agent_",
        ),
        "domains": (
            DomainBinding(
                binding_id="inventory",
                tool_namespace="inventory_",
                profile=profile,
                credential_scope=CredentialScope(),
                sharing_policy=DataSharingPolicy(),
            ),
        ),
        "output_renderer": component,
        "application_policy": component,
        "report_shell": component,
        "acceptance_profile": component,
    }.items():
        object.__setattr__(incomplete_application, name, value)

    registry = DomainRegistry()
    registry.register(
        profile.manifest.domain_id,
        profile.manifest.version,
        lambda: profile,
    )

    assert low_level.tool_catalog_path.is_file()
    with pytest.raises(
        ApplicationConfigurationError, match="missing application components"
    ):
        prepare_application(
            incomplete_application,
            registry=registry,
            workspace=tmp_path / "application",
            credentials=object(),
        )
