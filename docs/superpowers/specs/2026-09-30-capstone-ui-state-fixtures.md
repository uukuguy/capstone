# Capstone Thread UI State Fixtures

**Status:** Proposed validation contract for the first Web/TUI prototype. These fixtures exercise presentation behavior; they do not define the final public `capstone-thread/1` wire schema.

**Purpose:** Web and Textual TUI must render the same `ThreadSnapshot + EventPage` semantics. A fixture describes the durable state and canonical events; each client derives its own local layout, focus, scroll, and terminal-renderer state.

## Fixture boundary

Each fixture has four parts:

```text
Fixture
  ├── snapshot       verified ThreadSnapshot at base_event_seq
  ├── events         contiguous canonical EventPage after the snapshot
  ├── local_view     viewed page / replay cursor / draft / viewport hints
  └── assertions     visible state + enabled commands for Web, TUI, CLI
```

The fixture never contains a Provider token, raw `pandapowerNet`/PyPSA object, raw hidden reasoning, arbitrary file path, or a native runtime event that the public projection cannot explain. `diagnostic` events may appear only in the diagnostics assertion and never change authoritative answer/evidence state.

### Shared identifiers

Fixtures use stable, readable IDs so a failure points to a target instead of a screen coordinate:

| Field | Example |
| --- | --- |
| `thread_id` | `thr_demo_39` |
| `run_id` | `run_001` |
| `model_context_id` | `ctx_ieee39_7` |
| `grid_page_id` | `page_ieee39` |
| `turn_id` | `turn_004` |
| `attempt_id` | `attempt_004a` |
| `command_id` | `cmd_switch_005` |
| `selection_revision` | `sel_2` |
| `event_seq` | monotonically increasing integer |

Model revision and selection revision are part of every structured target assertion. A fixture that omits them cannot verify stale-reference or receipt-loss behavior.

## Canonical fixture states

The first prototype must implement these ten fixtures. The names are stable test IDs, not user-facing labels.

| ID | Snapshot state | Local view | Primary assertion |
| --- | --- | --- | --- |
| `idle_ieee39` | Run open, IEEE-39 context active, no Attempt | live IEEE-39 page, empty draft | ordinary send, professional send, model/profile drawers, and Case launch enabled |
| `attempt_running` | Attempt running with tool progress | live page, draft “停止” | ordinary/professional send disabled; cancel and explicit control enabled |
| `approval_wait` | Attempt waiting on expiring approval | live page, approval card focused | approve, deny, cancel, source inspection enabled; ordinary send disabled |
| `switch_pending` | old context active, model switch accepted | old page, pending banner | old context remains effective until activation; duplicate Apply reuses command identity |
| `historical_live_attempt` | live Attempt on IEEE-39 | viewed SciGRID historical page | historical business actions disabled; global live cancel still enabled |
| `replay_admitted_result` | current Run with committed result | replay cursor at event 148 | read-only authority label and Return to live; no current mutation |
| `reconnecting` | last trusted snapshot, active Attempt unknown | previous page, draft retained | receipt-required commands paused; no false cancel acceptance |
| `resync_required` | cursor gap, verified replacement snapshot available | page marked recovery | only snapshot reload/reconnect/help/exit; projection replaced atomically |
| `interrupted_attempt` | Attempt interrupted with no checkpoint | live page, stale element chip | retry creates a new Attempt and preserves prior Attempt link |
| `case_blocked` | Case pinned to context, required step blocked | live page, Case rail open | same-context retry differs from corrected-context restart |

`closed_run` is a terminal extension of `replay_admitted_result`: it verifies that the same projection becomes read-only after `run_closed` and remains replayable.

## Representative fixture

The following is intentionally abbreviated. The implementation fixture should use the same field names and add bounded payloads for every event type under test.

