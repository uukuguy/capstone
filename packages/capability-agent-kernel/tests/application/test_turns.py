from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

import pytest

import capability_agent._safe_files as safe_files_module
import capability_agent.application.context_store as context_store_module
from capability_agent.application.context_models import ContextEventDraft
from capability_agent.application.context_store import ApplicationContextStore
from capability_agent.application.errors import AnswerCommitError
from capability_agent.application.workspace import ApplicationWorkspace
from capability_agent.application.turns import TurnController
from capability_agent.domain.answer_admission import (
    AnswerAdmissionDecision,
    AnswerAdmissionInput,
    read_answer_admission_metadata,
)


RESULT_REF = "result:opaque:one"
EVIDENCE_REF = "evidence:opaque:one"


@dataclass
class RecordingPolicy:
    submissions: list[object] = field(default_factory=list)
    claims: list[object] = field(default_factory=list)

    def validate_claim(self, claim: object) -> None:
        self.claims.append(claim)

    def validate_submission(self, submission: object) -> None:
        self.submissions.append(submission)


@dataclass
class RecordingAdmissionPolicy:
    requests: list[AnswerAdmissionInput] = field(default_factory=list)

    def admit(self, request: AnswerAdmissionInput) -> AnswerAdmissionDecision:
        self.requests.append(request)
        return AnswerAdmissionDecision(
            mode="authority_backed" if request.result_refs else "limited",
            assurance="lineage_verified" if request.result_refs else "limited",
            answer_output=request.answer_output,
            diagnostic_codes=(),
        )


@dataclass
class RecordingAuthority:
    workspace_root: Path
    authority_id: str = "grid-authority"
    result_refs: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    foreign_artifact: bool = False
    raise_base_exception: bool = False
    failure: Exception | None = None

    def verify_result(self, reference: str) -> object:
        self.result_refs.append(reference)
        if self.raise_base_exception:
            raise KeyboardInterrupt("backend interrupt")
        if self.failure is not None:
            raise self.failure
        if self.foreign_artifact:
            return SimpleNamespace(
                reference=reference,
                path=self.workspace_root.parent / "foreign-run" / "result.json",
            )
        return object()

    def verify_evidence(self, reference: str) -> object:
        self.evidence_refs.append(reference)
        return object()

    def audit_answer_references(
        self, claim_evidence_refs: tuple[str, ...], result_refs: tuple[str, ...]
    ) -> tuple[object, ...]:
        del claim_evidence_refs, result_refs
        return ()


def _prepared_binding(workspace: ApplicationWorkspace, policy: RecordingPolicy, binding_id="grid") -> object:
    authority = RecordingAuthority(workspace.domain_roots[binding_id])
    admission = RecordingAdmissionPolicy()
    profile = SimpleNamespace(
        answer_policy=policy,
        create_answer_admission_policy=lambda current_authority: admission,
        answer_admission_capabilities=frozenset(
            {"authority_backed", "offline_information", "limited"}
        ),
        manifest=SimpleNamespace(authority_id=authority.authority_id),
    )
    return SimpleNamespace(
        binding=SimpleNamespace(binding_id=binding_id, profile=profile),
        runtime=SimpleNamespace(authority=authority),
        admission=admission,
    )


def _record_current_refs(current: object, *refs: str) -> None:
    current.store.append(ContextEventDraft(
        event_type="tool.observation.recorded", turn_id=current.handle.turn_id,
        payload={"binding_id": "grid", "turn_id": current.handle.turn_id, "result_refs": list(refs)},
    ))


@pytest.fixture
def active_turn(tmp_path: Path) -> tuple[ApplicationContextStore, ApplicationWorkspace, object]:
    workspace = ApplicationWorkspace.create(
        tmp_path / "runs", run_id="run-1", binding_ids=("grid",)
    )
    store = ApplicationContextStore.initialize(
        workspace, domains={"grid": "grid-state/1.0"}
    )
    policy = RecordingPolicy()
    prepared = _prepared_binding(workspace, policy)
    controller = TurnController(
        store=store,
        workspace=workspace,
        bindings={"grid": prepared},
        allowed_refs={RESULT_REF, EVIDENCE_REF},
    )
    handle = controller.start(1, "Inspect the registered resource")
    return store, workspace, SimpleNamespace(
        store=store,
        workspace=workspace,
        handle=handle,
        prepared=prepared,
        policy=policy,
    )


