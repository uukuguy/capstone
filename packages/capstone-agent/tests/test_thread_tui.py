from __future__ import annotations

import asyncio
from typing import Any

from textual.widgets import Button, Input, Select, Static

from capstone_agent.thread_protocol import CommandReceipt, EventPage, ThreadSnapshot
from capstone_agent.thread_tui import ThreadTuiApp, ThreadTuiSessionAdapter


def _snapshot() -> ThreadSnapshot:
    return ThreadSnapshot.from_document({
        "schema": "capstone-thread-snapshot/1", "thread_id": "thr_demo_39",
        "run": {"run_id": "run_001", "state": "open"},
        "active_model_context": {
            "id": "ctx_ieee39_7", "model_id": "ieee39", "model_revision": "7",
            "implementation_family": "pandapower", "selection_revision": "sel_2",
        },
        "active_grid_page_id": "page_ieee39", "current_attempt": None,
        "last_event_seq": 0, "base_event_seq": 0,
    })


def _events() -> EventPage:
    return EventPage.from_document({
        "schema": "capstone-thread-events/1", "thread_id": "thr_demo_39",
        "after_event_seq": 0, "next_event_seq": 0, "has_more": False, "events": [],
    }, expected_after_seq=0)


def _receipt(command: dict[str, Any]) -> CommandReceipt:
    return CommandReceipt(
        command_id=command["command_id"], idempotency_key=command["idempotency_key"],
        thread_id=command["thread_id"], run_id=command.get("run_id"), status="accepted",
        accepted_event_seq=1, rejection=None, target=None,
    )


def test_tui_submits_professional_command_with_current_cursor() -> None:
    asyncio.run(_test_tui_submits_professional_command_with_current_cursor())


async def _test_tui_submits_professional_command_with_current_cursor() -> None:
    submitted: list[dict[str, Any]] = []

    def submit(command: dict[str, Any]) -> CommandReceipt:
        submitted.append(command)
        return _receipt(command)

    app = ThreadTuiApp(_snapshot(), _events(), submit)
    async with app.run_test(size=(120, 40)) as pilot:
        app.query_one("#command-input", Input).value = "查看当前模型"
        await pilot.click("#send-professional")

    assert submitted[0]["kind"] == "send_professional"
    assert submitted[0]["expected_event_seq"] == 0
    assert submitted[0]["payload"] == {"text": "查看当前模型"}


def test_tui_model_switch_uses_selected_model_and_shows_receipt() -> None:
    asyncio.run(_test_tui_model_switch_uses_selected_model_and_shows_receipt())


async def _test_tui_model_switch_uses_selected_model_and_shows_receipt() -> None:
    submitted: list[dict[str, Any]] = []

    def submit(command: dict[str, Any]) -> CommandReceipt:
        submitted.append(command)
        return _receipt(command)

    app = ThreadTuiApp(
        _snapshot(), _events(), submit,
        model_options=(("ieee39", "IEEE-39 · pandapower"), ("pypsa39", "PyPSA-39 · PyPSA")),
    )
    async with app.run_test(size=(120, 40)) as pilot:
        select = app.query_one("#model-select", Select)
        select.value = "pypsa39"
        await pilot.click("#switch-model")
        assert "accepted" in str(app.query_one("#feedback", Static).content)

    assert submitted[0]["kind"] == "switch_model"
    assert submitted[0]["payload"] == {"model_id": "pypsa39"}


def test_tui_keeps_message_controls_available_while_next_turn_controls_are_pending() -> None:
    asyncio.run(_test_tui_keeps_message_controls_available_while_next_turn_controls_are_pending())


async def _test_tui_keeps_message_controls_available_while_next_turn_controls_are_pending() -> None:
    submitted: list[dict[str, Any]] = []

    def submit(command: dict[str, Any]) -> CommandReceipt:
        submitted.append(command)
        return _receipt(command)

    snapshot = ThreadSnapshot.from_document({
        **_snapshot().to_document(),
        "pending_model_switch": {
            "command_id": "cmd_switch_1", "model_id": "pypsa39", "model_revision": "1",
            "implementation_family": "pypsa", "selection": {
                "schema": "capstone-model-capability-selection/1", "enabled_profiles": [],
            },
        },
    })
    app = ThreadTuiApp(snapshot, _events(), submit, model_options=(("ieee39", "IEEE-39"), ("pypsa39", "PyPSA-39")))
    async with app.run_test(size=(120, 40)) as pilot:
        assert not app.query_one("#send-professional", Button).disabled
        app.query_one("#command-input", Input).value = "查看当前模型"
        await pilot.click("#send-professional")
    assert submitted[0]["kind"] == "send_professional"


def test_tui_session_adapter_preserves_typed_command_identity() -> None:
    calls: list[tuple[str, dict[str, Any], int, str, str]] = []

    class _Session:
        def snapshot(self) -> ThreadSnapshot:
            return _snapshot()

        def events(self, *, after: int = 0) -> EventPage:
            return _events()

        def command(self, kind: str, payload: dict[str, Any], *, expected_event_seq: int, command_id: str, idempotency_key: str) -> CommandReceipt:
            calls.append((kind, payload, expected_event_seq, command_id, idempotency_key))
            return _receipt({"kind": kind, "payload": payload, "expected_event_seq": expected_event_seq, "command_id": command_id, "idempotency_key": idempotency_key, "thread_id": "thr_demo_39"})

    command = {
        "kind": "send_professional", "payload": {"text": "查看模型"}, "expected_event_seq": 3,
        "command_id": "cmd_1", "idempotency_key": "idem_1",
    }
    receipt = ThreadTuiSessionAdapter(_Session()).submit(command)
    assert receipt.status == "accepted"
    assert calls == [("send_professional", {"text": "查看模型"}, 3, "cmd_1", "idem_1")]


def test_tui_live_session_refreshes_snapshot_and_event_cursor() -> None:
    asyncio.run(_test_tui_live_session_refreshes_snapshot_and_event_cursor())


async def _test_tui_live_session_refreshes_snapshot_and_event_cursor() -> None:
    class _Session:
        def __init__(self) -> None:
            self.latest = _snapshot()
            self.polled = False

        def snapshot(self) -> ThreadSnapshot:
            if self.polled:
                return ThreadSnapshot.from_document({
                    **self.latest.to_document(), "last_event_seq": 1,
                })
            return self.latest

        def events(self, *, after: int = 0) -> EventPage:
            if after == 0 and self.polled:
                return EventPage.from_document({
                    "schema": "capstone-thread-events/1", "thread_id": "thr_demo_39",
                    "after_event_seq": 0, "next_event_seq": 1, "has_more": False, "events": [{
                        "event_id": "evt_1", "event_seq": 1, "event_type": "attempt_started", "event_version": 1,
                        "thread_id": "thr_demo_39", "run_id": "run_001", "turn_id": "turn_001",
                        "attempt_id": "attempt_001", "model_context_id": "ctx_ieee39_7", "selection_revision": "sel_2",
                        "occurred_at": "2026-10-01T00:00:00+00:00", "visibility": "public", "payload": {},
                    }],
                }, expected_after_seq=0)
            return _events()

        def command(self, kind: str, payload: dict[str, Any], *, expected_event_seq: int, command_id: str, idempotency_key: str) -> CommandReceipt:
            raise AssertionError("command is not part of this refresh test")

    session = _Session()
    app = ThreadTuiApp(_snapshot(), _events(), lambda command: _receipt(command), session=session, poll_interval=0.05)
    async with app.run_test(size=(120, 40)) as pilot:
        session.polled = True
        await pilot.pause(0.08)
        assert app._event_cursor == 1
        assert app.events.next_event_seq == 1


def _paged_event(after: int, next_seq: int, *, has_more: bool) -> EventPage:
    return EventPage.from_document({
        "schema": "capstone-thread-events/1", "thread_id": "thr_demo_39",
        "after_event_seq": after, "next_event_seq": next_seq, "has_more": has_more,
        "events": [{
            "event_id": f"evt_{next_seq}", "event_seq": next_seq,
            "event_type": "attempt_progress", "event_version": 1,
            "thread_id": "thr_demo_39", "run_id": "run_001",
            "turn_id": "turn_001", "attempt_id": "attempt_001",
            "model_context_id": "ctx_ieee39_7", "selection_revision": "sel_2",
            "occurred_at": "2026-10-01T00:00:00+00:00", "visibility": "public",
            "payload": {"phase": "running"},
        }],
    }, expected_after_seq=after)


def test_tui_live_poll_applies_all_event_pages_before_advancing_snapshot() -> None:
    asyncio.run(_test_tui_live_poll_applies_all_event_pages_before_advancing_snapshot())


async def _test_tui_live_poll_applies_all_event_pages_before_advancing_snapshot() -> None:
    class _Session:
        def __init__(self) -> None:
            self.polled = False
            self.requested: list[int] = []

        def snapshot(self) -> ThreadSnapshot:
            return ThreadSnapshot.from_document({
                **_snapshot().to_document(), "last_event_seq": 2 if self.polled else 0,
            })

        def events(self, *, after: int = 0) -> EventPage:
            if not self.polled:
                return _events()
            self.requested.append(after)
            if after == 0:
                return _paged_event(0, 1, has_more=True)
            if after == 1:
                return _paged_event(1, 2, has_more=False)
            raise AssertionError(f"unexpected cursor {after}")

        def command(self, kind: str, payload: dict[str, Any], *, expected_event_seq: int, command_id: str, idempotency_key: str) -> CommandReceipt:
            raise AssertionError("no command expected")

    session = _Session()
    app = ThreadTuiApp(_snapshot(), _events(), lambda command: _receipt(command), session=session, poll_interval=0.05)
    async with app.run_test(size=(120, 40)) as pilot:
        session.polled = True
        await pilot.pause(0.08)
        assert session.requested[:2] == [0, 1]
        assert app._event_cursor == app.snapshot.last_event_seq == 2
        assert app.events.next_event_seq == 2
        assert len(app._event_ids) == 2


def test_tui_live_poll_freezes_on_incomplete_event_pages() -> None:
    asyncio.run(_test_tui_live_poll_freezes_on_incomplete_event_pages())


async def _test_tui_live_poll_freezes_on_incomplete_event_pages() -> None:
    class _Session:
        def __init__(self) -> None:
            self.polled = False

        def snapshot(self) -> ThreadSnapshot:
            return ThreadSnapshot.from_document({
                **_snapshot().to_document(), "last_event_seq": 2 if self.polled else 0,
            })

        def events(self, *, after: int = 0) -> EventPage:
            return _paged_event(0, 1, has_more=False) if self.polled else _events()

        def command(self, kind: str, payload: dict[str, Any], *, expected_event_seq: int, command_id: str, idempotency_key: str) -> CommandReceipt:
            raise AssertionError("no command expected")

    session = _Session()
    app = ThreadTuiApp(_snapshot(), _events(), lambda command: _receipt(command), session=session, poll_interval=0.05)
    async with app.run_test(size=(120, 40)) as pilot:
        session.polled = True
        await pilot.pause(0.08)
        assert app._event_cursor == app.snapshot.last_event_seq == 0
        assert app._recovery_required
        assert app.query_one("#send-professional", Button).disabled
