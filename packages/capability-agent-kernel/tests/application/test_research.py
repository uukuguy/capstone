from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from capability_agent.application.context_models import ContextEventDraft
from capability_agent.application.context_store import ApplicationContextStore, ContextStoreError
from capability_agent.application.research import ResearchController
from capability_agent.application.workspace import ApplicationWorkspace

REF = "result:sha256:" + "a" * 64


@pytest.fixture
def store(tmp_path):
    workspace = ApplicationWorkspace.create(tmp_path / "runs", run_id="run-1", binding_ids=())
    store = ApplicationContextStore.initialize(workspace)
    store.append(ContextEventDraft(event_type="turn.started", turn_id="turn-1", payload={"ordinal": 1}))
    return store


def controller(store, *, turn="turn-1", refs=()):
    return ResearchController(
        store, research_id="research-1", turn_id=turn,
        admit_reference=lambda ref: ref in refs,
    )


def request(request_id="update-1", revision=0, **changes):
    initial = {"goal": "Check the selected model"} if revision == 0 else {}
    return {"request_id": request_id, "expected_revision": revision, "changes": {**initial, **changes}}


def test_update_is_durable_and_returns_committed_revision(store):
    research = controller(store)
    receipt = research.update(request())
    assert receipt.research_revision == 1
    assert research.read().goal == "Check the selected model"
    assert ApplicationContextStore.replay(store.workspace).core.research == research.read()
    assert store.verify_materialized_snapshot() == store.snapshot


def test_retry_after_reopen_returns_original_receipt_without_new_event(store):
    first = controller(store).update(request())
    ledger = store.workspace.context_events_path.read_bytes()
    reopened = ApplicationContextStore(store.workspace, ApplicationContextStore.replay(store.workspace))
    assert controller(reopened).update(request()) == first
    assert reopened.workspace.context_events_path.read_bytes() == ledger


def test_same_request_id_with_different_content_is_rejected(store):
    research = controller(store)
    research.update(request())
    with pytest.raises(ContextStoreError, match="request identity"):
        research.update(request(goal="Different goal"))
    assert research.read().revision == 1


def test_revision_conflict_does_not_change_ledger(store):
    research = controller(store)
    research.update(request())
    ledger = store.workspace.context_events_path.read_bytes()
    with pytest.raises(ContextStoreError, match="research revision conflict"):
        research.update(request("update-2", 0, goal="Changed"))
    assert store.workspace.context_events_path.read_bytes() == ledger


def test_ended_turn_rejects_new_update_but_committed_retry_is_readable(store):
    research = controller(store)
    receipt = research.update(request())
    store.append(ContextEventDraft(event_type="turn.completed", turn_id="turn-1", payload={}))
    assert research.update(request()) == receipt
    with pytest.raises(ContextStoreError, match="active turn"):
        research.update(request("update-2", 1, goal="Late"))


def test_followup_turn_can_continue_the_same_research(store):
    controller(store).update(request())
    store.append(ContextEventDraft(event_type="turn.completed", turn_id="turn-1", payload={}))
    store.append(ContextEventDraft(event_type="turn.started", turn_id="turn-2", payload={"ordinal": 2}))
    research = controller(store, turn="turn-2")
    research.update(request("followup-1", 1, open_questions=["Does the result still apply?"]))
    assert research.read().revision == 2
    assert research.read().goal == "Check the selected model"


def test_unadmitted_reference_cannot_enter_research_or_authority_state(store):
    before = store.snapshot
    with pytest.raises(ContextStoreError, match="reference is not admitted"):
        controller(store).update(request(condition_refs=[REF]))
    assert store.snapshot == before


def test_supported_claim_requires_evidence_and_does_not_register_authority_result(store):
    research = controller(store, refs=(REF,))
    research.update(request(claims=[{"claim_id": "claim-1", "statement": "Observation supports the goal", "status": "supported", "refs": [REF]}]))
    assert research.read().claims[0].refs == (REF,)
    assert store.snapshot.core.result_refs == ()
    assert store.snapshot.core.evidence_refs == ()
    with pytest.raises(ContextStoreError, match="invalid research update"):
        research.update(request("update-2", 1, claims=[{"claim_id": "claim-2", "statement": "Unfounded", "status": "supported"}]))


def test_changing_conditions_marks_prior_claims_pending(store):
    research = controller(store, refs=(REF,))
    research.update(request(claims=[{"claim_id": "claim-1", "statement": "A supported observation", "status": "supported", "refs": [REF]}]))
    research.update(request("update-2", 1, condition_refs=[REF]))
    assert research.read().claims[0].status == "pending"
    assert research.read().claims[0].refs == (REF,)