def test_submit_uses_selected_binding_answer_policy(active_turn) -> None:
    _store, _workspace, current = active_turn
    controller = TurnController(
        store=current.store,
        workspace=current.workspace,
        bindings={"grid": current.prepared},
        allowed_refs={RESULT_REF, EVIDENCE_REF},
    )
    _record_current_refs(current, RESULT_REF, EVIDENCE_REF)

    committed = controller.submit(
        current.handle,
        answer_output="verified answer",
        referenced_bindings=("grid",),
        result_refs=(RESULT_REF,),
        evidence_refs=(EVIDENCE_REF,),
        duration_seconds=1.0,
    )

    assert committed.referenced_bindings == ("grid",)
    assert current.policy.submissions
    assert current.policy.submissions[-1].referenced_bindings == ("grid",)
    assert committed.admission is not None
    assert committed.admission.assurance == "lineage_verified"
    assert current.store.snapshot.core.active_turn is None


def test_submit_calls_domain_admission_for_a_zero_reference_answer(active_turn) -> None:
    _store, _workspace, current = active_turn
    controller = TurnController(
        store=current.store,
        workspace=current.workspace,
        bindings={"grid": current.prepared},
    )

    committed = controller.submit(
        current.handle,
        answer_output="unverified business assertion",
        duration_seconds=1.0,
    )

    admission = current.prepared.admission
    assert admission.requests == [
        AnswerAdmissionInput(
            question=current.handle.instruction,
            answer_output="unverified business assertion",
            result_refs=(),
            evidence_refs=(),
        )
    ]
    assert committed.status == "success"
    assert committed.answer_output == "unverified business assertion"


def test_submit_persists_answer_summary_without_changing_formal_answer(active_turn) -> None:
    _store, workspace, current = active_turn
    controller = TurnController(
        store=current.store,
        workspace=workspace,
        bindings={"grid": current.prepared},
    )

    committed = controller.submit(
        current.handle,
        answer_output="完整正式回答。",
        answer_summary="正式回答的过程摘要。",
        duration_seconds=1.0,
    )

    answer = json.loads(
        (workspace.turns_path / current.handle.turn_id / "answer.json").read_text()
    )
    events = list(ApplicationContextStore.replay_events(workspace)[1])
    assert committed.answer_output == "完整正式回答。"
    assert committed.answer_summary == "正式回答的过程摘要。"
    assert answer["answer_output"] == "完整正式回答。"
    assert answer["answer_summary"] == "正式回答的过程摘要。"
    assert any(
        event.event_type == "answer.submitted"
        and event.payload.get("answer_summary") == "正式回答的过程摘要。"
        for event in events
    )


@pytest.mark.parametrize("evaluation_fails", [False, True])
def test_evaluation_cannot_rewrite_or_fail_primary_answer(active_turn, evaluation_fails):
    _store, _workspace, current = active_turn

    def evaluate(request):
        if evaluation_fails:
            raise RuntimeError("evaluation unavailable")
        return AnswerAdmissionDecision("limited", "limited", "replacement text", ())

    current.prepared.binding.profile.create_answer_admission_policy = lambda authority: SimpleNamespace(admit=evaluate)
    controller = TurnController(store=current.store, workspace=current.workspace,
                                bindings={"grid": current.prepared})
    committed = controller.submit(current.handle, answer_output="original primary answer", duration_seconds=1.0)
    assert committed.status == "success"
    assert committed.answer_output == "original primary answer"
    assert committed.admission.assurance == "limited"
    if evaluation_fails:
        assert committed.admission.diagnostic_codes == ("answer_evaluation_unavailable",)


@pytest.mark.parametrize(("contract", "ok", "blocks_guide"), [
    ({"evidence_required": False, "state_effect": "none"}, True, False),
    ({"evidence_required": False, "state_effect": "none"}, False, True),
    ({"evidence_required": True, "state_effect": "none"}, True, True),
    ({"evidence_required": False, "state_effect": "write"}, True, True),
    ({}, True, True),
])
def test_guide_guard_uses_success_and_published_contract(active_turn, contract, ok, blocks_guide) -> None:
    _store, _workspace, current = active_turn
    current.prepared.runtime.capability_documents = ({"id": "generic.lookup", **contract},)
    current.store.append(ContextEventDraft(
        event_type="tool.observation.recorded", binding_id="grid", turn_id=current.handle.turn_id,
        payload={"binding_id": "grid", "turn_id": current.handle.turn_id,
                 "capability_id": "generic.lookup", "ok": ok},
    ))
    controller = TurnController(store=current.store, workspace=current.workspace,
                                bindings={"grid": current.prepared})
    controller.submit(current.handle, answer_output="reader text", duration_seconds=1.0)
    assert current.prepared.admission.requests[-1].authority_attempted is blocks_guide


