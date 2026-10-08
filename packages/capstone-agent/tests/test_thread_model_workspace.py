from __future__ import annotations

from dataclasses import replace

import pytest

from capstone_agent.thread_service import InMemoryThreadService, ThreadModelDescriptor
from test_thread_attempts import _model_service, _command
from test_thread_postgres import postgres_thread_service, _snapshot


def command(service, kind, payload, key="model"):
    snapshot = service.snapshot("thr_attempts")
    return {**_command("cmd_" + key), "kind": kind, "payload": payload,
            "expected_event_seq": snapshot.last_event_seq}


def test_workspace_is_separate_from_legacy_snapshot_and_starts_with_current_model():
    service = _model_service()
    assert hasattr(service, "read_models"), "persistent opened-model projection is missing"
    models = service.read_models("thr_attempts")
    assert models["schema"] == "capstone-thread-model-workspace/1"
    assert len(models["models"]) == 1
    assert models["current_entry_id"] == models["models"][0]["entry_id"]
    assert models["models"][0]["model_id"] == "ieee39"
    assert "model_workspace" not in service.snapshot("thr_attempts").to_document()


def test_open_and_activate_finish_without_an_attempt_and_keep_exact_revision():
    service = _model_service()
    receipt = service.submit_command(command(service, "open_model", {"model_id": "pypsa39"}))
    assert receipt.status == "accepted", receipt.rejection
    snapshot = service.snapshot("thr_attempts")
    assert snapshot.active_model_context.model_id == "pypsa39"
    assert snapshot.pending_model_switch is None and snapshot.current_attempt is None
    assert service.claim_attempt("worker", lease_seconds=30) is None
    models = service.read_models("thr_attempts")
    ieee39 = models["models"][0]
    old_context = snapshot.active_model_context.id
    service.submit_command(command(service, "activate_model", {"entry_id": ieee39["entry_id"]}, "activate"))
    current = service.snapshot("thr_attempts").active_model_context
    assert current.model_id == "ieee39" and current.model_revision == ieee39["model_revision"]
    assert current.id != old_context
    assert [item["model_id"] for item in service.read_models("thr_attempts")["models"]] == ["ieee39", "pypsa39"]


def test_current_close_selects_recent_other_and_last_model_is_protected():
    service = _model_service()
    receipt = service.submit_command(command(service, "open_model", {"model_id": "pypsa39"}))
    assert receipt.status == "accepted", receipt.rejection
    workspace = service.read_models("thr_attempts")
    close = command(service, "close_model", {"entry_id": workspace["current_entry_id"]}, "close")
    receipt = service.submit_command(close)
    assert receipt.status == "accepted"
    assert service.submit_command(close) == receipt
    assert service.snapshot("thr_attempts").active_model_context.model_id == "ieee39"
    workspace = service.read_models("thr_attempts")
    assert len(workspace["models"]) == 1
    rejected = service.submit_command(command(service, "close_model", {"entry_id": workspace["current_entry_id"]}, "last"))
    assert rejected.rejection == "last_model_required"
    assert service.read_models("thr_attempts") == workspace


def test_select_current_is_noop_and_unknown_entry_is_rejected():
    service = _model_service()
    assert hasattr(service, "read_models"), "persistent opened-model projection is missing"
    before = service.snapshot("thr_attempts")
    workspace = service.read_models("thr_attempts")
    receipt = service.submit_command(command(service, "activate_model", {"entry_id": workspace["current_entry_id"]}))
    assert receipt.status == "accepted"
    assert service.snapshot("thr_attempts") == before
    rejected = service.submit_command(command(service, "activate_model", {"entry_id": "mdl_missing"}, "missing"))
    assert rejected.rejection == "model_not_open"


def test_live_attempt_and_pending_legacy_switch_block_workspace_changes():
    service = _model_service()
    service.submit_command(_command())
    receipt = service.submit_command(command(service, "open_model", {"model_id": "pypsa39"}, "busy"))
    assert receipt.rejection == "attempt_in_progress"
    service = _model_service()
    service.submit_command(command(service, "switch_model", {"model_id": "pypsa39"}))
    receipt = service.submit_command(command(service, "open_model", {"model_id": "pypsa39"}, "pending"))
    assert receipt.rejection == "context_change_pending"


def test_legacy_activation_updates_workspace_without_changing_delayed_contract():
    service = _model_service()
    service.submit_command(command(service, "switch_model", {"model_id": "pypsa39"}))
    assert service.snapshot("thr_attempts").active_model_context.model_id == "ieee39"
    service.submit_command(command(service, "send_ordinary", {"text": "inspect"}, "turn"))
    assert hasattr(service, "read_models"), "persistent opened-model projection is missing"
    workspace = service.read_models("thr_attempts")
    assert len(workspace["models"]) == 2
    assert next(item for item in workspace["models"] if item["entry_id"] == workspace["current_entry_id"])["model_id"] == "pypsa39"


