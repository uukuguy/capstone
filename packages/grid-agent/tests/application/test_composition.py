from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

import pytest

from grid_agent.application.composition import prepare_domain_runtime
from grid_agent.domain import (
    ArtifactAuthority,
    CapabilityContractSource,
    DomainManifest,
    DomainManifestError,
    DomainProjector,
    DomainProjectorRegistry,
    DomainRuntimeProfile,
    VerifiedArtifact,
    VerifiedReferenceSet,
)


@dataclass
class RecordingExecutor:
    environment: dict[str, object]
    calls: list[tuple[str, dict[str, object]]] = field(default_factory=list)

    def invoke(
        self, capability: str, arguments: dict[str, object]
    ) -> dict[str, object]:
        self.calls.append((capability, arguments))
        return self.environment


class RecordingAuthority(ArtifactAuthority):
    authority_id = "inventory-api"

    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root

    def admit(
        self,
        capability: str,
        result: Mapping[str, object],
        evidence_refs: tuple[str, ...],
    ) -> VerifiedReferenceSet:
        return cast(VerifiedReferenceSet, object())

    def verify_result(self, reference: str) -> VerifiedArtifact:
        return cast(VerifiedArtifact, object())

    def audit_answer_references(
        self,
        claim_evidence_refs: tuple[str, ...],
        result_refs: tuple[str, ...],
    ) -> tuple[object, ...]:
        return ()


class StubProjectorRegistry(DomainProjectorRegistry):
    def require(self, projector_id: str) -> DomainProjector:
        return cast(DomainProjector, object())


@dataclass(frozen=True)
class FileContractSource(CapabilityContractSource):
    root: Path

    def load(self) -> tuple[dict[str, object], ...]:
        documents: list[dict[str, object]] = []
        for path in sorted(self.root.glob("*.json"), key=lambda item: item.name):
            documents.append(json.loads(path.read_text(encoding="utf-8")))
        return tuple(documents)


def _asset_document() -> dict[str, object]:
    return {
        "id": "asset.list",
        "tool_name": "inventory_asset_list",
        "availability": "published",
        "context_effect": {
            "requires_state": [],
            "consumes_state": [],
            "produces_state": ["inventory.assets"],
            "invalidates_state": [],
            "result_kind": "inventory.asset-list",
            "projector": "inventory-list-v1",
        },
        "purpose": "List versioned inventory assets.",
        "applies_to": ["read-only inventory discovery"],
        "not_for": ["inventory mutation"],
        "input_schema": {
            "type": "object",
            "additionalProperties": False,
            "required": [],
            "properties": {},
        },
        "requires": [],
        "produces": ["versioned asset summaries"],
        "common_next": [],
        "recovery": {},
    }


def inventory_profile(
    tmp_path: Path,
    *,
    protocol_version: str = "1.0",
    authority_factory: Callable[[Path], ArtifactAuthority] | None = None,
) -> tuple[DomainRuntimeProfile, RecordingExecutor]:
    fixture_root = tmp_path / "inventory"
    contracts = fixture_root / "contracts"
    contracts.mkdir(parents=True)
    (contracts / "asset.list.json").write_text(
        json.dumps(_asset_document()), encoding="utf-8"
    )
    policy = fixture_root / "policy.md"
    policy.write_text("# Inventory policy\n", encoding="utf-8")
    guides = fixture_root / "guides"
    guides.mkdir()
    (guides / "SKILL.md").write_text("# Inventory guide\n", encoding="utf-8")

    executor = RecordingExecutor(
        {
            "protocol": "inventory-capability",
            "protocol_version": protocol_version,
            "executable_capabilities": [{"id": "asset.list"}],
        }
    )
    manifest = DomainManifest(
        domain_id="inventory-readonly",
        version="1.0.0",
        display_name="Inventory",
        protocol="inventory-capability",
        protocol_version="1.0",
        executable_name="inventoryctl",
        tool_name_prefix="inventory_",
        authority_id="inventory-api",
        capability_contract_root=contracts,
        system_policy_path=policy,
        guide_root=guides,
    )
    return (
        DomainRuntimeProfile(
            manifest=manifest,
            contract_source=FileContractSource(contracts),
            executor_factory=lambda executable, workspace, timeout: executor,
            projector_registry=StubProjectorRegistry(),
            authority_factory=authority_factory or RecordingAuthority,
        ),
        executor,
    )


