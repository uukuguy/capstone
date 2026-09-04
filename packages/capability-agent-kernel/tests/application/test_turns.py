from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

import pytest

import capability_agent.application.context_store as context_store_module
import capability_agent.domain.answer_admission as answer_admission_module
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


def _prepared_binding(workspace: ApplicationWorkspace, policy: RecordingPolicy) -> object:
    authority = RecordingAuthority(workspace.domain_roots["grid"])
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
        binding=SimpleNamespace(binding_id="grid", profile=profile),
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
    assert committed.status == "limited"
    assert committed.answer_output == "unverified business assertion"


def test_admission_sidecar_binds_answer_and_legacy_answers_are_unknown(active_turn) -> None:
    _store, workspace, current = active_turn
    controller = TurnController(
        store=current.store, workspace=workspace, bindings={"grid": current.prepared}
    )
    committed = controller.submit(
        current.handle, answer_output="answer", duration_seconds=1.0
    )

    assert committed.answer_path is not None
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
    real_fstat = answer_admission_module.os.fstat
    fstat_calls = 0

    def replace_on_sidecar_open(descriptor: int):
        nonlocal fstat_calls
        fstat_calls += 1
        if fstat_calls == 3:
            replacement.replace(sidecar)
        return real_fstat(descriptor)

    monkeypatch.setattr(answer_admission_module.os, "fstat", replace_on_sidecar_open)

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


def test_submit_rejects_admission_mode_not_declared_by_selected_profile(active_turn) -> None:
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

    with pytest.raises(AnswerCommitError, match="declared"):
        controller.submit(current.handle, answer_output="model", duration_seconds=0.1)


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
