from __future__ import annotations

import pytest

from capstone_agent.thread_protocol import ThreadProtocolError, ThreadSnapshot
from capstone_agent.thread_service import AttemptClaim, InMemoryThreadService


REVISION = "revision:sha256:" + "a" * 64
RESULT_ONE = "result:sha256:" + "b" * 64
RESULT_TWO = "result:sha256:" + "c" * 64
EVIDENCE_ONE = "evidence:sha256:" + "d" * 64
EVIDENCE_TWO = "evidence:sha256:" + "e" * 64


def _service() -> InMemoryThreadService:
    return InMemoryThreadService.from_document({
        "schema": "capstone-thread-snapshot/1", "thread_id": "thr_projection",
        "run": {"run_id": "run_projection", "state": "open"},
        "active_model_context": {
            "id": "ctx_ieee39", "model_id": "ieee39", "model_revision": REVISION,
            "implementation_family": "pandapower", "selection_revision": "sel_0",
        },
        "active_grid_page_id": "page_ieee39", "current_attempt": None,
        "last_event_seq": 0, "base_event_seq": 0,
    })


def test_followup_claim_carries_only_results_for_the_exact_active_context():
    from dataclasses import replace
    from capstone_agent.thread_service import _prior_results_for_context

    service = _service()
    claim, projection = _claim_and_projection(service, 1, RESULT_ONE, EVIDENCE_ONE)
    _complete(service, claim, projection, RESULT_ONE, EVIDENCE_ONE)
    snapshot = service.snapshot("thr_projection")
    assert _prior_results_for_context(snapshot)[0].result_ref == RESULT_ONE
    assert _prior_results_for_context(snapshot)[0].evidence_refs == (EVIDENCE_ONE,)
    for changes in ({"id": "ctx_new"}, {"model_id": "case24_ieee_rts"}, {"model_revision": "revision:sha256:" + "f" * 64}):
        assert _prior_results_for_context(replace(snapshot, active_model_context=replace(snapshot.active_model_context, **changes))) == ()
    next_claim, _projection = _claim_and_projection(service, 2, RESULT_TWO, EVIDENCE_TWO)
    assert next_claim.prior_results[0].result_ref == RESULT_ONE


def test_prior_candidates_preserve_namespaced_public_references():
    from dataclasses import replace
    from capstone_agent.thread_service import _prior_results_for_context

    service = _service()
    claim, projection = _claim_and_projection(service, 1, RESULT_ONE, EVIDENCE_ONE)
    _complete(service, claim, projection, RESULT_ONE, EVIDENCE_ONE)
    snapshot = service.snapshot("thr_projection")
    item = replace(snapshot.result_projections[0], result_ref="pypsa-" + RESULT_ONE,
                   evidence_refs=("pypsa-" + EVIDENCE_ONE,), attempt_id="attempt:public.1")
    candidate = _prior_results_for_context(replace(snapshot, result_projections=(item,)))[0]
    assert candidate.result_ref == item.result_ref
    assert candidate.evidence_refs == item.evidence_refs
    assert candidate.attempt_id == item.attempt_id


def _claim_and_projection(
    service: InMemoryThreadService, ordinal: int, result_ref: str, evidence_ref: str,
) -> tuple[AttemptClaim, dict[str, object]]:
    snapshot = service.snapshot("thr_projection")
    receipt = service.submit_command({
        "schema": "capstone-command/1", "command_id": f"cmd_projection_{ordinal}",
        "idempotency_key": f"idem_projection_{ordinal}", "thread_id": "thr_projection",
        "run_id": "run_projection", "kind": "send_ordinary", "expected_event_seq": snapshot.last_event_seq,
        "payload": {"text": f"inspect {ordinal}"},
    })
    assert receipt.status == "accepted"
    claim = service.claim_attempt(f"worker-{ordinal}", lease_seconds=30)
    assert claim is not None
    projection = {
        "schema": "capstone-result-projection/1.0", "result_id": f"projection_{ordinal}",
        "result_ref": result_ref, "evidence_refs": [evidence_ref], "thread_id": claim.thread_id,
        "run_id": claim.run_id, "turn_id": claim.attempt.turn_id, "attempt_id": claim.attempt.attempt_id,
        "model_context_id": claim.model_context.id, "model_id": claim.model_context.model_id,
        "model_revision": REVISION,
        "source": {"capability_id": "analysis_powerflow_ac_run", "domain_pack_id": "pandapower-static-analysis", "implementation_family": "pandapower"},
        "status": "completed", "summary": [], "tables": [], "element_refs": [], "overlay": None,
    }
    return claim, projection


