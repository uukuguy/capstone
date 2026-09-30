from __future__ import annotations

import asyncio
from typing import Any

from capstone_agent.thread_protocol import CommandReceipt, EventPage, ThreadSnapshot
from capstone_agent.thread_tui import ThreadTuiApp


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
        app.query_one("#command-input").value = "查看当前模型"
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
        select = app.query_one("#model-select")
        select.value = "pypsa39"
        await pilot.click("#switch-model")
        assert "accepted" in str(app.query_one("#feedback").content)

    assert submitted[0]["kind"] == "switch_model"
    assert submitted[0]["payload"] == {"model_id": "pypsa39"}
