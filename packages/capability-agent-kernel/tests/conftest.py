from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
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
from capability_agent.application import (
    ApplicationManifest,
    ApplicationProfile,
    CredentialScope,
    DataSharingPolicy,
    DomainBinding,
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


@dataclass
class RecordingEndpoint:
    executor: RecordingExecutor
    metadata: Mapping[str, object] = field(
        default_factory=lambda: {"transport": "fixture"}
    )
    closed: bool = False

    def close(self) -> None:
        self.closed = True


@dataclass
class RecordingProvisioner:
    endpoint: RecordingEndpoint
    failure: Exception | None = None
    calls: list[tuple[DomainBinding, Path, object]] = field(default_factory=list)

    def prepare(
        self, *, binding: DomainBinding, workspace: Path, credentials: object
    ) -> RecordingEndpoint:
        self.calls.append((binding, workspace, credentials))
        if self.failure is not None:
            raise self.failure
        return self.endpoint


@dataclass(frozen=True)
class StaticPolicy:
    fragment: str

    def load(self) -> str:
        return self.fragment


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


@pytest.fixture
def complete_profile(inventory_profile) -> ApplicationProfile:
    domain_profile, executor = inventory_profile
    endpoint = RecordingEndpoint(executor)
    provisioner = RecordingProvisioner(endpoint)
    component = object()
    complete_domain = replace(
        domain_profile,
        manifest=replace(
            domain_profile.manifest,
            domain_id="fixture-domain",
            display_name="Fixture Domain",
        ),
        provisioner=provisioner,
        state_adapter=component,
        answer_policy=component,
        policy_provider=StaticPolicy("deny: domain-write"),
        guide_provider=component,
        presentation_provider=component,
        output_contract=component,
        acceptance_profile=component,
    )
    binding = DomainBinding(
        binding_id="fixture",
        tool_namespace="fixture_",
        profile=complete_domain,
        credential_scope=CredentialScope(),
        sharing_policy=DataSharingPolicy(),
    )
    return ApplicationProfile(
        manifest=ApplicationManifest(
            application_id="fixture-agent",
            version="1.0.0",
            display_name="Fixture Agent",
            context_schema="application-context/1.0",
            result_schema="capability-agent-output/1.0",
            artifact_schema="capability-agent-run/1.0",
            core_tool_namespace="agent_",
        ),
        domains=(binding,),
        output_renderer=component,
        application_policy=StaticPolicy("deny: application-write"),
        report_shell=component,
        acceptance_profile=component,
    )