def _complete(
    service: InMemoryThreadService, claim: AttemptClaim, projection: dict[str, object],
    result_ref: str, evidence_ref: str,
) -> None:
    service.finish_attempt(
        claim, phase="completed", payload={
            "answer": "ready", "result_refs": [result_ref], "evidence_refs": [evidence_ref],
            "result_projections": [projection],
        },
    )


def test_result_projection_survives_public_snapshot_roundtrip_and_keeps_attempt_identity() -> None:
    service = _service()
    claim, projection = _claim_and_projection(service, 1, RESULT_ONE, EVIDENCE_ONE)
    _complete(service, claim, projection, RESULT_ONE, EVIDENCE_ONE)

    roundtrip = ThreadSnapshot.from_document(service.snapshot("thr_projection").to_document())

    assert roundtrip.result_projections[0].attempt_id == claim.attempt.attempt_id
    assert roundtrip.result_projections[0].result_ref == RESULT_ONE
    assert roundtrip.result_projections[0].model_revision == REVISION
    terminal = service.read_events("thr_projection", 0).events[-1]
    assert terminal.event_type == "attempt_completed"
    assert terminal.payload["result_projections"] == [projection]


def test_multiple_completed_attempts_keep_distinct_result_projection_ids() -> None:
    service = _service()
    first_claim, first = _claim_and_projection(service, 1, RESULT_ONE, EVIDENCE_ONE)
    _complete(service, first_claim, first, RESULT_ONE, EVIDENCE_ONE)
    second_claim, second = _claim_and_projection(service, 2, RESULT_TWO, EVIDENCE_TWO)
    _complete(service, second_claim, second, RESULT_TWO, EVIDENCE_TWO)

    projections = service.snapshot("thr_projection").result_projections
    assert [item.result_ref for item in projections] == [RESULT_ONE, RESULT_TWO]
    assert projections[0].attempt_id == first_claim.attempt.attempt_id
    assert projections[1].attempt_id == second_claim.attempt.attempt_id
    assert projections[0].result_id != projections[1].result_id


def test_snapshot_rejects_malformed_projection_instead_of_dropping_it() -> None:
    document = _service().snapshot("thr_projection").to_document()
    document["result_projections"] = [{"schema": "capstone-result-projection/1.0"}]
    with pytest.raises(ThreadProtocolError, match="result_projections"):
        ThreadSnapshot.from_document(document)


def test_result_projection_catalog_keeps_only_the_recent_bounded_window() -> None:
    service = _service()
    for ordinal in range(1, 66):
        result_ref = "result:sha256:" + f"{ordinal:064x}"[-64:]
        evidence_ref = "evidence:sha256:" + f"{ordinal:064x}"[-64:]
        claim, projection = _claim_and_projection(service, ordinal, result_ref, evidence_ref)
        _complete(service, claim, projection, result_ref, evidence_ref)

    projections = service.snapshot("thr_projection").result_projections
    assert len(projections) == 64
    assert projections[0].result_ref == "result:sha256:" + f"{2:064x}"
    assert projections[-1].result_ref == "result:sha256:" + f"{65:064x}"


def test_result_projection_with_element_refs_requires_domain_diagram_identity() -> None:
    service = _service()
    claim, projection = _claim_and_projection(service, 1, RESULT_ONE, EVIDENCE_ONE)
    projection["element_refs"] = [{"element_kind": "line", "element_id": "line:999"}]
    projection["_diagram_element_ids"] = ["line:11"]
    with pytest.raises(ValueError, match="unknown diagram element"):
        service.finish_attempt(
            claim, phase="completed", payload={
                "answer": "ready", "result_refs": [RESULT_ONE],
                "evidence_refs": [EVIDENCE_ONE], "result_projections": [projection],
            },
        )
