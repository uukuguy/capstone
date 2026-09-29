from __future__ import annotations

import pytest

from thread_fixtures import load_fixture


@pytest.mark.parametrize(
    "fixture_name",
    ["idle-ieee39", "historical-live-attempt", "resync-required", "interrupted-attempt"],
)
def test_thread_ui_fixture_loads_through_strict_protocol(fixture_name: str) -> None:
    fixture = load_fixture(fixture_name)

    assert fixture["fixture_id"] == fixture_name
    assert fixture["snapshot"].thread_id == "thr_demo_39"
    assert fixture["event_page"].thread_id == "thr_demo_39"


def test_historical_fixture_preserves_live_attempt_target() -> None:
    fixture = load_fixture("historical-live-attempt")
    snapshot = fixture["snapshot"]
    local_view = fixture["local_view"]

    assert local_view["viewed_grid_page_id"] != snapshot.active_grid_page_id
    assert snapshot.current_attempt is not None
    assert snapshot.current_attempt.target_model_context_id == snapshot.active_model_context.id


def test_resync_fixture_starts_from_verified_snapshot_base() -> None:
    fixture = load_fixture("resync-required")
    snapshot = fixture["snapshot"]
    page = fixture["event_page"]

    assert snapshot.base_event_seq == page.after_event_seq
    assert page.events == ()


def test_fixture_loader_rejects_unknown_fixture() -> None:
    with pytest.raises(FileNotFoundError):
        load_fixture("missing")
