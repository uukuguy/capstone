import hashlib
import json
from pathlib import Path

import pytest

from grid_agent.analysis.capabilities import KNOWN_CONTEXT_PROJECTORS
from grid_agent.analysis.integrity import ContentReferenceVerifier
from grid_agent.analysis.workspace import AnalysisWorkspace
from grid_agent.domain import DomainRuntimeProfile
from grid_agent.domain.projection import VerifiedInvocation
from grid_agent.domains import build_pandapower_profile
from grid_agent.simulator.client import GridctlClient


ROOT = Path(__file__).resolve().parents[4]


def test_pandapower_profile_owns_all_grid_runtime_resources() -> None:
    profile = build_pandapower_profile(ROOT)

    assert isinstance(profile, DomainRuntimeProfile)
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


def test_pandapower_profile_public_runtime_surface_is_preserved() -> None:
    profile = build_pandapower_profile(ROOT)

    assert profile.create_executor.__name__ == "create_executor"
    assert profile.create_authority.__name__ == "create_authority"
    assert profile.contract_source.__class__.__name__ == (
        "FilesystemCapabilityContractSource"
    )
    assert profile.projector_registry.__class__.__name__ == (
        "PandapowerProjectorRegistry"
    )


def test_pandapower_profile_adapts_grid_runtime_dependencies(tmp_path: Path) -> None:
    profile = build_pandapower_profile(ROOT)

    executor = profile.create_executor(tmp_path / "gridctl", tmp_path / "run", 17)
    authority = profile.create_authority(tmp_path / "run")

    assert isinstance(executor, GridctlClient)
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


def test_pandapower_authority_matches_current_run_verifier(tmp_path: Path) -> None:
    profile = build_pandapower_profile(ROOT)
    workspace = AnalysisWorkspace.create(tmp_path / "runs", "authority-test")
    revision_payload = _canonical_json(
        {"model_id": "ieee39", "pandapower_version": "3.4.0", "bus": [1, 2]}
    )
    revision_digest = hashlib.sha256(
        revision_payload.encode("utf-8")
    ).hexdigest()
    revision_ref = "revision:sha256:" + revision_digest
    (workspace.evidence_path / "models").mkdir(parents=True, exist_ok=True)
    (
        workspace.evidence_path / "models" / f"{revision_digest}.json"
    ).write_text(revision_payload, encoding="utf-8")
    context = {
        "revision_ref": revision_ref,
        "model_id": "ieee39",
        "source": "registered",
        "engine": "pandapower",
        "pandapower_version": "3.4.0",
        "counts": {"bus": 39, "line": 35, "trafo": 11},
    }
    context_payload = _canonical_json(context)
    context_digest = hashlib.sha256(context_payload.encode("utf-8")).hexdigest()
    context_ref = "context:sha256:" + context_digest
    (workspace.evidence_path / "contexts" / f"{context_digest}.json").write_text(
        context_payload, encoding="utf-8"
    )
    result_body = {
        "result_type": "analysis.powerflow.ac",
        "context_ref": context_ref,
        "revision_ref": context["revision_ref"],
        "converged": True,
        "total_active_loss": 1.25,
        "solver_summary": {
            "success": True,
            "total_active_loss": 1.25,
            "algorithm": "nr",
        },
        "branch_results": [],
    }
    result_digest = hashlib.sha256(
        _canonical_json(result_body).encode("utf-8")
    ).hexdigest()
    result_ref = "result:sha256:" + result_digest
    (workspace.results_path / f"powerflow-{result_digest}.json").write_text(
        _canonical_json({"result_ref": result_ref, **result_body}),
        encoding="utf-8",
    )
    evidence_body = {
        "evidence_type": "analysis_result",
        "capability_id": "analysis.powerflow.ac.run",
        "context_ref": context_ref,
        "revision_ref": context["revision_ref"],
        "result_ref": result_ref,
        "facts": {"converged": True, "total_active_loss": 1.25},
    }
    evidence_digest = hashlib.sha256(
        _canonical_json(evidence_body).encode("utf-8")
    ).hexdigest()
    evidence_ref = "evidence:sha256:" + evidence_digest
    evidence_path = (
        workspace.evidence_path
        / "analysis"
        / f"analysis-evidence-{evidence_digest}.json"
    )
    evidence_path.write_text(_canonical_json(evidence_body), encoding="utf-8")
    result = {
        "context_ref": context_ref,
        "revision_ref": context["revision_ref"],
        "result_ref": result_ref,
        "evidence_refs": [evidence_ref],
        "converged": True,
        "total_active_loss": 1.25,
    }
    evidence_refs = (evidence_ref,)
    authority = profile.create_authority(workspace.root_path)
    verifier = ContentReferenceVerifier(workspace.root_path)

    references = authority.admit(
        "analysis.powerflow.ac.run", result, evidence_refs
    )
    expected = verifier.admit_successful_tool_references(
        "analysis.powerflow.ac.run", result, evidence_refs
    )

    assert references.results == expected.results
    assert references.context == expected.context
    assert references.evidence == expected.evidence


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
    dumped = delta.model_dump()

    assert dumped["projector"] == "model-context-v1"
    assert dumped["model"] is not None
    assert dumped["model"]["model_id"] == "case9"


def _canonical_json(document: object) -> str:
    return json.dumps(
        document,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )
