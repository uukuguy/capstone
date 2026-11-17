# Control persistent events

Owner: capstone-control; HTTP adapter: capstone-agent. Branch
`feat/control-events-20261117` targets dev `a7fb27d4` (task board PR135 accepted).

## Contract

Each accepted state revision records one bounded event in the same transaction.
Retries and stale observations record none. Control owns its event table; it
does not query Agent ledger tables. Events contain versioned state and binding
references, not objective text, credentials, command payloads or raw products.
Control sequence and Agent observation sequence remain distinct.

`read_events(workspace, goal_id, after=0, limit=50, through=None)` returns at
most 100 events. The first page fixes a through-sequence; subsequent pages can
pin that value. Workspace mismatch is not found. Legacy Goals report incomplete
coverage and receive no invented past events. Existing Goal responses are unchanged.

## Execution and acceptance

- [ ] Add `packages/capstone-control/tests/test_events.py`: retry/stale suppression,
  pagination under append, legacy coverage, version/binding identity and rollback.
  Run `uv run --project packages/capstone-agent pytest packages/capstone-control/tests/test_events.py -q`
  and confirm missing-event API failures before implementation.
- [ ] Add `capstone_control/events.py`; extend MemoryStore and PostgresStore atomic
  writes and indexed reads. Attach explicit event kinds at all service mutations.
- [ ] Add authorized GET `/api/v1/control/goals/{goal_id}/events` in control_host.py.
  Verify scope, bounded queries, and no execution wake on reads.
- [ ] Test real disposable PostgreSQL persistence, concurrency and rollback.
- [ ] Run focused Control/adapter checks; record results, commit owned paths and
  prepare a focused development CI route. CI needs new explicit approval.

The next UI slice connects runtime lanes and diagnostic links to this source.
This backend slice does not claim runtime-view, cloud or release acceptance.
