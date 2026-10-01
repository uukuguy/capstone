from __future__ import annotations

import json
from pathlib import Path

import pytest

from capstone_agent.thread_http import ThreadResyncRequired
from validation.thread.provider_free_host import ProviderFreeThreadHost


def _pandas_question(index: int = 0) -> str:
    document = json.loads(Path("validation/application/pandapower-scripted-task.json").read_text())
    return document["questions"][index]["text"]


def test_provider_free_thread_selection_and_retry_preserve_attempt_lineage(tmp_path: Path) -> None:
    with ProviderFreeThreadHost("pandapower-static-analysis", tmp_path) as session:
        initial = session.create()
        profile = {"profile_id": "pandapower-static-analysis", "profile_version": "1.0.1"}
        selection = session.command("replace_selection", {"enabled_profiles": [profile]})
        assert selection.status == "accepted"
        accepted = session.command("send_professional", {"text": _pandas_question()})
        assert accepted.status == "accepted"
        events = session.events(after=initial.last_event_seq).events
        completed = next(event for event in reversed(events) if event.event_type == "attempt_completed")

        failed = session.command("send_professional", {"text": "故意使用未登记的指令触发失败。"})
        assert failed.status == "accepted"
        failed_events = session.events(after=completed.event_seq).events
        failed_terminal = next(event for event in reversed(failed_events) if event.event_type == "attempt_failed")
        retry = session.command("retry_new_attempt", {"attempt_id": failed_terminal.attempt_id})
        assert retry.status == "accepted"
        retry_events = session.events(after=failed_terminal.event_seq).events
        retry_started = next(event for event in retry_events if event.event_type == "attempt_started")
        assert retry_started.attempt_id != failed_terminal.attempt_id
        assert retry_started.turn_id == failed_terminal.turn_id
        assert all(event.event_seq <= failed_terminal.event_seq for event in events)


def test_provider_free_thread_cursor_gap_requires_verified_snapshot(tmp_path: Path) -> None:
    with ProviderFreeThreadHost("pandapower-static-analysis", tmp_path) as session:
        session.create()
        session.command("send_professional", {"text": _pandas_question()})
        # The validation host intentionally exposes compaction only through the
        # service seam; this exercises the same resync response as Postgres.
        service = session._host.service  # type: ignore[attr-defined]
        snapshot = session.snapshot()
        service.compact_before(snapshot.last_event_seq - 1)
        with pytest.raises(ThreadResyncRequired) as error:
            session.events(after=0)
        assert error.value.snapshot.base_event_seq == snapshot.last_event_seq - 1
        recovered = session.events(after=error.value.snapshot.base_event_seq)
        assert recovered.after_event_seq == error.value.snapshot.base_event_seq
