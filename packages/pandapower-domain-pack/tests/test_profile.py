from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from capability_agent import DomainRuntimeProfile
from pandapower_domain import PandapowerResourceSet, build_pandapower_profile
from pandapower_domain.capabilities import KNOWN_CONTEXT_PROJECTORS
from pandapower_domain.execution import GridctlExecutor


def test_pandapower_profile_owns_installed_runtime_resources() -> None:
    profile = build_pandapower_profile()
    resources = PandapowerResourceSet.load()

    assert isinstance(profile, DomainRuntimeProfile)
    assert profile.manifest.domain_id == "pandapower-static-analysis"
    assert profile.manifest.capability_contract_root == resources.capability_contract_root
    assert profile.manifest.system_policy_path == resources.system_policy_path
    assert profile.manifest.guide_root == resources.guide_root
    assert profile.manifest.protocol == "grid-capability"
    assert profile.manifest.tool_name_prefix == "grid_"
    assert profile.manifest.protocol_version == "1.0"
    assert profile.manifest.executable_name == "gridctl"
    assert profile.manifest.authority_id == "gridctl"
    profile.manifest.assert_resources_present()


def test_pandapower_profile_has_no_repository_root_parameter() -> None:
    assert "repository_root" not in inspect.signature(build_pandapower_profile).parameters


def test_pandapower_profile_public_runtime_surface_is_preserved() -> None:
    profile = build_pandapower_profile()

    assert profile.create_executor.__name__ == "create_executor"
    assert profile.create_authority.__name__ == "create_authority"
    assert profile.contract_source.__class__.__name__ == (
        "FilesystemCapabilityContractSource"
    )
    assert profile.projector_registry.__class__.__name__ == (
        "PandapowerProjectorRegistry"
    )


def test_pandapower_profile_adapts_grid_runtime_dependencies(tmp_path: Path) -> None:
    profile = build_pandapower_profile()

    executor = profile.create_executor(tmp_path / "gridctl", tmp_path / "run", 17)
    authority = profile.create_authority(tmp_path / "run")

    assert isinstance(executor, GridctlExecutor)
    assert executor.executable == tmp_path / "gridctl"
    assert executor.workspace == tmp_path / "run"
    assert executor.timeout_seconds == 17
    assert authority.authority_id == "gridctl"
    assert authority.workspace_root == tmp_path / "run"
    assert {
        profile.projector_registry.require(projector_id).projector_id
        for projector_id in KNOWN_CONTEXT_PROJECTORS
    } == KNOWN_CONTEXT_PROJECTORS
    with pytest.raises(LookupError, match="unknown projector"):
        profile.projector_registry.require("unknown-v1")


def test_pandapower_profile_is_application_complete() -> None:
    profile = build_pandapower_profile()

    assert profile.missing_application_components() == ()
    assert profile.output_contract is not None
    assert profile.output_contract.schema_id == (
        "pandapower-static-analysis-output/1.0"
    )
    for component in (
        profile.provisioner,
        profile.state_adapter,
        profile.answer_policy,
        profile.policy_provider,
        profile.guide_provider,
        profile.presentation_provider,
        profile.output_contract,
        profile.acceptance_profile,
    ):
        assert component is not None
        assert component.__class__.__module__.startswith("pandapower_domain.")
