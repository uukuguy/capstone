from types import SimpleNamespace

import pytest

from capstone_agent.kernel_capability_preparation import AuthorityModelBinding
from capstone_agent.kernel_pi_session import _build_kernel_admission
from capstone_agent.thread_protocol import AttemptSnapshot, ModelContextSnapshot
from capstone_agent.thread_service import AttemptClaim
from capability_agent.domain.answer_admission import AnswerAdmissionDecision

REVISION = "revision:sha256:" + "a" * 64
CONTEXT = "context:sha256:" + "b" * 64
EVIDENCE = "evidence:sha256:" + "c" * 64


def _admission(document, *, family="pandapower", context_ref=CONTEXT, linked_document=None, model_reference_verifier=None,
               context_identity_verifier=None,
               evidence_documents=None, result_documents=None, extra_bindings=None):
    policy = SimpleNamespace(admit=lambda request: AnswerAdmissionDecision(
        mode="authority_backed" if request.evidence_refs else "offline_information",
        assurance="lineage_verified" if request.evidence_refs else "deterministic_information",
        answer_output=request.answer_output,
        diagnostic_codes=(),
    ))
    calls = []

    def verify(reference):
        calls.append(reference)
        if isinstance(document, Exception):
            raise document
        return SimpleNamespace(document=evidence_documents[reference] if evidence_documents is not None else document)

    authority = SimpleNamespace(
        verify_evidence=verify,
        verify_result=lambda reference: SimpleNamespace(
            document=result_documents[reference] if result_documents is not None else linked_document),
        audit_answer_references=lambda *_: (),
    )
    runtime = SimpleNamespace(authority=authority, profile=SimpleNamespace(
        create_answer_admission_policy=lambda _: policy,
        answer_admission_capabilities=frozenset({"authority_backed", "offline_information"}),
    ))
    profile = SimpleNamespace(
        model_binding=AuthorityModelBinding("grid", "ieee39", REVISION, family, context_ref,
            model_reference_verifier=model_reference_verifier,
            context_identity_verifier=context_identity_verifier),
        prepared_application=SimpleNamespace(bindings={"grid": SimpleNamespace(
            runtime=runtime, binding=SimpleNamespace(tool_namespace="grid_")), **(extra_bindings or {})}),
    )
    context = ModelContextSnapshot("ctx_bound", "ieee39", REVISION, family, "sel_0")
    claim = AttemptClaim("thr_bound", "run_bound", AttemptSnapshot("turn_1", "attempt_1", "running", context.id),
                         "send_auto", "inspect", context.id, "sel_0", "lease_1", context)
    return _build_kernel_admission((profile,)), claim, calls


def _unused_binding():
    policy = SimpleNamespace(admit=lambda request: AnswerAdmissionDecision(
        "limited", "limited", request.answer_output, ("no_current_run_result",)))
    return SimpleNamespace(binding=SimpleNamespace(tool_namespace="unused_"), runtime=SimpleNamespace(
        authority=SimpleNamespace(), profile=SimpleNamespace(
            create_answer_admission_policy=lambda _: policy,
            answer_admission_capabilities=frozenset({"limited"}))))


def test_unused_selected_pack_does_not_downgrade_verified_model_observation():
    admit, claim, _ = _admission({"context_ref": CONTEXT, "revision_ref": REVISION},
        extra_bindings={"unused": _unused_binding()})
    event = {"binding_id": "grid", "ok": True, "evidence_refs": [EVIDENCE]}
    answer = admit(claim, "current model", (), (EVIDENCE,), (event,))
    assert answer.mode == "authority_backed"
    assert answer.evidence_refs == (EVIDENCE,)


def test_published_guide_without_authority_references_does_not_require_tool_provenance():
    admit, claim, _ = _admission({"context_ref": CONTEXT, "revision_ref": REVISION},
        extra_bindings={"unused": _unused_binding()})
    events = ({"binding_id": "grid", "ok": True, "evidence_refs": [EVIDENCE]},
        {"tool_name": "unused_guide_open", "ok": True})
    assert admit(claim, "current model", (), (EVIDENCE,), events).mode == "authority_backed"


@pytest.mark.parametrize("guide", [
    {"tool_name": "unknown_guide_open", "ok": True},
    {"tool_name": "unused_guide_open", "ok": True, "evidence_refs": [EVIDENCE]},
])
def test_unregistered_or_reference_bearing_guide_cannot_bypass_binding_ownership(guide):
    admit, claim, _ = _admission({"context_ref": CONTEXT, "revision_ref": REVISION},
        extra_bindings={"unused": _unused_binding()})
    with pytest.raises(ValueError, match="owner"):
        admit(claim, "answer", (), (EVIDENCE,), (guide,))


def test_participating_failed_pack_still_limits_admission():
    admit, claim, _ = _admission({"context_ref": CONTEXT, "revision_ref": REVISION},
        extra_bindings={"unused": _unused_binding()})
    events = ({"binding_id": "grid", "ok": True, "evidence_refs": [EVIDENCE]},
        {"binding_id": "unused", "ok": False, "capability": "operation"})
    answer = admit(claim, "UNVERIFIED ranking", (), (EVIDENCE,), events)
    assert answer.mode == 'authority_backed'
    assert answer.task_outcome['status'] == 'partial'
    assert 'UNVERIFIED ranking' not in answer.answer
    assert answer.evidence_refs == (EVIDENCE,)


@pytest.mark.parametrize("document", [
    {"context_ref": "context:sha256:" + "d" * 64, "revision_ref": REVISION},
    {"context_ref": CONTEXT, "revision_ref": "revision:sha256:" + "d" * 64},
    RuntimeError("corrupted evidence"),
])
def test_evidence_only_foreign_or_corrupted_artifacts_cannot_commit(document):
    admit, claim, _ = _admission(document)
    event = {"binding_id": "grid", "ok": True, "capability": "topology.branch.endpoints.get", "evidence_refs": [EVIDENCE]}
    with pytest.raises((ValueError, RuntimeError)):
        admit(claim, "answer", (), (EVIDENCE,), (event,))


def test_successful_foreign_model_observation_cannot_commit_without_result_refs():
    admit, claim, _ = _admission({})
    event = {"binding_id": "grid", "ok": True, "capability": "context.open",
             "model_id": "case24_ieee_rts", "context_ref": "context:sha256:" + "d" * 64}
    with pytest.raises(ValueError, match="bound"):
        admit(claim, "opened RTS", (), (), (event,))


def test_matching_evidence_only_artifact_is_verified_before_admission():
    admit, claim, calls = _admission({"context_ref": CONTEXT, "revision_ref": REVISION})
    event = {"binding_id": "grid", "ok": True, "capability": "topology.branch.endpoints.get", "evidence_refs": [EVIDENCE]}
    answer = admit(claim, "answer", (), (EVIDENCE,), (event,))
    assert answer.evidence_refs == (EVIDENCE,)
    assert calls == [EVIDENCE]


def test_bad_later_identity_retains_separately_admitted_earlier_evidence():
    admit, claim, _ = _admission({'context_ref': CONTEXT, 'revision_ref': REVISION})
    events = ({'binding_id': 'grid', 'ok': True, 'evidence_refs': [EVIDENCE]},
        {'binding_id': 'grid', 'ok': True, 'context_ref': 'context:sha256:' + 'd' * 64, 'revision_ref': REVISION})
    answer = admit(claim, 'UNVERIFIED ranking', (), (EVIDENCE,), events)
    assert answer.task_outcome['status'] == 'partial'
    assert answer.evidence_refs == (EVIDENCE,)
    assert 'UNVERIFIED' not in answer.answer


@pytest.mark.parametrize("document", [
    {"model_id": "ieee39"}, {"revision_ref": REVISION},
    {"context_ref": CONTEXT}, {"model_ref": CONTEXT},
    {"context_ref": CONTEXT, "revision_ref": REVISION,
     "model_revision": "revision:sha256:" + "d" * 64},
])
def test_incomplete_or_conflicting_context_artifact_identity_cannot_commit(document):
    admit, claim, _ = _admission(document)
    event = {"binding_id": "grid", "ok": True, "evidence_refs": [EVIDENCE]}
    with pytest.raises(ValueError, match="identity|bound"):
        admit(claim, "answer", (), (EVIDENCE,), (event,))


def test_pypsa_opaque_model_reference_is_valid_bound_identity():
    model_ref = "model:sha256:" + "b" * 64
    admit, claim, calls = _admission({"model_ref": model_ref}, family="pypsa", context_ref=model_ref)
    event = {"binding_id": "grid", "ok": True, "evidence_refs": [EVIDENCE]}
    answer = admit(claim, "answer", (), (EVIDENCE,), (event,))
    assert answer.evidence_refs == (EVIDENCE,)
    assert calls == [EVIDENCE]


@pytest.mark.parametrize("document", [
    {"model_id": "ieee39"}, {"revision_ref": REVISION},
    {"model_ref": "model:sha256:" + "d" * 64},
])
def test_pypsa_incomplete_or_foreign_model_identity_cannot_commit(document):
    model_ref = "model:sha256:" + "b" * 64
    admit, claim, _ = _admission(document, family="pypsa", context_ref=model_ref)
    event = {"binding_id": "grid", "ok": True, "evidence_refs": [EVIDENCE]}
    with pytest.raises(ValueError, match="identity|bound"):
        admit(claim, "answer", (), (EVIDENCE,), (event,))


@pytest.mark.parametrize("family,context_ref,linked_document", [
    ("pandapower", CONTEXT, {"context_ref": CONTEXT, "revision_ref": REVISION}),
    ("pypsa", "model:sha256:" + "b" * 64, {"model_ref": "model:sha256:" + "b" * 64}),
])
def test_evidence_can_prove_binding_through_verified_linked_result(family, context_ref, linked_document):
    admit, claim, _ = _admission(
        {"result_ref": "result:sha256:" + "d" * 64}, family=family,
        context_ref=context_ref, linked_document=linked_document,
    )
    event = {"binding_id": "grid", "ok": True, "evidence_refs": [EVIDENCE]}
    answer = admit(claim, "answer", (), (EVIDENCE,), (event,))
    assert answer.evidence_refs == (EVIDENCE,)


@pytest.mark.parametrize("linked_document", [
    {"model_id": "ieee39"},
    {"context_ref": "context:sha256:" + "d" * 64, "revision_ref": REVISION},
])
def test_evidence_link_cannot_hide_incomplete_or_foreign_result_identity(linked_document):
    admit, claim, _ = _admission(
        {"result_ref": "result:sha256:" + "d" * 64}, linked_document=linked_document,
    )
    event = {"binding_id": "grid", "ok": True, "evidence_refs": [EVIDENCE]}
    with pytest.raises(ValueError, match="identity|bound"):
        admit(claim, "answer", (), (EVIDENCE,), (event,))


def test_model_binding_accepts_exact_reference_without_calling_verifier():
    calls = []
    binding = AuthorityModelBinding(
        "source", "ieee39", REVISION, "pypsa", "model:sha256:" + "b" * 64,
        model_reference_verifier=lambda reference: calls.append(reference) or False,
    )
    assert binding.accepts_model_reference(binding.context_ref)
    assert calls == []


def test_model_binding_default_rejects_other_reference():
    binding = AuthorityModelBinding("source", "ieee39", REVISION, "pypsa", "model:sha256:" + "b" * 64)
    assert binding.accepts_model_reference(binding.context_ref)
    assert not binding.accepts_model_reference("model:sha256:" + "d" * 64)


def test_model_binding_requires_callable_reference_verifier():
    with pytest.raises(TypeError, match="verifier"):
        AuthorityModelBinding("source", "ieee39", REVISION, "pypsa", "model:sha256:" + "b" * 64,
                              model_reference_verifier="invalid")


def test_authorized_model_descendant_is_admitted_from_event_and_artifact():
    model_ref = "model:sha256:" + "b" * 64
    descendant = "model:sha256:" + "d" * 64
    calls = []

    def verifier(reference):
        calls.append(reference)
        return reference == descendant

    admit, claim, _ = _admission(
        {"model_ref": descendant}, family="pypsa", context_ref=model_ref,
        model_reference_verifier=verifier,
    )
    event = {"binding_id": "grid", "ok": True, "model_ref": descendant, "evidence_refs": [EVIDENCE]}
    answer = admit(claim, "answer", (), (EVIDENCE,), (event,))
    assert answer.evidence_refs == (EVIDENCE,)
    assert calls and set(calls) == {descendant}


@pytest.mark.parametrize("failure", ["false", "error", "truthy"])
@pytest.mark.parametrize("source", ["event", "artifact"])
def test_unverified_model_descendant_cannot_commit(failure, source):
    model_ref = "model:sha256:" + "b" * 64
    descendant = "model:sha256:" + "d" * 64

    def verifier(reference):
        if failure == "error":
            raise RuntimeError("unavailable authority")
        return "unverified" if failure == "truthy" else False

    document = {"model_ref": descendant if source == "artifact" else model_ref}
    admit, claim, _ = _admission(
        document, family="pypsa", context_ref=model_ref, model_reference_verifier=verifier,
    )
    event = {"binding_id": "grid", "ok": True, "evidence_refs": [EVIDENCE]}
    if source == "event":
        event["model_ref"] = descendant
    with pytest.raises(ValueError, match="bound"):
        admit(claim, "answer", (), (EVIDENCE,), (event,))


def test_model_reference_grant_does_not_relax_pandapower_context_or_revision():
    admit, claim, _ = _admission(
        {"context_ref": "context:sha256:" + "d" * 64, "revision_ref": REVISION},
        model_reference_verifier=lambda reference: True,
    )
    event = {"binding_id": "grid", "ok": True, "evidence_refs": [EVIDENCE]}
    with pytest.raises(ValueError, match="bound"):
        admit(claim, "answer", (), (EVIDENCE,), (event,))


def test_verified_child_context_and_revision_are_admitted_together():
    child = 'context:sha256:' + 'd' * 64
    revision = 'revision:sha256:' + 'e' * 64
    admit, claim, _ = _admission({'context_ref': child, 'revision_ref': revision},
        context_identity_verifier=lambda context, version: (context, version) == (child, revision))
    event = {'binding_id': 'grid', 'ok': True, 'capability': 'model.revision.derive',
             'context_ref': child, 'model_revision': revision, 'evidence_refs': [EVIDENCE]}
    assert admit(claim, 'verified scenario', (), (EVIDENCE,), (event,)).evidence_refs == (EVIDENCE,)


@pytest.mark.parametrize('source', ['event', 'artifact'])
def test_child_context_grant_cannot_accept_a_mismatched_revision(source):
    child = 'context:sha256:' + 'd' * 64
    revision = 'revision:sha256:' + 'e' * 64
    document = {'context_ref': CONTEXT, 'revision_ref': REVISION}
    event = {'binding_id': 'grid', 'ok': True, 'evidence_refs': [EVIDENCE]}
    if source == 'event':
        event.update(context_ref=child, model_revision=REVISION)
    else:
        document.update(context_ref=child)
    admit, claim, _ = _admission(document,
        context_identity_verifier=lambda context, version: (context, version) == (child, revision))
    with pytest.raises(ValueError, match='bound'):
        admit(claim, 'invalid scenario', (), (EVIDENCE,), (event,))


@pytest.mark.parametrize("repeated_evidence", [[], [EVIDENCE], ["evidence:sha256:" + "d" * 64]])
def test_repeated_result_views_keep_all_current_admitted_evidence(repeated_evidence):
    result_ref = "result:sha256:" + "e" * 64
    document = {"context_ref": CONTEXT, "revision_ref": REVISION, "result_ref": result_ref}
    admit, claim, _ = _admission(document, linked_document=document)
    events = (
        {"binding_id": "grid", "ok": True, "capability": "analysis.powerflow.ac.run",
         "result_refs": [result_ref], "evidence_refs": [EVIDENCE]},
        {"binding_id": "grid", "ok": True, "capability": "result.branches.rank",
         "result_refs": [result_ref], "evidence_refs": repeated_evidence},
        {"binding_id": "grid", "ok": True, "capability": "result.dataset.query",
         "result_refs": [result_ref], "evidence_refs": []},
    )
    admitted_evidence = tuple(dict.fromkeys([EVIDENCE, *repeated_evidence]))
    answer = admit(claim, "answer", (result_ref,), admitted_evidence, events)
    assert len(answer.result_projections) == 1
    assert answer.result_projections[0]["evidence_refs"] == list(admitted_evidence)


def test_result_projection_does_not_merge_evidence_outside_attempt_admission():
    result_ref = "result:sha256:" + "e" * 64
    document = {"context_ref": CONTEXT, "revision_ref": REVISION, "result_ref": result_ref}
    admit, claim, _ = _admission(document, linked_document=document)
    events = (
        {"binding_id": "grid", "ok": True, "result_refs": [result_ref], "evidence_refs": [EVIDENCE]},
        {"binding_id": "grid", "ok": True, "result_refs": [result_ref],
         "evidence_refs": ["evidence:sha256:" + "f" * 64]},
    )
    answer = admit(claim, "answer", (result_ref,), (EVIDENCE,), events)
    assert answer.result_projections[0]["evidence_refs"] == [EVIDENCE]