class DiagramCatalog:
    def resolve(self, model_id):
        if model_id not in {"ieee39", "case57"}:
            raise LookupError(model_id)
        return ThreadModelDescriptor(model_id, "7", "pandapower", display_name=model_id)

    def diagram(self, model_id, revision):
        return {"schema": "capstone-network-diagram/1.0",
                "model": {"id": model_id, "revision": revision, "source": "gridctl"},
                "coordinate_system": "schematic", "buses": [{"id": "bus:1", "label": "Bus 1", "x": 0, "y": 0, "vn_kv": 110}],
                "branches": []}


def test_failed_diagram_preparation_leaves_workspace_context_and_cursor_unchanged():
    class Broken(DiagramCatalog):
        def diagram(self, model_id, revision):
            return super().diagram("ieee39", revision)
    service = _model_service()
    service.set_model_catalog(Broken())
    before = service.snapshot("thr_attempts")
    receipt = service.submit_command(command(service, "open_model", {"model_id": "case57"}))
    assert receipt.rejection == "model_preparation_failed"
    assert service.snapshot("thr_attempts") == before


def test_historical_reopen_rejects_catalog_drift_without_substituting_a_new_revision():
    service = _model_service()
    service.set_model_catalog(DiagramCatalog())
    before = service.snapshot("thr_attempts")
    receipt = service.submit_command(command(service, "open_model", {"model_id": "case57", "model_revision": "old"}))
    assert receipt.rejection == "model_revision_unavailable"
    assert service.snapshot("thr_attempts") == before


def test_inactive_close_retains_current_context_and_records_one_durable_outcome():
    service = _model_service()
    service.submit_command(command(service, "open_model", {"model_id": "pypsa39"}))
    workspace = service.read_models("thr_attempts")
    before = service.snapshot("thr_attempts")
    receipt = service.submit_command(command(service, "close_model", {"entry_id": workspace["models"][0]["entry_id"]}, "inactive"))
    assert receipt.status == "accepted"
    after = service.snapshot("thr_attempts")
    assert after.active_model_context == before.active_model_context
    assert after.last_event_seq == before.last_event_seq + 1
    event = service.read_events("thr_attempts", before.last_event_seq).events[0]
    assert event.event_type == "model_workspace_changed"
    assert event.payload["closed_model_name"] == "ieee39"


def test_model_controls_reject_stale_cursor_without_changing_membership():
    service = _model_service()
    request = command(service, "open_model", {"model_id": "pypsa39"})
    request["expected_event_seq"] = 1
    before = service.read_models("thr_attempts")
    assert service.submit_command(request).rejection == "stale_event_seq"
    assert service.read_models("thr_attempts") == before


@pytest.mark.parametrize("kind", ["open_model", "switch_model"])
def test_opened_model_limit_rejects_immediate_and_legacy_controls_before_activation(kind):
    from capstone_agent.thread_model_workspace import model_entry
    service = _model_service()
    context = service.snapshot("thr_attempts").active_model_context
    workspace = service._model_workspace
    workspace["models"].extend(model_entry(replace(context, model_id=f"test{i}"), 0) for i in range(63))
    before = service.snapshot("thr_attempts")
    receipt = service.submit_command(command(service, kind, {"model_id": "pypsa39"}))
    assert receipt.rejection == "opened_model_limit"
    assert service.snapshot("thr_attempts") == before


def test_close_retains_exact_historical_topology_after_event_window_truncation():
    service = _model_service()
    service.set_model_catalog(DiagramCatalog())
    receipt = service.submit_command(command(service, "open_model", {"model_id": "case57"}))
    assert receipt.status == "accepted", receipt.rejection
    context = service.snapshot("thr_attempts").active_model_context
    workspace = service.read_models("thr_attempts")
    service.submit_command(command(service, "close_model", {"entry_id": workspace["current_entry_id"]}, "close"))
    current = service.snapshot("thr_attempts")
    # Trimming a live event window must not erase historical source events.
    service._snapshot = replace(current, base_event_seq=current.last_event_seq)
    history = service.read_network_events("thr_attempts", context_id=context.id)
    assert history["model_context"]["id"] == context.id
    assert history["events"][0]["payload"]["diagram"]["model"] == {"id": "case57", "revision": "7", "source": "gridctl"}
    assert service.snapshot("thr_attempts").active_model_context.id == current.active_model_context.id


def postgres_command(service, thread_id, kind, payload, key):
    snapshot = service.snapshot(thread_id)
    return {"schema": "capstone-command/1", "command_id": "cmd_" + key, "idempotency_key": "idem_" + key,
            "thread_id": thread_id, "run_id": snapshot.run.run_id, "kind": kind,
            "expected_event_seq": snapshot.last_event_seq, "payload": payload}