@pytest.mark.parametrize("guide", [False, True])
def test_admission_sidecar_binds_answer_and_legacy_answers_are_unknown(active_turn, guide) -> None:
    _store, workspace, current = active_turn
    if guide:
        current.prepared.admission.admit = lambda request: AnswerAdmissionDecision(
            "offline_information", "guide_access_verified", request.answer_output, (),
        )
        current.store.append(ContextEventDraft(
            event_type="tool.observation.recorded", turn_id=current.handle.turn_id,
            payload={"binding_id": "grid", "turn_id": current.handle.turn_id,
                     "kind": "published_guide_read", "resource_id": "guide", "sha256": "a" * 64},
        ))
    controller = TurnController(
        store=current.store, workspace=workspace, bindings={"grid": current.prepared}
    )
    committed = controller.submit(
        current.handle, answer_output="answer", duration_seconds=1.0
    )

    assert committed.answer_path is not None
    assert json.loads(committed.answer_path.with_name("answer-admission.json").read_text())["schema"] == (
        "capability-agent-answer-admission/1.1" if guide else "capability-agent-answer-admission/1.0"
    )
    admission_ref = current.store.snapshot.core.answer_lifecycle["admission_ref"]
    assert read_answer_admission_metadata(
        committed.answer_path, expected_admission_ref=admission_ref
    ) == committed.admission
    with pytest.raises(ValueError, match="durable commit"):
        read_answer_admission_metadata(committed.answer_path)
    legacy = workspace.turns_path / "legacy" / "answer.json"
    legacy.parent.mkdir()
    legacy.write_text('{"answer_output":"old"}', encoding="utf-8")
    assert read_answer_admission_metadata(legacy) is None
    legacy.with_name("answer-admission.json").write_text(
        json.dumps({"schema": "capability-agent-answer-admission/1.0"}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="durable commit"):
        read_answer_admission_metadata(legacy)
    legacy.with_name("answer-admission.json").unlink()
    with pytest.raises(ValueError, match="missing"):
        read_answer_admission_metadata(legacy, expected_admission_ref=admission_ref)

    sidecar = committed.answer_path.with_name("answer-admission.json")
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    payload["mode"] = "authority_backed"
    sidecar.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="digest"):
        read_answer_admission_metadata(
            committed.answer_path, expected_admission_ref=admission_ref
        )


def test_admission_reader_rejects_sidecar_replaced_while_reading(
    active_turn, monkeypatch: pytest.MonkeyPatch
) -> None:
    _store, workspace, current = active_turn
    controller = TurnController(
        store=current.store, workspace=workspace, bindings={"grid": current.prepared}
    )
    committed = controller.submit(
        current.handle, answer_output="answer", duration_seconds=1.0
    )
    assert committed.answer_path is not None
    sidecar = committed.answer_path.with_name("answer-admission.json")
    replacement = sidecar.with_name("replacement-admission.json")
    replacement.write_bytes(sidecar.read_bytes())
    real_stat = safe_files_module.os.stat
    replaced = False

    def replace_before_named_identity(*args: object, **kwargs: object):
        nonlocal replaced
        if not replaced and args and args[0] == "answer-admission.json":
            replaced = True
            replacement.replace(sidecar)
        return real_stat(*args, **kwargs)

    monkeypatch.setattr(
        safe_files_module.os, "stat", replace_before_named_identity
    )

    with pytest.raises(ValueError, match="unreadable"):
        read_answer_admission_metadata(
            committed.answer_path, expected_admission_ref=committed.admission_ref
        )


def test_admission_reader_rejects_a_symlinked_turns_ancestor(active_turn) -> None:
    _store, workspace, current = active_turn
    controller = TurnController(
        store=current.store, workspace=workspace, bindings={"grid": current.prepared}
    )
    committed = controller.submit(
        current.handle, answer_output="answer", duration_seconds=1.0
    )
    assert committed.answer_path is not None
    original_turns = workspace.root / "original-turns"
    workspace.turns_path.rename(original_turns)
    workspace.turns_path.symlink_to(original_turns, target_is_directory=True)

    with pytest.raises(ValueError, match="unreadable"):
        read_answer_admission_metadata(
            committed.answer_path, expected_admission_ref=committed.admission_ref
        )


