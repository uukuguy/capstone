from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pandapower_domain import PandapowerArtifactAuthority, build_pandapower_profile
from pandapower_domain.authority import ContentReferenceVerifier


def test_pandapower_authority_matches_current_run_verifier(tmp_path: Path) -> None:
    profile = build_pandapower_profile()
    run_root = tmp_path / "run"
    evidence_root = run_root / "evidence"
    (evidence_root / "models").mkdir(parents=True)
    (evidence_root / "contexts").mkdir()
    (evidence_root / "results").mkdir()
    (evidence_root / "analysis").mkdir()

    revision_payload = _canonical_json(
        {"model_id": "ieee39", "pandapower_version": "3.4.0", "bus": [1, 2]}
    )
    revision_digest = hashlib.sha256(revision_payload.encode("utf-8")).hexdigest()
    revision_ref = "revision:sha256:" + revision_digest
    (evidence_root / "models" / f"{revision_digest}.json").write_text(
        revision_payload, encoding="utf-8"
    )
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
    (evidence_root / "contexts" / f"{context_digest}.json").write_text(
        context_payload, encoding="utf-8"
    )
    result_body = {
        "result_type": "analysis.powerflow.ac",
        "context_ref": context_ref,
        "revision_ref": revision_ref,
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
    (evidence_root / "results" / f"powerflow-{result_digest}.json").write_text(
        _canonical_json({"result_ref": result_ref, **result_body}), encoding="utf-8"
    )
    evidence_body = {
        "evidence_type": "analysis_result",
        "capability_id": "analysis.powerflow.ac.run",
        "context_ref": context_ref,
        "revision_ref": revision_ref,
        "result_ref": result_ref,
        "facts": {"converged": True, "total_active_loss": 1.25},
    }
    evidence_digest = hashlib.sha256(
        _canonical_json(evidence_body).encode("utf-8")
    ).hexdigest()
    evidence_ref = "evidence:sha256:" + evidence_digest
    (
        evidence_root / "analysis" / f"analysis-evidence-{evidence_digest}.json"
    ).write_text(_canonical_json(evidence_body), encoding="utf-8")
    result = {
        "context_ref": context_ref,
        "revision_ref": revision_ref,
        "result_ref": result_ref,
        "evidence_refs": [evidence_ref],
        "converged": True,
        "total_active_loss": 1.25,
    }
    evidence_refs = (evidence_ref,)
    authority = profile.create_authority(run_root)
    assert isinstance(authority, PandapowerArtifactAuthority)
    verifier = ContentReferenceVerifier(run_root)

    references = authority.admit("analysis.powerflow.ac.run", result, evidence_refs)
    expected = verifier.admit_successful_tool_references(
        "analysis.powerflow.ac.run", result, evidence_refs
    )

    assert references.results == expected.results
    assert references.context == expected.context
    assert references.evidence == expected.evidence


def _canonical_json(document: object) -> str:
    return json.dumps(
        document,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )
