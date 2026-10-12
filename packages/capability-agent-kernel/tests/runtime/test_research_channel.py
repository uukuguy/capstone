from __future__ import annotations

import importlib
import json
from hashlib import sha256
from pathlib import Path

import pytest

from capability_agent.application import ApplicationContextStore, ContextEventDraft, ResearchController
from capability_agent.application.workspace import ApplicationWorkspace


@pytest.fixture
def channel(tmp_path):
    module = importlib.util.find_spec("capability_agent.runtime.research_channel")
    assert module is not None, "research request channel is not implemented"
    Channel = importlib.import_module(module.name).ResearchRequestChannel
    workspace = ApplicationWorkspace.create(tmp_path / "runs", run_id="run-1", binding_ids=())
    store = ApplicationContextStore.initialize(workspace)
    store.append(ContextEventDraft(event_type="turn.started", turn_id="turn-1", payload={"ordinal": 1}))
    controller = ResearchController(store, research_id="research-1", turn_id="turn-1", admit_reference=lambda _: False)
    active = [True]
    return Channel(controller, attempt_id="attempt-1", is_active=lambda: active[0]), active


def publish(channel, request_id="update-1", revision=0, goal="Study this model"):
    path = channel.requests_path / f"{request_id}.json"
    path.write_text(json.dumps({"request_id": request_id, "expected_revision": revision, "changes": {"goal": goal}}))
    return path


def receipt(channel, request_id="update-1"):
    return json.loads((channel.receipts_path / f"{request_id}.json").read_text())


def test_missing_initial_goal_is_rejected_and_can_be_repaired_without_uncertain_commit(channel):
    pump, _ = channel
    path = pump.requests_path / "missing-goal.json"
    path.write_text(json.dumps({"request_id": "missing-goal", "expected_revision": 0,
        "changes": {"notes": [{"note_id": "note-one", "text": "Observed failure"}]}}))
    pump.drain()
    ack = receipt(pump, "missing-goal")
    assert ack["status"] == "rejected"
    assert ack["code"] == "research_goal_required"
    assert pump.controller.read() is None
    publish(pump, request_id="repaired-goal")
    pump.drain()
    assert receipt(pump, "repaired-goal")["status"] == "committed"
    assert receipt(pump, "missing-goal")["status"] == "rejected"


def test_channel_publishes_view_before_success_receipt(channel):
    pump, _ = channel
    publish(pump)
    assert pump.drain() == 1
    ack = receipt(pump)
    view = json.loads(pump.view_path.read_text())
    assert ack["status"] == "committed"
    assert ack["receipt"]["research_revision"] == 1
    assert view["research_revision"] == 1
    assert view["state"]["goal"] == "Study this model"
    assert view["attempt_id"] == "attempt-1"


def test_channel_publishes_host_bound_tool_contract_without_caller_identity(channel):
    pump, _ = channel
    binding = json.loads((pump.root / "binding.json").read_text())
    assert binding["schema_version"] == "capability-research-channel/1.0"
    assert binding["attempt_id"] == "attempt-1"
    schema = binding["update_tool_schema"]
    assert set(schema["properties"]) == {"expected_revision", "changes"}
    assert schema["additionalProperties"] is False
    assert "ResearchChanges" in schema["$defs"]
    assert binding["read_tool_schema"]["properties"]["limit"]["maximum"] == 8


def test_lost_receipt_is_regenerated_without_second_update(channel):
    pump, _ = channel
    publish(pump)
    pump.drain()
    original = receipt(pump)
    (pump.receipts_path / "update-1.json").unlink()
    assert pump.drain() == 1
    assert receipt(pump) == original
    assert pump.controller.read().revision == 1


def test_uncertain_receipt_can_be_resolved_after_attempt_closes(channel):
    pump, active = channel
    path = publish(pump)
    committed = pump.controller.update(json.loads(path.read_text()))
    (pump.receipts_path / "update-1.json").write_text(json.dumps({
        "request_id": "update-1", "request_sha256": sha256(path.read_bytes()).hexdigest(),
        "status": "not_confirmed", "code": "research_update_not_confirmed",
    }))
    active[0] = False
    assert pump.drain() == 1
    assert receipt(pump)["status"] == "committed"
    assert receipt(pump)["receipt"]["event_sequence"] == committed.event_sequence
    assert pump.controller.read().revision == 1


