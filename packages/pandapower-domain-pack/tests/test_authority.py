from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

import pandapower_domain.authority as authority_module
from pandapower_domain import PandapowerArtifactAuthority, build_pandapower_profile
from pandapower_domain.authority import ContentReferenceVerifier, SimulatorIntegrityError


def test_context_descendant_requires_verified_same_model_ancestry(tmp_path: Path) -> None:
    models = tmp_path / "evidence" / "models"
    contexts = tmp_path / "evidence" / "contexts"
    models.mkdir(parents=True)
    contexts.mkdir()

    def context(model: str, parent: str | None, state: int) -> str:
        revision = _canonical_json({"state": state}).encode()
        digest = hashlib.sha256(revision).hexdigest()
        (models / f"{digest}.json").write_bytes(revision)
        payload = _canonical_json({"model_id": model, "parent_context_ref": parent,
                                   "revision_ref": f"revision:sha256:{digest}"}).encode()
        key = hashlib.sha256(payload).hexdigest()
        (contexts / f"{key}.json").write_bytes(payload)
        return f"context:sha256:{key}"

    root = context("grid", None, 0)
    child = context("grid", root, 1)
    leaf = context("grid", child, 2)
    authority = PandapowerArtifactAuthority(tmp_path)
    assert authority.verify_context_descendant(leaf, root).reference == leaf
    assert authority.verify_context_descendant(root, root).reference == root
    with pytest.raises(SimulatorIntegrityError, match="not derived"):
        authority.verify_context_descendant(context("grid", None, 3), root)
    with pytest.raises(SimulatorIntegrityError, match="crosses model"):
        authority.verify_context_descendant(context("other", child, 4), root)
    (contexts / f"{child.rsplit(':', 1)[1]}.json").write_text('{}')
    with pytest.raises(SimulatorIntegrityError, match="digest"):
        authority.verify_context_descendant(leaf, root)


def test_pandapower_authority_matches_current_run_verifier(tmp_path: Path, monkeypatch) -> None:
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
    recovered = authority.recover_references()
    assert recovered == {'authority_id': 'gridctl', 'capability_id': 'legacy.workspace.read',
                         'result_refs': [result_ref], 'evidence_refs': [evidence_ref], 'context_refs': [context_ref]}

    (evidence_root / 'results' / 'unrelated.json').write_text('{}')
    staged = tmp_path / 'delegated-read'
    authority.stage_read_inputs(staged, [result_ref], [evidence_ref])
    target = PandapowerArtifactAuthority(staged)
    assert target.verify_result(result_ref).document == result_body | {'result_ref': result_ref}
    assert target.verify_evidence(evidence_ref).document == evidence_body
    assert hashlib.sha256(target.verify_evidence(evidence_ref).path.read_bytes()).hexdigest() == evidence_digest
    assert target.verify_context(context_ref).document == context
    context_only = tmp_path / 'delegated-context'
    authority.stage_read_inputs(context_only, [], [], [context_ref], [revision_ref])
    assert PandapowerArtifactAuthority(context_only).verify_context(context_ref).document == context
    assert not (context_only / 'evidence' / 'results').exists()
    with pytest.raises(SimulatorIntegrityError, match='requested revision'):
        authority.stage_read_inputs(tmp_path / 'wrong-revision', [], [], [context_ref],
                                    ['revision:sha256:' + 'a' * 64])
    assert not (staged / 'evidence' / 'results' / 'unrelated.json').exists()
    with pytest.raises(SimulatorIntegrityError, match='linked result and evidence'):
        authority.stage_read_inputs(tmp_path / 'rejected', [], [evidence_ref])

    from pandapower_domain.execution import GridctlExecutor
    from pandapower_domain.tool_service import PandapowerToolService

    service = PandapowerToolService(workspace_root=tmp_path)
    service._capabilities = {'read': 'result.read', 'write': 'result.write'}
    service._read_only = {'read': True, 'write': False}
    monkeypatch.setattr(service, '_executor', lambda workspace:
        GridctlExecutor(executable=tmp_path / 'unused', workspace=tmp_path / workspace))
    called = []

    def run(executor, request, **kwargs):
        assert executor.workspace.name.startswith('grant-')
        isolated = PandapowerArtifactAuthority(executor.workspace)
        call = json.loads(request)
        if call['arguments'].get('context_ref'):
            assert isolated.verify_context(context_ref).document == context
            body = {'context_ref': context_ref, 'revision_ref': revision_ref}
        else:
            assert isolated.verify_result(result_ref).reference == result_ref
            assert isolated.verify_evidence(evidence_ref).reference == evidence_ref
            body = result
        called.append(executor.workspace)
        response = {**call, 'ok': True, 'result': body}
        return 0, (json.dumps(response) + '\n').encode(), b'', False

    monkeypatch.setattr(GridctlExecutor, '_run_bounded', run)
    grant = dict(owner='run', authority_id='gridctl', result_refs=[result_ref], evidence_refs=[evidence_ref])
    document = dict(task_id='consumer', call_id='read', name='read', arguments={'result_ref': result_ref})
    received = service.invoke(document, workspace_id='consumer', authority_inputs=[grant])
    assert received['ok'] is True
    assert received['authority_references']['result_refs'] == [result_ref]
    assert received['authority_references']['evidence_refs'] == [evidence_ref]
    assert len(called) == 1 and not called[0].exists()
    assert service.invoke({**document, 'name': 'write'}, workspace_id='consumer', authority_inputs=[grant])['ok'] is False
    assert service.invoke({**document, 'arguments': {**document['arguments'],
        'evidence_ref': 'evidence:sha256:' + 'a' * 64}},
        workspace_id='consumer', authority_inputs=[grant])['ok'] is False
    assert len(called) == 1
    context_grant = {**grant, 'context_refs': [context_ref], 'result_refs': [], 'evidence_refs': []}
    read_context = {**document, 'call_id': 'read-context',
                    'arguments': {'context_ref': context_ref, 'revision_ref': revision_ref}}
    receipt = service.invoke(read_context, workspace_id='consumer', authority_inputs=[context_grant])
    assert receipt['ok'] is True
    assert receipt['authority_references']['context_refs'] == [context_ref]
    assert receipt['authority_references']['result_refs'] == receipt['authority_references']['evidence_refs'] == []
    assert not called[-1].exists()

    legacy_id = 'pi-' + 'a' * 64
    run_root.rename(tmp_path / legacy_id)
    ledger = tmp_path / legacy_id / 'execution-receipts'
    ledger.mkdir()
    proof = {'task_id': legacy_id, 'call_id': 'invocation'}
    (ledger / ('1' * 32 + '.json')).write_text(json.dumps(proof))
    assert service.recover(proof) == recovered
    with pytest.raises(ValueError, match='does not match'):
        service.recover({**proof, 'call_id': 'other'})


def _canonical_json(document: object) -> str:
    return json.dumps(
        document,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )


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
