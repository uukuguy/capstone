from __future__ import annotations

from pathlib import Path

from pandapower_domain.resources import PandapowerResourceSet


def test_load_uses_installed_simulator_contract_resources() -> None:
    resources = PandapowerResourceSet.load()

    documents = sorted(
        resources.capability_contract_root.glob("*.json"), key=lambda path: path.name
    )
    assert len(documents) == 30
    assert all(path.is_file() for path in documents)
    assert not any("packages/grid-simulator/src" in str(path) for path in documents)


def test_contract_resource_root_is_compatible_with_filesystem_sources() -> None:
    resources = PandapowerResourceSet.load()

    assert isinstance(resources.capability_contract_root, Path)
    assert resources.capability_contract_root.is_dir()