def test_synthetic_domain_materializes_through_public_seams(tmp_path: Path) -> None:
    profile, executor = inventory_profile(tmp_path)
    workspace = tmp_path / "run"

    prepared = prepare_domain_runtime(
        profile,
        executable=tmp_path / "inventoryctl",
        workspace=workspace,
        tool_catalog_path=workspace / "tool-catalog.json",
        guide_index_path=workspace / "guide-index.json",
    )

    catalog = json.loads(prepared.tool_catalog_path.read_text(encoding="utf-8"))
    guide = json.loads(prepared.guide_index_path.read_text(encoding="utf-8"))
    assert executor.calls == [("environment.describe", {})]
    assert prepared.executor is executor
    assert prepared.authority.authority_id == "inventory-api"
    assert prepared.authority.workspace_root == workspace
    assert prepared.environment_description["protocol"] == "inventory-capability"
    assert prepared.capability_documents == (_asset_document(),)
    assert [tool["name"] for tool in catalog["tools"]] == [
        "inventory_asset_list",
        "inventory_record_decision",
    ]
    assert "grid_asset_list" not in prepared.tool_catalog_path.read_text(encoding="utf-8")
    assert guide["root"] == str(profile.manifest.guide_root.resolve())
    assert guide["resources"] == {
        "overview": str((tmp_path / "inventory/guides/SKILL.md").resolve())
    }
    assert profile.manifest.system_policy_path == tmp_path / "inventory/policy.md"
    assert "grid-static-analysis" not in guide["root"]
    assert prepared.profile.manifest.domain_id == "inventory-readonly"


def test_prepare_domain_runtime_rejects_incompatible_protocol_before_downstream_runtime(
    tmp_path: Path,
) -> None:
    pi_launcher_calls = 0
    authority_calls = 0

    def provider_or_pi_launcher(workspace: Path) -> ArtifactAuthority:
        nonlocal pi_launcher_calls, authority_calls
        pi_launcher_calls += 1
        authority_calls += 1
        raise AssertionError("provider or Pi launcher must not be invoked")

    profile, executor = inventory_profile(
        tmp_path,
        protocol_version="2.0",
        authority_factory=provider_or_pi_launcher,
    )
    workspace = tmp_path / "run"

    with pytest.raises(DomainManifestError, match="protocol_version"):
        prepare_domain_runtime(
            profile,
            executable=tmp_path / "bin/inventoryctl",
            workspace=workspace,
            tool_catalog_path=workspace / "tool-catalog.json",
            guide_index_path=workspace / "guide-index.json",
        )

    assert executor.calls == [("environment.describe", {})]
    assert pi_launcher_calls == 0
    assert authority_calls == 0
    assert not (workspace / "tool-catalog.json").exists()
    assert not (workspace / "guide-index.json").exists()


def test_prepare_domain_runtime_validates_profile_resources_before_executor_creation(
    tmp_path: Path,
) -> None:
    profile, _ = inventory_profile(tmp_path)
    profile.manifest.system_policy_path.unlink()
    executor_factory_calls = 0

    def executor_factory(
        executable: Path, workspace: Path, timeout: float
    ) -> RecordingExecutor:
        nonlocal executor_factory_calls
        executor_factory_calls += 1
        return RecordingExecutor({})

    invalid_profile = DomainRuntimeProfile(
        manifest=profile.manifest,
        contract_source=profile.contract_source,
        executor_factory=executor_factory,
        projector_registry=profile.projector_registry,
        authority_factory=profile.authority_factory,
    )

    with pytest.raises(DomainManifestError, match="system_policy_path"):
        prepare_domain_runtime(
            invalid_profile,
            executable=tmp_path / "bin/inventoryctl",
            workspace=tmp_path / "run",
            tool_catalog_path=tmp_path / "run/tool-catalog.json",
            guide_index_path=tmp_path / "run/guide-index.json",
        )

    assert executor_factory_calls == 0
