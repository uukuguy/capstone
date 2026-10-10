from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

import pandapower_domain.authority as authority_module
from pandapower_domain import PandapowerArtifactAuthority, build_pandapower_profile
from pandapower_domain.authority import ContentReferenceVerifier, SimulatorIntegrityError


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


def test_solver_failure_is_confirmed_without_blame_or_raw_text():
    diagnostic = PandapowerArtifactAuthority.describe_execution_failure('powerflow_non_converged')
    assert diagnostic['category'] == 'calculation'
    assert diagnostic['confirmation'] == 'confirmed'
    assert '不能单独证明' in diagnostic['summary']
    assert PandapowerArtifactAuthority.describe_execution_failure('SECRET') is None


def _write_context_chain(root, *, parent=None, model='ieee39', marker='base'):
    def write(kind, directory, document):
        data = _canonical_json(document)
        digest = hashlib.sha256(data.encode()).hexdigest()
        path = root / 'evidence' / directory / (digest + '.json')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data)
        return kind + ':sha256:' + digest
    revision = write('revision', 'models', {'marker': marker})
    document = {'model_id': model, 'revision_ref': revision, 'engine': 'pandapower',
                'engine_version': '3.4.0'}
    if parent:
        parent_ref, parent_revision = parent
        lineage = {**document, 'origin': 'derived', 'parent_context_ref': parent_ref,
                   'parent_revision_ref': parent_revision}
        document.update(origin='derived', parent_context_ref=parent_ref,
                        lineage_ref=write('lineage', 'revisions', lineage))
    return write('context', 'contexts', document), revision


def test_authority_verifies_exact_root_and_multistep_descendant_identity(tmp_path):
    base = _write_context_chain(tmp_path)
    child = _write_context_chain(tmp_path, parent=base, marker='child')
    grandchild = _write_context_chain(tmp_path, parent=child, marker='grandchild')
    authority = ContentReferenceVerifier(tmp_path)
    for reference, revision in (base, child, grandchild):
        assert authority.verify_context_descendant(reference, base_ref=base[0],
            model_id='ieee39', revision_ref=revision)
    assert not authority.verify_context_descendant(child[0], base_ref=base[0],
        model_id='ieee39', revision_ref=base[1])


def test_authority_rejects_tampered_lineage_and_excess_depth(tmp_path):
    base = _write_context_chain(tmp_path)
    child = _write_context_chain(tmp_path, parent=base, marker='child')
    authority = ContentReferenceVerifier(tmp_path)
    context = authority.verify_context(child[0]).document
    path = tmp_path / 'evidence' / 'revisions' / (context['lineage_ref'].split(':')[-1] + '.json')
    path.write_text('{}')
    assert not authority.verify_context_descendant(child[0], base_ref=base[0], model_id='ieee39', revision_ref=child[1])
    current = base
    for index in range(64):
        current = _write_context_chain(tmp_path, parent=current, marker=f'depth-{index}')
    assert not authority.verify_context_descendant(current[0], base_ref=base[0], model_id='ieee39', revision_ref=current[1])


def test_authority_rejects_foreign_root_and_missing_lineage(tmp_path):
    base = _write_context_chain(tmp_path)
    foreign = _write_context_chain(tmp_path, marker='foreign')
    child = _write_context_chain(tmp_path, parent=foreign, marker='child')
    authority = ContentReferenceVerifier(tmp_path)
    assert not authority.verify_context_descendant(child[0], base_ref=base[0],
        model_id='ieee39', revision_ref=child[1])
    for path in (tmp_path / 'evidence/revisions').glob('*.json'):
        path.unlink()
    assert not authority.verify_context_descendant(child[0], base_ref=foreign[0],
        model_id='ieee39', revision_ref=child[1])


def test_authority_rejects_leaf_and_parent_symlinks(tmp_path: Path) -> None:
    other_run = tmp_path / "other-run"
    result_ref, other_path = _write_result(other_run)

    leaf_run = tmp_path / "leaf-run"
    leaf_path = leaf_run / "evidence/results" / other_path.name
    leaf_path.parent.mkdir(parents=True)
    leaf_path.symlink_to(other_path)

    parent_run = tmp_path / "parent-run"
    (parent_run / "evidence").mkdir(parents=True)
    (parent_run / "evidence/results").symlink_to(other_path.parent)

    with pytest.raises(SimulatorIntegrityError, match="current run|could not be read"):
        ContentReferenceVerifier(leaf_run).verify_result(result_ref)
    with pytest.raises(SimulatorIntegrityError, match="current run|could not be read"):
        ContentReferenceVerifier(parent_run).verify_result(result_ref)


def test_authority_does_not_admit_a_reference_from_another_run(tmp_path: Path) -> None:
    result_ref, _ = _write_result(tmp_path / "other-run")
    current_run = tmp_path / "current-run"
    (current_run / "evidence/results").mkdir(parents=True)

    with pytest.raises(SimulatorIntegrityError, match="current run"):
        ContentReferenceVerifier(current_run).verify_result(result_ref)


def test_authority_detects_a_named_file_exchange_after_open(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_root = tmp_path / "run"
    result_ref, result_path = _write_result(run_root)
    outside_ref, outside_path = _write_result(tmp_path / "outside")
    assert outside_ref == result_ref
    original_read = os.read
    exchanged = False

    def exchange_before_read(descriptor: int, count: int) -> bytes:
        nonlocal exchanged
        if not exchanged:
            exchanged = True
            result_path.unlink()
            result_path.symlink_to(outside_path)
        return original_read(descriptor, count)

    monkeypatch.setattr(authority_module.os, "read", exchange_before_read)

    with pytest.raises(SimulatorIntegrityError, match="binding changed"):
        ContentReferenceVerifier(run_root).verify_result(result_ref)
    assert exchanged


def _write_result(run_root: Path) -> tuple[str, Path]:
    body = {
        "context_ref": "context:sha256:" + "1" * 64,
        "revision_ref": "revision:sha256:" + "2" * 64,
        "result_type": "analysis.powerflow.ac",
        "converged": True,
    }
    digest = hashlib.sha256(_canonical_json(body).encode("utf-8")).hexdigest()
    result_ref = f"result:sha256:{digest}"
    path = run_root / "evidence/results" / f"result-{digest}.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        _canonical_json({"result_ref": result_ref, **body}),
        encoding="utf-8",
    )
    return result_ref, path