def test_later_evidence_get_binds_to_its_verified_result_instead_of_latest_result():
    first_result = "result:sha256:" + "1" * 64
    second_result = "result:sha256:" + "2" * 64
    second_evidence = "evidence:sha256:" + "d" * 64
    identity = {"context_ref": CONTEXT, "revision_ref": REVISION}
    admit, claim, _ = _admission({}, linked_document=identity, evidence_documents={
        EVIDENCE: {**identity, "result_ref": first_result},
        second_evidence: {**identity, "result_ref": second_result},
    })
    events = (
        {"binding_id": "grid", "ok": True, "result_refs": [first_result], "evidence_refs": [EVIDENCE]},
        {"binding_id": "grid", "ok": True, "result_refs": [second_result], "evidence_refs": [second_evidence]},
        {"binding_id": "grid", "ok": True, "capability": "evidence.get", "evidence_refs": [EVIDENCE]},
    )
    answer = admit(claim, "answer", (first_result, second_result), (EVIDENCE, second_evidence), events)
    associations = {item["result_ref"]: item["evidence_refs"] for item in answer.result_projections}
    assert associations == {first_result: [EVIDENCE], second_result: [second_evidence]}


def test_projection_mapping_still_rejects_result_with_conflicting_binding_owners():
    from capstone_agent.kernel_pi_session import _build_result_projections

    result_ref = "result:sha256:" + "e" * 64
    _, claim, _ = _admission({})
    events = (
        {"binding_id": "first", "result_refs": [result_ref], "evidence_refs": [EVIDENCE]},
        {"binding_id": "second", "result_refs": [result_ref], "evidence_refs": []},
    )
    with pytest.raises(ValueError, match="conflicting binding owners"):
        _build_result_projections(claim, (), {"first": object(), "second": object()},
                                  (result_ref,), (EVIDENCE,), events)


@pytest.mark.parametrize("scenario_link", [True, False])
def test_aggregate_projection_uses_verified_root_evidence_membership(scenario_link):
    root = "result:sha256:" + "1" * 64
    other_root = "result:sha256:" + "2" * 64
    child = "result:sha256:" + "3" * 64
    identity = {"context_ref": CONTEXT, "revision_ref": REVISION}
    aggregate = {**identity, "evidence_refs": [EVIDENCE],
                 "scenarios": [{"scenario_result_ref": child, "evidence_ref": EVIDENCE}]}
    evidence = {**identity, **({"result_ref": child} if scenario_link else {})}
    admit, claim, _ = _admission(evidence, result_documents={
        root: aggregate, other_root: aggregate, child: identity,
    })
    events = ({"binding_id": "grid", "ok": True,
               "result_refs": [root, other_root], "evidence_refs": [EVIDENCE]},)
    answer = admit(claim, "answer", (root, other_root), (EVIDENCE,), events)
    assert {item["result_ref"]: item["evidence_refs"] for item in answer.result_projections} == {
        root: [EVIDENCE], other_root: [EVIDENCE],
    }


@pytest.mark.parametrize("linked_result", ["result:sha256:" + "2" * 64, None])
def test_unselected_result_evidence_or_context_fact_is_not_assigned_to_selected_result(linked_result):
    selected = "result:sha256:" + "1" * 64
    identity = {"context_ref": CONTEXT, "revision_ref": REVISION}
    evidence = {**identity, "result_ref": linked_result}
    admit, claim, _ = _admission(evidence, linked_document=identity)
    events = ({"binding_id": "grid", "ok": True, "result_refs": [selected], "evidence_refs": [EVIDENCE]},)
    answer = admit(claim, "answer", (selected,), (EVIDENCE,), events)
    assert answer.result_projections[0]["evidence_refs"] == []


def test_scenario_result_identity_uses_application_model_reference_grant():
    base = "model:sha256:" + "b" * 64
    descendant = "model:sha256:" + "d" * 64
    root = "result:sha256:" + "1" * 64
    child = "result:sha256:" + "2" * 64
    calls = []
    admit, claim, _ = _admission(
        {"result_ref": child}, family="pypsa", context_ref=base,
        model_reference_verifier=lambda reference: calls.append(reference) or reference == descendant,
        result_documents={root: {"model_ref": base, "evidence_refs": [EVIDENCE]},
                          child: {"model_ref": descendant}},
    )
    events = ({"binding_id": "grid", "ok": True, "result_refs": [root], "evidence_refs": [EVIDENCE]},)
    answer = admit(claim, "answer", (root,), (EVIDENCE,), events)
    assert answer.result_projections[0]["evidence_refs"] == [EVIDENCE]
    assert descendant in calls