@pytest.mark.parametrize("read_before_control", [False, True])
def test_postgres_legacy_models_are_restored_once_without_reviving_closed_models(postgres_thread_service, read_before_control):
    from psycopg.types.json import Jsonb
    from capstone_agent.thread_model_workspace import synchronize_workspace
    service, thread_id = postgres_thread_service
    service.set_model_catalog(DiagramCatalog())
    initial = _snapshot(thread_id)
    service.create_thread(initial)
    middle = replace(initial.active_model_context, id="ctx_middle", model_id="GBnetwork", model_revision="old-gb")
    current = replace(initial.active_model_context, id="ctx_current", model_id="case57")
    with service._connect() as connection:
        for seq, previous, active in [(2, initial.active_model_context, middle), (3, middle, current)]:
            event = service._make_control_event({"thread_id": thread_id, "run_id": initial.run.run_id}, active,
                event_seq=seq, event_type="model_context_activated",
                payload={"previous_context": previous.to_document(), "model_context": active.to_document()})
            service._insert_event(connection, event)
        snapshot = replace(initial, active_model_context=current, last_event_seq=3, base_event_seq=3)
        # Reproduce the previous migration, which already persisted only the current model.
        connection.execute("""UPDATE capstone_threads SET model_context_id = %s, model_id = %s,
            last_event_seq = 3, base_event_seq = 3, model_workspace = %s WHERE thread_id = %s""",
            (current.id, current.model_id, Jsonb(synchronize_workspace(None, snapshot, DiagramCatalog())), thread_id))
    if read_before_control:
        before_read = service.snapshot(thread_id)
        workspace = service.read_models(thread_id)
        assert {item["model_id"] for item in workspace["models"]} == {"ieee39", "GBnetwork", "case57"}
        assert next(item for item in workspace["models"] if item["model_id"] == "GBnetwork")["model_revision"] == "old-gb"
        assert service.snapshot(thread_id) == before_read
    # The first command also migrates, without requiring a preceding GET /models.
    entry = synchronize_workspace(None, initial)["current_entry_id"]
    receipt = service.submit_command(postgres_command(service, thread_id, "activate_model", {"entry_id": entry}, "activate_legacy"))
    assert receipt.status == "accepted", receipt.rejection
    workspace = service.read_models(thread_id)
    assert len(workspace["models"]) == 3
    assert service.snapshot(thread_id).active_model_context.model_id == "ieee39"
    gb = next(item for item in workspace["models"] if item["model_id"] == "GBnetwork")
    assert service.submit_command(postgres_command(service, thread_id, "close_model", {"entry_id": gb["entry_id"]}, "close_legacy")).status == "accepted"
    service.compact_before(thread_id, service.snapshot(thread_id).last_event_seq)
    from capstone_agent.thread_service import PostgresThreadService
    reloaded = PostgresThreadService(service.dsn, model_catalog=DiagramCatalog())
    assert {item["model_id"] for item in reloaded.read_models(thread_id)["models"]} == {"ieee39", "case57"}
    # A workspace managed by the preceding release has no migration marker yet.
    with service._connect() as connection:
        connection.execute("UPDATE capstone_threads SET model_workspace_migrated = false WHERE thread_id = %s", (thread_id,))
    assert {item["model_id"] for item in reloaded.read_models(thread_id)["models"]} == {"ieee39", "case57"}
    assert reloaded.read_network_events(thread_id, context_id=middle.id)["model_context"]["model_revision"] == "old-gb"


def test_legacy_workspace_import_keeps_distinct_versions_and_bounds_recent_models():
    from capstone_agent.thread_model_workspace import MAX_OPEN_MODELS, migrate_workspace
    snapshot = _snapshot("thr_migration")
    context = snapshot.active_model_context
    documents = [(seq, replace(context, model_id=f"grid{seq}").to_document()) for seq in range(70)]
    documents += [(80, replace(context, model_revision="older").to_document())]
    workspace = migrate_workspace(None, snapshot, documents, set())
    assert len(workspace["models"]) == MAX_OPEN_MODELS
    assert {(item["model_id"], item["model_revision"]) for item in workspace["models"] if item["model_id"] == "ieee39"} == {("ieee39", "7"), ("ieee39", "older")}
    assert "grid69" in {item["model_id"] for item in workspace["models"]}
    assert "grid0" not in {item["model_id"] for item in workspace["models"]}
    assert next(item for item in workspace["models"] if item["entry_id"] == workspace["current_entry_id"])["model_revision"] == "7"


