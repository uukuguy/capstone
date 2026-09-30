from __future__ import annotations

from thread_fixtures import load_fixture

from capstone_agent.thread_fixture_runner import expected_commands, run_fixture


def test_historical_page_keeps_live_cancel_target() -> None:
    projection = run_fixture(load_fixture("historical-live-attempt"))

    assert projection.active_grid_page_id == "page_ieee39"
    assert projection.viewed_grid_page_id == "page_scigrid_2"
    assert "cancel_live_attempt" in projection.enabled_commands
    assert "send_professional" not in projection.enabled_commands


def test_gap_fixture_is_resync_required_and_has_no_business_commands() -> None:
    projection = run_fixture(load_fixture("resync-required"))

    assert projection.transport_state == "resync_required"
    assert projection.enabled_commands == frozenset({"reconnect", "resync", "help", "exit"})


def test_all_surfaces_share_the_same_semantic_command_set() -> None:
    fixture = load_fixture("interrupted-attempt")

    assert expected_commands(fixture, "web") == expected_commands(fixture, "tui")
    assert expected_commands(fixture, "tui") == expected_commands(fixture, "cli")


def test_idle_fixture_exposes_business_commands() -> None:
    projection = run_fixture(load_fixture("idle-ieee39"))

    assert projection.enabled_commands == frozenset({
        "send_auto",
        "send_professional",
        "model_switch",
        "replace_selection",
        "launch_case",
        "open_replay",
    })


def test_interrupted_attempt_offers_new_attempt_without_resuming_old_one() -> None:
    projection = run_fixture(load_fixture("interrupted-attempt"))

    assert projection.current_attempt_id == "attempt_008a"
    assert "retry_new_attempt" in projection.enabled_commands
    assert "send_ordinary" not in projection.enabled_commands
