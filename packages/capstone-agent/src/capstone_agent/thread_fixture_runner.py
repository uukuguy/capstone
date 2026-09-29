"""Projection-only runner for the shared Web/TUI/CLI Thread UI fixtures."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .thread_protocol import EventPage, ThreadSnapshot


_SURFACES = frozenset({"web", "tui", "cli"})
_ACTIVE_PHASES = frozenset({"created", "accepted", "running", "committing"})
_TERMINAL_PHASES = frozenset({"cancelled", "interrupted", "completed", "failed"})
_RECOVERY_COMMANDS = frozenset({"reconnect", "resync", "help", "exit"})


class FixtureRunnerError(ValueError):
    """A fixture cannot be projected into a safe shared UI state."""


@dataclass(frozen=True, slots=True)
class FixtureProjection:
    transport_state: str
    run_state: str
    active_model_context_id: str
    active_grid_page_id: str
    viewed_grid_page_id: str
    current_attempt_id: str | None
    authority_labels: tuple[str, ...]
    enabled_commands: frozenset[str]


def _parts(fixture: Mapping[str, Any]) -> tuple[ThreadSnapshot, EventPage, Mapping[str, Any]]:
    snapshot = fixture.get("snapshot")
    event_page = fixture.get("event_page")
    local_view = fixture.get("local_view")
    if not isinstance(snapshot, ThreadSnapshot):
        raise FixtureRunnerError("fixture snapshot is not verified")
    if not isinstance(event_page, EventPage):
        raise FixtureRunnerError("fixture event page is not verified")
    if not isinstance(local_view, dict):
        raise FixtureRunnerError("fixture local_view is invalid")
    if event_page.thread_id != snapshot.thread_id:
        raise FixtureRunnerError("fixture event page thread does not match snapshot")
    if event_page.after_event_seq != snapshot.last_event_seq:
        raise FixtureRunnerError("fixture event page does not follow snapshot")
    return snapshot, event_page, local_view


def _transport_state(fixture: Mapping[str, Any]) -> str:
    assertions = fixture.get("assertions")
    if not isinstance(assertions, dict):
        return "live"
    state = assertions.get("transport_state", "live")
    if state not in {"live", "reconnecting", "resync_required", "offline"}:
        raise FixtureRunnerError("fixture transport_state is invalid")
    return state


def _view_state(snapshot: ThreadSnapshot, local_view: Mapping[str, Any]) -> tuple[str, str]:
    viewed = local_view.get("viewed_grid_page_id", snapshot.active_grid_page_id)
    if not isinstance(viewed, str) or not viewed:
        raise FixtureRunnerError("fixture viewed_grid_page_id is invalid")
    if local_view.get("replay") is not None:
        return "replay", viewed
    return ("historical" if viewed != snapshot.active_grid_page_id else "live"), viewed


def _execution_state(snapshot: ThreadSnapshot, event_page: EventPage) -> str:
    attempt = snapshot.current_attempt
    if attempt is None:
        return "idle"
    if any(event.event_type == "approval_requested" for event in event_page.events):
        return "approval_wait"
    if attempt.phase == "waiting":
        return "approval_wait"
    if attempt.phase in _ACTIVE_PHASES:
        return "active"
    if attempt.phase in _TERMINAL_PHASES:
        return "terminal"
    raise FixtureRunnerError("fixture attempt phase is invalid")


def _commands(*, transport: str, run_state: str, execution: str, view: str, attempt_phase: str | None) -> frozenset[str]:
    if transport != "live":
        return _RECOVERY_COMMANDS
    if run_state in {"closed", "failed"}:
        return frozenset({"open_replay"}) | ({"return_live"} if view != "live" else set())
    if view == "replay":
        return frozenset({"return_live"})

    commands: set[str] = {"open_replay"}
    if execution == "idle" and view == "live":
        commands.update({"send_ordinary", "send_professional", "model_switch", "replace_selection", "launch_case"})
    elif execution == "approval_wait":
        commands.update({"approve", "deny", "cancel_live_attempt"})
    elif execution == "active":
        commands.update({"cancel_live_attempt", "send_control"})
    elif execution == "terminal" and attempt_phase == "interrupted":
        commands.add("retry_new_attempt")

    if view == "historical":
        commands.add("return_live")
        commands.difference_update({"send_ordinary", "send_professional", "model_switch", "replace_selection", "launch_case"})
    return frozenset(commands)


def run_fixture(fixture: Mapping[str, Any]) -> FixtureProjection:
    snapshot, event_page, local_view = _parts(fixture)
    transport = _transport_state(fixture)
    view, viewed_page = _view_state(snapshot, local_view)
    execution = _execution_state(snapshot, event_page)
    attempt_phase = None if snapshot.current_attempt is None else snapshot.current_attempt.phase
    labels = tuple(
        label
        for event in event_page.events
        for label in (event.payload.get("authority_label"),)
        if isinstance(label, str) and label
    )
    return FixtureProjection(
        transport_state=transport,
        run_state=snapshot.run.state,
        active_model_context_id=snapshot.active_model_context.id,
        active_grid_page_id=snapshot.active_grid_page_id,
        viewed_grid_page_id=viewed_page,
        current_attempt_id=None if snapshot.current_attempt is None else snapshot.current_attempt.attempt_id,
        authority_labels=labels,
        enabled_commands=_commands(
            transport=transport,
            run_state=snapshot.run.state,
            execution=execution,
            view=view,
            attempt_phase=attempt_phase,
        ),
    )


def expected_commands(fixture: Mapping[str, Any], surface: str) -> frozenset[str]:
    if surface not in _SURFACES:
        raise FixtureRunnerError("fixture surface is invalid")
    return run_fixture(fixture).enabled_commands