def test_postgres_workspace_persists_close_and_historical_topology(postgres_thread_service):
    from capstone_agent.thread_service import PostgresThreadService
    service, thread_id = postgres_thread_service
    service.set_model_catalog(DiagramCatalog())
    service.create_thread(_snapshot(thread_id))
    initial = service.read_models(thread_id)
    receipt = service.submit_command(postgres_command(service, thread_id, "open_model", {"model_id": "case57"}, "open"))
    assert receipt.status == "accepted"
    context = service.snapshot(thread_id).active_model_context
    reopened_service = PostgresThreadService(service.dsn, model_catalog=DiagramCatalog())
    workspace = reopened_service.read_models(thread_id)
    assert len(workspace["models"]) == 2
    close = postgres_command(reopened_service, thread_id, "close_model", {"entry_id": workspace["current_entry_id"]}, "close")
    receipt = reopened_service.submit_command(close)
    assert receipt.status == "accepted" and reopened_service.submit_command(close) == receipt
    assert reopened_service.read_models(thread_id)["current_entry_id"] == initial["current_entry_id"]
    reopened_service.compact_before(thread_id, reopened_service.snapshot(thread_id).last_event_seq)
    history = reopened_service.read_network_events(thread_id, context_id=context.id)
    assert history["model_context"]["id"] == context.id
    assert history["events"][0]["payload"]["diagram"]["model"]["id"] == "case57"


def test_postgres_concurrent_identical_model_controls_have_one_commit(postgres_thread_service):
    from concurrent.futures import ThreadPoolExecutor
    service, thread_id = postgres_thread_service
    service.set_model_catalog(DiagramCatalog())
    service.create_thread(_snapshot(thread_id))
    initial_seq = service.snapshot(thread_id).last_event_seq
    request = postgres_command(service, thread_id, "open_model", {"model_id": "case57"}, "concurrent")
    with ThreadPoolExecutor(max_workers=2) as executor:
        receipts = list(executor.map(service.submit_command, [request, request]))
    assert receipts[0] == receipts[1]
    assert receipts[0].status == "accepted"
    assert len(service.read_models(thread_id)["models"]) == 2
    assert service.snapshot(thread_id).last_event_seq == initial_seq + 3


def test_postgres_creation_retains_baseline_topology_without_a_turn(postgres_thread_service):
    service, thread_id = postgres_thread_service
    service.set_model_catalog(DiagramCatalog())
    service.create_thread(_snapshot(thread_id))
    page = service.read_network_events(thread_id)
    assert len(page["events"]) == 1
    assert page["events"][0]["event_type"] == "network_diagram"
    assert page["events"][0].get("attempt_id") is None
    assert service.claim_attempt("worker", lease_seconds=30) is None


def test_postgres_closed_model_replays_exact_attempt_layer_after_compaction(postgres_thread_service):
    from capstone_agent.network_diagram import normalize_network_diagram
    service, thread_id = postgres_thread_service
    catalog = DiagramCatalog()
    service.set_model_catalog(catalog)
    service.create_thread(_snapshot(thread_id))
    service.submit_command(postgres_command(service, thread_id, "open_model", {"model_id": "case57"}, "case"))
    original_context = service.snapshot(thread_id).active_model_context
    attempts = []
    for index, focus in enumerate((["bus:1"], [])):
        receipt = service.submit_command(postgres_command(service, thread_id, "send_ordinary", {"text": "inspect"}, f"inspect{index}"))
        assert receipt.status == "accepted"
        claim = service.claim_attempt("history-worker", lease_seconds=30)
        assert claim is not None
        diagram = normalize_network_diagram(catalog.diagram("case57", "7"))
        service.append_runtime_event(claim, event_type="network_diagram", payload={"diagram": diagram})
        service.append_runtime_event(claim, event_type="network_layer", payload={"ordinal": 1,
            "layer": {"schema": "capstone-network-layer/1.0", "ordinal": 1, "diagram_ref": diagram["ref"],
                      "model_revision": "7", "focus_ids": focus, "next_focus_ids": [], "overlay": None}})
        service.finish_attempt(claim, phase="completed", payload={"answer": "fixture answer", "result_refs": []})
        attempts.append(claim.attempt.attempt_id)
    workspace = service.read_models(thread_id)
    service.submit_command(postgres_command(service, thread_id, "close_model", {"entry_id": workspace["current_entry_id"]}, "close"))
    service.compact_before(thread_id, service.snapshot(thread_id).last_event_seq)
    page = service.read_network_events(thread_id, context_id=original_context.id, attempt_id=attempts[0])
    layer = next(event for event in page["events"] if event["event_type"] == "network_layer")
    assert layer["attempt_id"] == attempts[0]
    assert layer["payload"]["layer"]["focus_ids"] == ["bus:1"]
    latest = service.read_network_events(thread_id, context_id=original_context.id)
    assert next(event for event in latest["events"] if event["event_type"] == "network_layer")["attempt_id"] == attempts[1]
    assert any(event["event_type"] == "command_accepted" for event in service.read_history(thread_id)["events"])