def test_submit_rejects_undeclared_binding_without_committing(active_turn) -> None:
    _store, _workspace, current = active_turn
    controller = TurnController(
        store=current.store,
        workspace=current.workspace,
        bindings={"grid": current.prepared},
        allowed_refs={RESULT_REF, EVIDENCE_REF},
    )

    with pytest.raises(AnswerCommitError, match="binding"):
        controller.submit(
            current.handle,
            answer_output="answer",
            referenced_bindings=("missing",),
            result_refs=(RESULT_REF,),
            evidence_refs=(EVIDENCE_REF,),
            duration_seconds=1.0,
        )

    assert current.store.snapshot.core.active_turn is not None
    assert current.store.snapshot.core.answer_lifecycle == {}


def test_submit_rejects_reference_not_admitted_for_current_turn(active_turn) -> None:
    _store, _workspace, current = active_turn
    controller = TurnController(
        store=current.store,
        workspace=current.workspace,
        bindings={"grid": current.prepared},
        allowed_refs=set(),
    )

    with pytest.raises(AnswerCommitError, match="current turn"):
        controller.submit(
            current.handle,
            answer_output="answer",
            referenced_bindings=("grid",),
            result_refs=(RESULT_REF,),
            evidence_refs=(EVIDENCE_REF,),
            duration_seconds=1.0,
        )

    assert current.store.snapshot.core.active_turn is not None


def test_submit_rejects_missing_required_evidence_from_domain_policy(active_turn) -> None:
    _store, _workspace, current = active_turn

    class RejectingPolicy(RecordingPolicy):
        def validate_submission(self, submission: object) -> None:
            super().validate_submission(submission)
            raise ValueError("required evidence is missing")

    current.prepared.binding.profile.answer_policy = RejectingPolicy()
    controller = TurnController(
        store=current.store,
        workspace=current.workspace,
        bindings={"grid": current.prepared},
        allowed_refs={RESULT_REF, EVIDENCE_REF},
    )
    _record_current_refs(current, RESULT_REF, EVIDENCE_REF)

    with pytest.raises(AnswerCommitError, match="evidence"):
        controller.submit(
            current.handle,
            answer_output="answer",
            referenced_bindings=("grid",),
            result_refs=(RESULT_REF,),
            evidence_refs=(EVIDENCE_REF,),
            duration_seconds=1.0,
        )

    assert current.store.snapshot.core.active_turn is not None


def test_submit_uses_only_current_turn_admissions(tmp_path: Path) -> None:
    workspace = ApplicationWorkspace.create(
        tmp_path / "runs", run_id="run-2", binding_ids=("grid",)
    )
    store = ApplicationContextStore.initialize(
        workspace, domains={"grid": "grid-state/1.0"}
    )
    policy = RecordingPolicy()
    prepared = _prepared_binding(workspace, policy)
    controller = TurnController(
        store=store,
        workspace=workspace,
        bindings={"grid": prepared},
        allowed_refs={RESULT_REF, EVIDENCE_REF},
    )
    handle = controller.start(1, "Inspect")
    store.append(
        ContextEventDraft(
            event_type="tool.observation.recorded",
            turn_id=handle.turn_id,
            payload={
                "binding_id": "grid",
                "turn_id": handle.turn_id,
                "result_refs": [RESULT_REF],
                "evidence_refs": [EVIDENCE_REF],
            },
        )
    )
    committed = controller.submit(
        handle,
        answer_output="answer",
        referenced_bindings=("grid",),
        result_refs=(RESULT_REF,),
        evidence_refs=(EVIDENCE_REF,),
        duration_seconds=0.1,
    )
    assert committed.answer_output == "answer"


def test_submit_rejects_prior_turn_reference_even_when_static_allowlist_contains_it(
    tmp_path: Path,
) -> None:
    workspace = ApplicationWorkspace.create(
        tmp_path / "runs", run_id="run-previous-ref", binding_ids=("grid",)
    )
    store = ApplicationContextStore.initialize(
        workspace, domains={"grid": "grid-state/1.0"}
    )
    prepared = _prepared_binding(workspace, RecordingPolicy())
    controller = TurnController(
        store=store,
        workspace=workspace,
        bindings={"grid": prepared},
        allowed_refs={RESULT_REF},
    )
    first = controller.start(1, "first")
    store.append(ContextEventDraft(
        event_type="tool.observation.recorded", turn_id=first.turn_id,
        payload={"binding_id": "grid", "turn_id": first.turn_id, "result_refs": [RESULT_REF]},
    ))
    controller.submit(first, answer_output="first", referenced_bindings=("grid",), result_refs=(RESULT_REF,), duration_seconds=0.1)
    second = controller.start(2, "second")

    with pytest.raises(AnswerCommitError, match="current turn"):
        controller.submit(second, answer_output="second", referenced_bindings=("grid",), result_refs=(RESULT_REF,), duration_seconds=0.1)


