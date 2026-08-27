from pathlib import Path

import pytest

from grid_agent.domain.manifest import DomainManifest, DomainManifestError


def manifest(tmp_path: Path, **changes: object) -> DomainManifest:
    values: dict[str, object] = {
        "domain_id": "inventory-readonly",
        "version": "1.0.0",
        "display_name": "Inventory",
        "protocol": "inventory-capability",
        "protocol_version": "1.0",
        "executable_name": "inventoryctl",
        "tool_name_prefix": "inventory_",
        "authority_id": "inventory-api",
        "capability_contract_root": tmp_path / "contracts",
        "system_policy_path": tmp_path / "policy.md",
        "guide_root": tmp_path / "guides",
    }
    values.update(changes)
    return DomainManifest(**values)  # type: ignore[arg-type]


def test_manifest_accepts_compatible_environment(tmp_path: Path) -> None:
    value = manifest(tmp_path)

    value.assert_environment_compatible(
        {"protocol": "inventory-capability", "protocol_version": "1.0"}
    )


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"domain_id": "Inventory"}, "domain_id"),
        ({"executable_name": "bin/inventoryctl"}, "executable_name"),
        ({"tool_name_prefix": "inventory"}, "tool_name_prefix"),
    ],
)
def test_manifest_rejects_unsafe_identity_fields(
    tmp_path: Path, changes: dict[str, object], message: str
) -> None:
    with pytest.raises(DomainManifestError, match=message):
        manifest(tmp_path, **changes)


def test_manifest_rejects_runtime_protocol_mismatch(tmp_path: Path) -> None:
    with pytest.raises(DomainManifestError, match="protocol_version"):
        manifest(tmp_path).assert_environment_compatible(
            {"protocol": "inventory-capability", "protocol_version": "2.0"}
        )


def test_manifest_rejects_missing_versioned_resources(tmp_path: Path) -> None:
    with pytest.raises(DomainManifestError, match="capability_contract_root"):
        manifest(tmp_path).assert_resources_present()
