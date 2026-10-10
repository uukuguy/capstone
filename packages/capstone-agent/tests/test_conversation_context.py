from dataclasses import FrozenInstanceError

import pytest

from capstone_agent.conversation_context import ConversationContext, project_conversation, MAX_HISTORY_BYTES
from capstone_agent.thread_service import ThreadExecutionError
from test_thread_attempts import _model_service, _command, _ModelCatalog, _AnySelectionCatalog
from test_thread_postgres import postgres_thread_service, _snapshot, _command as postgres_command


def send(service, text, key, kind="send_ordinary", payload=None):
    command = {**_command("cmd_" + key), "kind": kind,
               "expected_event_seq": service.snapshot("thr_attempts").last_event_seq,
               "payload": {"text": text} if payload is None else payload}
    receipt = service.submit_command(command)
    assert receipt.status == "accepted", receipt.rejection
    return service.claim_attempt("worker", 30)


def test_shared_text_crosses_topic_and_model_switch_with_source_ids():
    service = _model_service()
    first = send(service, "analyse grid", "analysis")
    service.finish_attempt(first, phase="completed", payload={"answer": "grid answer"})
    weather = send(service, "weather please", "weather")
    assert [m["content"] for m in weather.conversation_context.to_document()["messages"]] == ["analyse grid", "grid answer"]
    service.finish_attempt(weather, phase="completed", payload={"answer": "weather answer"})
    send(service, "", "switch", "open_model", {"model_id": "pypsa39"})
    followup = send(service, "translate and compare both answers", "followup")
    history = followup.conversation_context.to_document()
    assert [m["content"] for m in history["messages"]] == ["analyse grid", "grid answer", "weather please", "weather answer"]
    assert history["messages"][0]["model_context_id"] == first.model_context_id
    assert history["messages"][0]["turn_id"] == first.attempt.turn_id
    assert history["messages"][0]["attempt_id"] == first.attempt.attempt_id
    assert history["messages"][0]["model_context_id"] != followup.model_context_id
    assert history["objects"] == [{"object_id": first.model_context_id,
        "model_id": "ieee39", "model_revision": first.model_context.model_revision,
        "implementation_family": "pandapower"}]
    history["objects"][0]["model_id"] = "mutated"
    assert followup.conversation_context.to_document()["objects"][0]["model_id"] == "ieee39"
    history["messages"][0]["content"] = "mutated"
    assert followup.conversation_context.to_document()["messages"][0]["content"] == "analyse grid"
    with pytest.raises(FrozenInstanceError):
        followup.conversation_context.history_cutoff = 0


def test_cancel_retry_uses_original_history_cutoff_and_excludes_partial_text():
    service = _model_service()
    first = send(service, "first", "first")
    service.finish_attempt(first, phase="completed", payload={"answer": "saved answer"})
    cancelled = send(service, "cancel me", "cancel")
    original = cancelled.conversation_context.to_document()
    service.append_runtime_event(cancelled, event_type="assistant_text_delta", payload={"text": "partial conclusion"})
    service.finish_attempt(cancelled, phase="cancelled", payload={"answer": "partial conclusion"})
    intervening = send(service, "another request", "other")
    assert [m["content"] for m in intervening.conversation_context.to_document()["messages"]] == ["first", "saved answer", "cancel me"]
    service.finish_attempt(intervening, phase="completed", payload={"answer": "later answer"})
    retry = send(service, "", "retry", "retry_new_attempt", {"attempt_id": cancelled.attempt.attempt_id})
    assert retry.conversation_context.to_document() == original
    assert retry.attempt.attempt_id != cancelled.attempt.attempt_id


def test_shared_history_is_bounded_and_marks_truncation():
    service = _model_service()
    for ordinal in range(18):
        claim = send(service, "request " + str(ordinal), str(ordinal))
        service.finish_attempt(claim, phase="completed", payload={"answer": "answer " + str(ordinal)})
    latest = send(service, "latest", "latest")
    document = latest.conversation_context.to_document()
    assert document["truncated"] is True
    assert len(document["messages"]) == 32
    assert document["messages"][0]["content"] == "request 2"