def test_closed_attempt_cannot_commit_pending_update(channel):
    pump, active = channel
    publish(pump)
    active[0] = False
    pump.drain()
    assert receipt(pump)["status"] == "rejected"
    assert receipt(pump)["code"] == "attempt_closed"
    assert pump.controller.read() is None


def test_channel_rejects_caller_selected_identity_and_path(channel):
    pump, _ = channel
    path = publish(pump)
    request = json.loads(path.read_text())
    request["research_id"] = "another-research"
    path.write_text(json.dumps(request))
    pump.drain()
    assert receipt(pump)["status"] == "rejected"
    assert pump.controller.read() is None


def test_invalid_update_returns_bounded_field_errors_without_echoing_input(channel):
    pump, _ = channel
    path = publish(pump)
    request = json.loads(path.read_text())
    request["changes"]["claims"] = [{"claim_id": "claim-1", "statement": "private-marker",
                                    "status": "supported", "refs": []}]
    path.write_text(json.dumps(request))
    pump.drain()
    ack = receipt(pump)
    assert ack["code"] == "invalid_research_update"
    assert ack["validation_errors"]
    assert ack["validation_errors"][0]["path"] == ["changes", "claims", 0]
    assert "private-marker" not in json.dumps(ack)
    assert pump.controller.read() is None
    corrected = json.loads(path.read_text())
    corrected["request_id"] = "update-2"
    corrected["changes"]["claims"][0]["status"] = "pending"
    (pump.requests_path / "update-2.json").write_text(json.dumps(corrected))
    pump.drain()
    assert receipt(pump, "update-2")["status"] == "committed"


def test_receipt_write_failure_does_not_undo_committed_research(channel, monkeypatch):
    pump, _ = channel
    module = importlib.import_module("capability_agent.runtime.research_channel")
    real_write = module.write_bound_text
    def fail_receipt(path, text):
        if Path(path).parent == pump.receipts_path:
            raise OSError("injected receipt failure")
        return real_write(path, text)
    publish(pump)
    with monkeypatch.context() as patch:
        patch.setattr(module, "write_bound_text", fail_receipt)
        with pytest.raises(OSError, match="receipt failure"):
            pump.drain()
    assert pump.controller.read().revision == 1
    assert pump.drain() == 1
    assert receipt(pump)["status"] == "committed"
    assert pump.controller.read().revision == 1


def test_changed_request_cannot_reuse_an_existing_receipt(channel):
    pump, _ = channel
    publish(pump)
    pump.drain()
    publish(pump, goal="Changed payload")
    with pytest.raises(RuntimeError, match="request changed"):
        pump.drain()
    assert pump.controller.read().goal == "Study this model"


def test_symlink_request_is_not_followed(channel, tmp_path):
    pump, _ = channel
    outside = tmp_path / "outside.json"
    outside.write_text("{}")
    (pump.requests_path / "update-1.json").symlink_to(outside)
    with pytest.raises(OSError):
        pump.drain()
    assert pump.controller.read() is None


def test_drain_batch_is_bounded(channel):
    pump, _ = channel
    for number in range(3):
        publish(pump, request_id=f"update-{number}", revision=number, goal=f"Goal {number}")
    assert pump.drain(max_requests=1) == 1
    assert pump.controller.read().revision == 1
    assert pump.drain(max_requests=1) == 1
    assert pump.controller.read().revision == 2


def test_conflict_receipt_reports_current_revision_without_claiming_uncertain_commit(channel):
    pump, _ = channel
    publish(pump)
    pump.drain()
    publish(pump, request_id="update-2", revision=0, goal="Conflicting update")
    pump.drain()
    ack = receipt(pump, "update-2")
    assert ack["status"] == "rejected"
    assert ack["code"] == "research_revision_conflict"
    assert ack["research_revision"] == 1
    assert pump.controller.read().revision == 1


def test_unadmitted_reference_receipt_is_a_rejection(channel):
    pump, _ = channel
    path = publish(pump)
    request = json.loads(path.read_text())
    request["changes"]["condition_refs"] = ["result:sha256:" + "a" * 64]
    path.write_text(json.dumps(request))
    pump.drain()
    assert receipt(pump)["status"] == "rejected"
    assert receipt(pump)["code"] == "research_reference_not_admitted"
    assert pump.controller.read() is None
