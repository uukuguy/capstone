from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

import pytest

from capability_agent.domain import (
    ArtifactAuthority,
    CapabilityContractSource,
    DomainManifest,
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


@pytest.fixture
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