def test_frozen_attempt_input_retains_config_across_retry_and_returns_copies():
    service = _model_service()
    first = send(service, "first", "first")
    document = {"config_revision": "config_1", "request": {"instruction": "first"}}
    assert service.freeze_attempt_input(first, document) == document
    document["request"]["instruction"] = "changed"
    frozen = service.freeze_attempt_input(first, {"config_revision": "config_2"})
    assert frozen["config_revision"] == "config_1"
    assert frozen["request"]["instruction"] == "first"
    service.finish_attempt(first, phase="cancelled", payload={})
    retry = send(service, "", "retry", "retry_new_attempt", {"attempt_id": first.attempt.attempt_id})
    assert service.freeze_attempt_input(retry, {"config_revision": "config_3"}) == frozen
    with pytest.raises(ThreadExecutionError, match="lease"):
        service.freeze_attempt_input(first, {})


def test_unicode_history_keeps_eight_recent_turns_within_byte_budget():
    rows = [{"instruction": "电" * 10000, "answer": "网" * 10000,
             "turn_id": "turn_" + str(i), "attempt_id": "attempt_" + str(i),
             "model_context_id": "context", "status": "completed"} for i in range(16)]
    context = project_conversation(rows, 100)
    document = context.to_document()
    assert document["truncated"] is True
    assert len({m["turn_id"] for m in document["messages"]}) >= 8
    assert sum(len(m["content"].encode()) for m in document["messages"]) <= MAX_HISTORY_BYTES
    assert ConversationContext.from_document(document) == context


def test_restored_thread_has_no_other_thread_text():
    first = _model_service()
    claim = send(first, "private first Thread", "first")
    first.finish_attempt(claim, phase="completed", payload={"answer": "private answer"})
    restored = _model_service()
    fresh = send(restored, "fresh request", "fresh")
    assert fresh.conversation_context.to_document()["messages"] == []


def test_legacy_context_document_does_not_invent_model_metadata():
    context = ConversationContext.from_document({"history_cutoff": 0, "messages": [], "truncated": False})
    assert context.to_document()["objects"] == []


def test_postgres_projection_and_retry_keep_original_snapshot(postgres_thread_service):
    service, thread_id = postgres_thread_service
    service.create_thread(_snapshot(thread_id))

    def submit(text, key, kind="send_ordinary", payload=None):
        command = {**postgres_command(thread_id), "command_id": "cmd_" + key,
                   "idempotency_key": "idem_" + key, "kind": kind,
                   "expected_event_seq": service.snapshot(thread_id).last_event_seq,
                   "payload": {"text": text} if payload is None else payload}
        assert service.submit_command(command).status == "accepted"
        return service.claim_attempt("context_test", 30)

    first = submit("analyse grid", "analysis")
    service.finish_attempt(first, phase="completed", payload={"answer": "grid answer"})
    second = submit("translate that", "translation")
    original = second.conversation_context.to_document()
    assert [m["content"] for m in original["messages"]] == ["analyse grid", "grid answer"]
    frozen = service.freeze_attempt_input(second, {"engine_identity": {"config_revision": "1"}})
    service.append_runtime_event(second, event_type="assistant_text_delta", payload={"text": "partial"})
    service.finish_attempt(second, phase="cancelled", payload={"answer": "partial"})
    third = submit("weather please", "weather")
    assert [m["content"] for m in third.conversation_context.to_document()["messages"]] == ["analyse grid", "grid answer", "translate that"]
    service.finish_attempt(third, phase="completed", payload={"answer": "weather answer"})
    retry = submit("", "retry", "retry_new_attempt", {"attempt_id": second.attempt.attempt_id})
    assert retry.conversation_context.to_document() == original
    assert service.freeze_attempt_input(retry, {"engine_identity": {"config_revision": "2"}}) == frozen
    service.finish_attempt(retry, phase="completed", payload={"answer": "translated answer"})
    service.set_model_catalog(_ModelCatalog())
    service.set_capability_catalog(_AnySelectionCatalog())
    assert submit("", "switch", "open_model", {"model_id": "pypsa39"}) is None
    comparison = submit("compare with the earlier model", "comparison")
    objects = comparison.conversation_context.to_document()["objects"]
    assert objects == [{"object_id": first.model_context_id, "model_id": "ieee39",
                        "model_revision": first.model_context.model_revision,
                        "implementation_family": "pandapower"}]
    assert comparison.model_context.model_id == "pypsa39"