def test_submit_accepts_current_turn_reference_when_static_allowlist_also_allows_it(
    tmp_path: Path,
) -> None:
    workspace = ApplicationWorkspace.create(
        tmp_path / "runs", run_id="run-current-ref", binding_ids=("grid",)
    )
    store = ApplicationContextStore.initialize(
        workspace, domains={"grid": "grid-state/1.0"}
    )
    prepared = _prepared_binding(workspace, RecordingPolicy())
    controller = TurnController(store=store, workspace=workspace, bindings={"grid": prepared}, allowed_refs={RESULT_REF})
    handle = controller.start(1, "current")
    store.append(ContextEventDraft(
        event_type="tool.observation.recorded", turn_id=handle.turn_id,
        payload={"binding_id": "grid", "turn_id": handle.turn_id, "result_refs": [RESULT_REF]},
    ))

    committed = controller.submit(handle, answer_output="current", referenced_bindings=("grid",), result_refs=(RESULT_REF,), duration_seconds=0.1)

    assert committed.admission.assurance == "lineage_verified"


def test_submit_diagnoses_undeclared_evaluation_mode_without_veto(active_turn) -> None:
    _store, _workspace, current = active_turn
    current.prepared.binding.profile.answer_admission_capabilities = frozenset(
        {"authority_backed", "limited"}
    )
    current.prepared.admission.admit = lambda request: AnswerAdmissionDecision(
        mode="offline_information",
        assurance="deterministic_information",
        answer_output="guide",
        diagnostic_codes=(),
    )
    controller = TurnController(
        store=current.store, workspace=current.workspace, bindings={"grid": current.prepared}
    )

    committed = controller.submit(current.handle, answer_output="model", duration_seconds=0.1)
    assert committed.status == "success"
    assert committed.answer_output == "model"
    assert committed.admission.diagnostic_codes == ("answer_evaluation_unavailable",)


def test_submit_rejects_empty_admitted_answer(active_turn) -> None:
    _store, _workspace, current = active_turn
    controller = TurnController(
        store=current.store, workspace=current.workspace, bindings={"grid": current.prepared}
    )

    with pytest.raises(AnswerCommitError, match="must not be empty"):
        controller.submit(current.handle, answer_output="", duration_seconds=0.1)


def test_submit_rejects_foreign_run_reference_without_mutating_turn(active_turn) -> None:
    _store, _workspace, current = active_turn
    current.prepared.runtime.authority.foreign_artifact = True
    controller = TurnController(
        store=current.store,
        workspace=current.workspace,
        bindings={"grid": current.prepared},
        allowed_refs={RESULT_REF},
    )
    _record_current_refs(current, RESULT_REF)

    with pytest.raises(AnswerCommitError, match="evidence validation"):
        controller.submit(
            current.handle,
            answer_output="answer",
            referenced_bindings=("grid",),
            result_refs=(RESULT_REF,),
            duration_seconds=1.0,
        )

    assert current.store.snapshot.core.active_turn is not None
    assert current.store.snapshot.core.answer_lifecycle == {}


def test_submit_rejects_wrong_binding_authority(active_turn) -> None:
    _store, _workspace, current = active_turn
    current.prepared.runtime.authority.authority_id = "other-authority"
    controller = TurnController(
        store=current.store,
        workspace=current.workspace,
        bindings={"grid": current.prepared},
        allowed_refs={RESULT_REF},
    )
    _record_current_refs(current, RESULT_REF)

    with pytest.raises(AnswerCommitError, match="authority"):
        controller.submit(
            current.handle,
            answer_output="answer",
            referenced_bindings=("grid",),
            result_refs=(RESULT_REF,),
            duration_seconds=1.0,
        )

    assert current.store.snapshot.core.active_turn is not None