```json
{
  "fixture_id": "historical_live_attempt",
  "snapshot": {
    "schema": "capstone-thread-snapshot/1",
    "thread_id": "thr_demo_39",
    "run": {"run_id": "run_001", "state": "open"},
    "active_model_context": {
      "id": "ctx_ieee39_7",
      "model_id": "ieee39",
      "model_revision": "7",
      "implementation_family": "pandapower",
      "selection_revision": "sel_2"
    },
    "active_grid_page_id": "page_ieee39",
    "current_attempt": {
      "turn_id": "turn_004",
      "attempt_id": "attempt_004a",
      "phase": "running",
      "target_model_context_id": "ctx_ieee39_7"
    },
    "last_event_seq": 183,
    "base_event_seq": 180
  },
  "events": [
    {"event_seq": 181, "event_type": "grid_page_registered", "grid_page_id": "page_scigrid_2"},
    {"event_seq": 182, "event_type": "grid_page_viewed", "grid_page_id": "page_scigrid_2", "view_only": true},
    {"event_seq": 183, "event_type": "attempt_progress", "attempt_id": "attempt_004a", "phase": "running"}
  ],
  "local_view": {
    "viewed_grid_page_id": "page_scigrid_2",
    "replay": null,
    "draft": "停止当前计算",
    "element_reference": null
  },
  "assertions": {
    "web": {
      "header": "Attempt attempt_004a running",
      "banner": "Viewing SciGRID rev 2 · historical",
      "enabled_commands": ["cancel_live_attempt", "send_control", "return_live", "open_replay"],
      "disabled_commands": ["send_ordinary", "send_professional", "launch_case", "replace_selection"]
    },
    "tui": {
      "focused_surface": "grid",
      "live_attempt_rail": "Stop attempt_004a",
      "enabled_keys": ["Ctrl+C", "F7", "f", "r", "Esc"]
    },
    "cli": {
      "status_line": "view=historical live_attempt=attempt_004a",
      "control_result": "command receipt targets attempt_004a"
    }
  }
}
```

The event `grid_page_viewed` is local presentation state in the production protocol; the fixture may include it in `local_view` instead of the durable page if the final contract keeps viewing entirely client-local. The assertion is what matters: viewing SciGRID cannot change `active_model_context_id` and cannot hide the live cancel target.

## Cross-client assertion contract

For each fixture, the test harness compares semantic projections rather than DOM or terminal escape sequences:

| Semantic projection | Web | TUI | CLI |
| --- | --- | --- | --- |
| active model/context | header badge + grid marker | top status + active tab | prompt/status JSON |
| viewed page | selected tab + read-only banner | selected page tab + marker | replay/view metadata |
| live Attempt | Attempt rail + progress card | status rail + progress card | stderr progress / JSONL event |
| draft state | composer value and target warning | editor buffer and target warning | input buffer / pending command |
| enabled command set | button/menu disabled state | keymap/palette availability | accepted/rejected command or exit code |
| authority/evidence | card label and source drawer | card label and evidence screen | structured output/reference |
| recovery cursor | diagnostics drawer | footer cursor/modal | stderr + structured error |

The fixture test fails if one client:

- enables a command another client marks semantically invalid;
- treats `historical`, `reference/non-authoritative`, or `diagnostic/unadmitted` as `admitted/current`;
- loses the target model revision, selection revision, Attempt ID, or command ID;
- reports a command as accepted without a matching canonical receipt;
- labels an interrupted Attempt as resumed;
- changes the business active model when only the viewed page changed.

## Event sequences for the first prototype

The fixture runner should cover these minimal event sequences:

1. **Idle → professional preparation → committed answer:** `turn_accepted`, `context_preparing`, `tool_started`, `result_admitted`, `answer_committed`.
2. **Running → control:** `attempt_started`, `control_received`, `cancel_requested`, `attempt_cancelled` or `attempt_interrupted`.
3. **Switch after boundary:** `command_accepted`, `model_context_preparing`, `attempt_terminal`, `model_context_activated`.
4. **Approval:** `approval_requested`, `approval_decided`, then the normal Attempt terminal path.
5. **Gap recovery:** `resync_required`, verified snapshot replacement, `read_events(after_seq=base_event_seq)`.
6. **Case blocked:** `case_started`, step Attempt events, `case_step_blocked`, either same-context retry or corrected-context restart.

The event list is deliberately small. The UI must not depend on Pi native event names or on an answer string to infer a state.

## Scroll, focus, and viewport assertions

These are local presentation details but need deterministic checks:

- Streaming while at the latest message keeps the viewport anchored to the latest committed/streaming item.
- Scrolling upward during streaming preserves the user’s position and shows an unread count plus `Return to latest`; it does not jump on every token.
- Opening a drawer or approval card stores the invoking element and restores focus after close.
- Selecting an element records model ID, model revision, page ID, element ID, and selection source. Changing only the viewport does not invalidate it; changing the model/revision or entering replay does.
- TGP repaint, resize, and fallback can change terminal presentation only. The semantic grid page and selected element remain identical.

## Completion gate

This fixture contract is ready for implementation when:

1. the public Thread protocol names are frozen enough to serialize the abbreviated example;
2. a fixture runner can derive the same enabled command set for Web and TUI;
3. the ten state fixtures and the six event sequences have explicit expected receipts;
4. the browser and Ghostty/iTerm2 prototypes pass the semantic assertions without requiring a Provider credential;
5. failures point to fixture ID, event sequence, command target, and client surface.

Until then, the UI design remains proposed and the existing Case App remains the compatibility presentation.