def test_claim_revision_keeps_prior_statement_in_event_history(store):
    research = controller(store, refs=(REF,))
    research.update(request(claims=[{"claim_id": "claim-1", "statement": "First hypothesis"}]))
    research.update(request("update-2", 1, claims=[{"claim_id": "claim-1", "statement": "Counterexample found", "status": "refuted", "refs": [REF]}]))
    assert len(research.read().claims) == 1
    assert research.read().claims[0].status == "refuted"
    assert "First hypothesis" in store.workspace.context_events_path.read_text()


def test_duplicate_claim_ids_and_oversized_input_are_rejected(store):
    research = controller(store)
    claim = {"claim_id": "claim-1", "statement": "Hypothesis"}
    for changes in ({"claims": [claim, claim]}, {"goal": "x" * 4001}, {}):
        with pytest.raises(ContextStoreError, match="invalid research update"):
            research.update({"request_id": "bad", "expected_revision": 0, "changes": changes})
    assert research.read() is None


def test_initial_update_requires_goal_and_rejects_caller_identity_fields(store):
    research = controller(store)
    with pytest.raises(ContextStoreError, match="initial research goal"):
        research.update({"request_id": "update-1", "expected_revision": 0, "changes": {"open_questions": ["What is the target?"]}})
    for key in ("turn_id", "research_id", "run_id"):
        with pytest.raises(ContextStoreError, match="invalid research update"):
            research.update({**request(), key: "caller-selected"})


def test_two_concurrent_updates_at_same_revision_have_one_winner(store):
    research = controller(store)
    def submit(number):
        try:
            return research.update(request(f"update-{number}", 0, goal=f"Goal {number}"))
        except ContextStoreError:
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(submit, (1, 2)))
    assert sum(item is not None for item in outcomes) == 1
    assert research.read().revision == 1
    assert store.verify_materialized_snapshot() == store.snapshot


def test_persistence_failure_does_not_return_success(store, monkeypatch):
    import capability_agent.application.context_store as module
    def fail(*args, **kwargs):
        raise OSError("injected write failure")
    monkeypatch.setattr(module, "_stage_bytes", fail)
    with pytest.raises(ContextStoreError, match="persistence failed"):
        controller(store).update(request())
    assert store.snapshot.core.research is None


def test_pre_research_ledger_replays_with_original_hashes():
    legacy = Path(__file__).parent / "fixtures" / "pre-research-context.jsonl"
    snapshot = ApplicationContextStore.replay(legacy)
    assert getattr(snapshot.core, "research", "missing") is None
    assert "research" not in snapshot.core.model_dump(mode="json")


def test_public_application_api_exports_research_contracts():
    from capability_agent import application
    assert getattr(application, "ResearchController", None) is ResearchController
    assert getattr(application, "ResearchState", None) is not None


def test_duplicate_receipt_rejects_ledger_that_no_longer_matches_memory(store):
    research = controller(store)
    research.update(request())
    second_store = ApplicationContextStore(store.workspace, store.snapshot)
    controller(second_store).update(request("update-2", 1, goal="Updated elsewhere"))
    with pytest.raises(ContextStoreError, match="ledger does not match"):
        research.update(request())


def test_notes_append_without_overwriting_prior_exploration(store):
    research = controller(store)
    research.update(request(notes=[{"note_id": "note-1", "text": "First method failed"}]))
    research.update(request("update-2", 1, notes=[{"note_id": "note-2", "text": "Try a different method"}]))
    assert len(research.read().notes) == 2
    with pytest.raises(ContextStoreError, match="note identity"):
        research.update(request("update-3", 2, notes=[{"note_id": "note-1", "text": "Overwrite history"}]))


@pytest.mark.parametrize("snapshot_replaced", [False, True])
def test_interrupted_commit_recovers_and_retry_does_not_apply_twice(store, monkeypatch, snapshot_replaced):
    import capability_agent.application.context_store as module
    previous = store.snapshot
    replace_snapshot = module._replace_snapshot
    def interrupt_snapshot(source, destination):
        if snapshot_replaced:
            replace_snapshot(source, destination)
        raise KeyboardInterrupt("simulated interruption")
    def interrupt_rollback(*args, **kwargs):
        raise KeyboardInterrupt("simulated interruption")
    with monkeypatch.context() as patch:
        patch.setattr(module, "_replace_snapshot", interrupt_snapshot)
        patch.setattr(module, "_rollback_transaction", interrupt_rollback)
        with pytest.raises(KeyboardInterrupt):
            controller(store).update(request())
    recovered = ApplicationContextStore(store.workspace, previous)
    receipt = controller(recovered).update(request())
    assert receipt.research_revision == 1
    assert recovered.snapshot.core.research.revision == 1
    assert recovered.verify_materialized_snapshot() == recovered.snapshot