def test_submit_rejects_missing_required_evidence_before_commit(active_turn) -> None:
    _store, _workspace, current = active_turn

    class EvidenceRequiredPolicy(RecordingPolicy):
        def validate_submission(self, submission: object) -> None:
            super().validate_submission(submission)
            if not submission.claim_evidence_refs:
                raise ValueError("secret backend evidence rule")

    current.prepared.binding.profile.answer_policy = EvidenceRequiredPolicy()
    controller = TurnController(
        store=current.store,
        workspace=current.workspace,
        bindings={"grid": current.prepared},
        allowed_refs={RESULT_REF},
    )

    with pytest.raises(AnswerCommitError) as error:
        controller.submit(
            current.handle,
            answer_output="answer",
            referenced_bindings=("grid",),
            result_refs=(RESULT_REF,),
            duration_seconds=1.0,
        )

    assert "secret backend" not in str(error.value)
    assert current.store.snapshot.core.active_turn is not None


def test_submit_sanitizes_authority_errors(active_turn) -> None:
    _store, _workspace, current = active_turn
    current.prepared.runtime.authority.failure = RuntimeError("private backend token")
    controller = TurnController(
        store=current.store,
        workspace=current.workspace,
        bindings={"grid": current.prepared},
        allowed_refs={RESULT_REF},
    )

    with pytest.raises(AnswerCommitError) as error:
        controller.submit(
            current.handle,
            answer_output="answer",
            referenced_bindings=("grid",),
            result_refs=(RESULT_REF,),
            duration_seconds=1.0,
        )

    assert "private backend token" not in str(error.value)
    assert current.store.snapshot.core.active_turn is not None


def test_submit_does_not_swallow_base_exception_from_authority(active_turn) -> None:
    _store, _workspace, current = active_turn
    current.prepared.runtime.authority.raise_base_exception = True
    controller = TurnController(
        store=current.store,
        workspace=current.workspace,
        bindings={"grid": current.prepared},
        allowed_refs={RESULT_REF},
    )
    _record_current_refs(current, RESULT_REF)

    with pytest.raises(KeyboardInterrupt):
        controller.submit(
            current.handle,
            answer_output="answer",
            referenced_bindings=("grid",),
            result_refs=(RESULT_REF,),
            duration_seconds=1.0,
        )

    assert current.store.snapshot.core.active_turn is not None


def test_submit_rolls_back_answer_and_context_when_store_fails_mid_commit(
    active_turn, monkeypatch: pytest.MonkeyPatch
) -> None:
    _store, workspace, current = active_turn
    controller = TurnController(
        store=current.store,
        workspace=workspace,
        bindings={"grid": current.prepared},
    )
    before = current.store.snapshot
    before_lines = workspace.context_events_path.read_bytes()
    real_replace = context_store_module._replace_snapshot

    def replace_then_fail(source: Path, destination: Path) -> None:
        real_replace(source, destination)
        raise RuntimeError("storage backend secret")

    monkeypatch.setattr(context_store_module, "_replace_snapshot", replace_then_fail)

    with pytest.raises(AnswerCommitError, match="persistence") as error:
        controller.submit(
            current.handle,
            answer_output="answer",
            duration_seconds=1.0,
        )

    assert "storage backend secret" not in str(error.value)
    assert current.store.snapshot == before
    assert workspace.context_events_path.read_bytes() == before_lines
    assert not (workspace.turns_path / current.handle.turn_id / "answer.json").exists()
    assert not (
        workspace.turns_path / current.handle.turn_id / "answer-draft.json"
    ).exists()
    assert current.store.snapshot.core.active_turn is not None


def test_submit_rolls_back_sidecar_answer_drafts_and_context_when_sidecar_write_fails(
    active_turn, monkeypatch: pytest.MonkeyPatch
) -> None:
    _store, workspace, current = active_turn
    controller = TurnController(
        store=current.store,
        workspace=workspace,
        bindings={"grid": current.prepared},
    )
    before = current.store.snapshot
    before_lines = workspace.context_events_path.read_bytes()
    import capability_agent.application.turns as turns_module

    real_write = turns_module._write_bytes_atomic

    def fail_sidecar(path: Path, content: bytes) -> None:
        if path.name == "answer-admission.json":
            raise OSError("sidecar write failed")
        real_write(path, content)

    monkeypatch.setattr(turns_module, "_write_bytes_atomic", fail_sidecar)

    with pytest.raises(AnswerCommitError, match="persistence"):
        controller.submit(current.handle, answer_output="answer", duration_seconds=1.0)

    turn_path = workspace.turns_path / current.handle.turn_id
    assert current.store.snapshot == before
    assert workspace.context_events_path.read_bytes() == before_lines
    assert not (turn_path / "answer.json").exists()
    assert not (turn_path / "answer-draft.json").exists()
    assert not (turn_path / "answer-admission.json").exists()
    assert not (workspace.turns_path / "active-answer-draft.json").exists()
    assert current.store.snapshot.core.active_turn is not None


