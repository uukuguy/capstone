from pathlib import Path

import pytest

from grid_agent.analysis.capabilities import KNOWN_CONTEXT_PROJECTORS
from grid_agent.domain.projection import VerifiedInvocation
from grid_agent.domains import build_pandapower_profile


ROOT = Path(__file__).resolve().parents[4]


def test_pandapower_profile_owns_all_grid_runtime_resources() -> None:
    profile = build_pandapower_profile(ROOT)

    assert profile.manifest.domain_id == "pandapower-static-analysis"
    assert profile.manifest.protocol == "grid-capability"
    assert profile.manifest.protocol_version == "1.0"
    assert profile.manifest.executable_name == "gridctl"
    assert profile.manifest.tool_name_prefix == "grid_"
    assert profile.manifest.authority_id == "gridctl"
    assert profile.manifest.capability_contract_root == (
        ROOT / "packages/grid-simulator/src/grid_simulator/capabilities/definitions"
    )
    assert profile.manifest.system_policy_path == ROOT / "configs/agent/system-policy.md"
    assert profile.manifest.guide_root == ROOT / "skills/grid-static-analysis"


def test_pandapower_profile_adapts_grid_runtime_dependencies(tmp_path: Path) -> None:
    profile = build_pandapower_profile(ROOT)

    executor = profile.create_executor(tmp_path / "gridctl", tmp_path / "run", 17)
    authority = profile.create_authority(tmp_path / "run")

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


def test_pandapower_projector_delegates_verified_invocation() -> None:
    profile = build_pandapower_profile(ROOT)
    invocation = VerifiedInvocation(
        capability="model.open",
        projector_id="model-context-v1",
        result_kind="model-context",
        result={
            "context_ref": "context:sha256:abc",
            "revision_ref": "revision:sha256:def",
            "model": "case9",
            "source": "registered",
        },
        arguments={},
        turn_id="turn-1",
        result_paths={},
        active_revision_ref=None,
    )

    delta = profile.projector_registry.require("model-context-v1").project(invocation)

    assert delta.projector == "model-context-v1"
    assert delta.model is not None
    assert delta.model.model_id == "case9"