def test_recorder_failure_after_commit_preserves_success_and_replay(active_turn) -> None:
    _store, workspace, current = active_turn

    class FailingRecorder:
        def append(self, draft: object) -> None:
            raise OSError("trajectory unavailable")

    controller = TurnController(
        store=current.store,
        workspace=workspace,
        bindings={"grid": current.prepared},
        recorder=FailingRecorder(),
    )

    committed = controller.submit(
        current.handle,
        answer_output="original answer",
        duration_seconds=0.1,
    )

    assert committed.status == "success"
    assert committed.answer_output == "original answer"
    assert committed.post_commit_diagnostic_codes == ("trajectory_recording_unavailable",)
    assert committed.answer_path is not None and committed.answer_path.is_file()
    assert current.store.snapshot.core.turns[-1]["status"] == "success"
    assert ApplicationContextStore.replay(workspace.context_events_path) == current.store.snapshot
    assert not (workspace.turns_path / "active-turn.json").exists()


def test_committed_turn_replays_with_the_same_nonce_bound_lifecycle(active_turn) -> None:
    _store, workspace, current = active_turn
    controller = TurnController(
        store=current.store,
        workspace=workspace,
        bindings={"grid": current.prepared},
    )

    committed = controller.submit(
        current.handle,
        answer_output="answer",
        duration_seconds=1.0,
    )

    assert committed.answer_ref is not None
    assert ApplicationContextStore.replay(workspace.context_events_path) == current.store.snapshot


@pytest.fixture
def multi_turn(tmp_path):
    workspace = ApplicationWorkspace.create(tmp_path / "runs", run_id="multi", binding_ids=("grid", "inventory"))
    store = ApplicationContextStore.initialize(workspace, domains={key: "state/1.0" for key in workspace.domain_roots})
    bindings = {key: _prepared_binding(workspace, RecordingPolicy(), key) for key in workspace.domain_roots}
    controller = TurnController(store=store, workspace=workspace, bindings=bindings)
    handle = controller.start(1, "Inspect both systems")
    for key in bindings:
        store.append(ContextEventDraft(
            event_type="tool.observation.recorded", turn_id=handle.turn_id,
            payload={"binding_id": key, "turn_id": handle.turn_id,
                     "result_refs": [f"result:{key}"], "evidence_refs": [f"evidence:{key}"]},
        ))
    return SimpleNamespace(workspace=workspace, store=store, bindings=bindings, controller=controller, handle=handle)


def _multi_submit(current, **overrides):
    arguments = dict(
        answer_output="Both systems were checked.", referenced_bindings=("grid", "inventory"),
        result_refs=("result:grid", "result:inventory"),
        evidence_refs=("evidence:grid", "evidence:inventory"),
        claims=tuple(dict(statement=f"{key} checked", category="observation",
                          result_refs=(f"result:{key}",), evidence_refs=(f"evidence:{key}",))
                     for key in ("grid", "inventory")), duration_seconds=0.1,
    )
    arguments.update(overrides)
    return current.controller.submit(current.handle, **arguments)


@pytest.mark.parametrize("evaluation", ["verified", "limited", "raises", "invalid"])
def test_multi_binding_admission_preserves_owned_decisions_and_replay(multi_turn, evaluation):
    current = multi_turn
    if evaluation != "verified":
        def admit(request):
            if evaluation == "raises":
                raise RuntimeError("private evaluation error")
            return AnswerAdmissionDecision(
                "limited", "limited" if evaluation != "invalid" else "lineage_verified",
                "replacement", ("inventory_limited",),
            )
        current.bindings["inventory"].admission.admit = admit
    committed = _multi_submit(current)
    assert committed.admission.assurance == ("lineage_verified" if evaluation == "verified" else "limited")
    assert committed.status == "success"
    assert committed.answer_output == "Both systems were checked."
    assert committed.referenced_bindings == ("grid", "inventory")
    payload = json.loads(committed.answer_path.with_name("answer-admission.json").read_text())
    assert payload["schema"] == "capability-agent-answer-admission/1.2"
    assert list(payload["bindings"]) == ["grid", "inventory"]
    assert payload["bindings"]["grid"]["assurance"] == "lineage_verified"
    assert payload["bindings"]["inventory"]["assurance"] == committed.admission.assurance
    for key, binding in current.bindings.items():
        assert set(binding.runtime.authority.result_refs) == {f"result:{key}"}
        assert set(binding.runtime.authority.evidence_refs) == {f"evidence:{key}"}
        assert binding.binding.profile.answer_policy.submissions[-1].referenced_bindings == (key,)
    assert read_answer_admission_metadata(committed.answer_path, expected_admission_ref=committed.admission_ref) == committed.admission
    assert ApplicationContextStore.replay(current.workspace.context_events_path) == current.store.snapshot
    if evaluation == "verified":
        payload["bindings"]["grid"]["diagnostic_codes"] = ["tampered"]
        committed.answer_path.with_name("answer-admission.json").write_text(json.dumps(payload))
        with pytest.raises(ValueError, match="digest"):
            read_answer_admission_metadata(committed.answer_path, expected_admission_ref=committed.admission_ref)


@pytest.mark.parametrize("overrides, message", [
    ({"claims": (dict(statement="both", category="observation", result_refs=("result:grid", "result:inventory")),)}, "cross binding"),
    ({"referenced_bindings": ("grid", "unknown")}, "undeclared"),
    ({"result_refs": ("result:missing",)}, "current turn"),
    ({"claims": (dict(statement="unqualified", category="observation"),)}, "unqualified"),
    ({"referenced_bindings": ("grid",)}, "another binding"),
])
def test_multi_binding_rejects_ambiguous_or_foreign_references(multi_turn, overrides, message):
    with pytest.raises(AnswerCommitError, match=message):
        _multi_submit(multi_turn, **overrides)
    assert multi_turn.store.snapshot.core.active_turn is not None
    assert multi_turn.store.snapshot.core.answer_lifecycle == {}


@pytest.mark.parametrize("assurances, expected", [
    (("deterministic_information", "deterministic_information"), "deterministic_information"),
    (("guide_access_verified", "guide_access_verified"), "guide_access_verified"),
    (("deterministic_information", "guide_access_verified"), "limited"),
])
def test_multi_binding_offline_assurance_requires_unanimity(multi_turn, assurances, expected):
    for key, assurance in zip(multi_turn.bindings, assurances):
        multi_turn.bindings[key].admission.admit = lambda request, value=assurance: AnswerAdmissionDecision(
            "offline_information", value, "replacement", (),
        )
        multi_turn.store.append(ContextEventDraft(
            event_type="tool.observation.recorded", turn_id=multi_turn.handle.turn_id,
            payload={"binding_id": key, "turn_id": multi_turn.handle.turn_id,
                     "kind": "published_guide_read", "resource_id": "guide", "sha256": "a" * 64},
        ))
    committed = _multi_submit(multi_turn, result_refs=(), evidence_refs=(), claims=())
    assert committed.admission.assurance == expected
    assert committed.answer_output == "Both systems were checked."
    assert read_answer_admission_metadata(committed.answer_path, expected_admission_ref=committed.admission_ref) == committed.admission


@pytest.mark.parametrize("mutation", ["missing", "invalid", "aggregate", "codes"])
def test_multi_binding_reader_rejects_invalid_structure_even_with_matching_digest(multi_turn, mutation):
    from hashlib import sha256
    from capability_agent.trajectory.canonical import canonical_json_bytes

    committed = _multi_submit(multi_turn)
    sidecar = committed.answer_path.with_name("answer-admission.json")
    payload = json.loads(sidecar.read_text())
    if mutation == "missing":
        del payload["bindings"]["inventory"]
    elif mutation == "invalid":
        payload["bindings"]["inventory"]["assurance"] = "limited"
    elif mutation == "aggregate":
        payload["mode"], payload["assurance"] = "limited", "limited"
    else:
        payload["bindings"]["inventory"]["diagnostic_codes"] = ["unexpected"]
    content = canonical_json_bytes(payload)
    sidecar.write_bytes(content)
    with pytest.raises(ValueError, match="binding|aggregate"):
        read_answer_admission_metadata(
            committed.answer_path,
            expected_admission_ref="admission:sha256:" + sha256(content).hexdigest(),
        )
