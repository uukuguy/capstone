# OP-04 Task Report

## RED

- Baseline `test_rpc_requires_ack_before_agent_end` passed once, so the old
  race was not reproducible as a single deterministic failure in this run.
  The prior review identified that the fake provider emitted `agent_end`
  without first consuming stdin, leaving protocol ordering timing-dependent.
- No production RPC code was changed. There is no corresponding fixture in
  `packages/capability-agent-kernel/tests/runtime/test_rpc.py` requiring this
  change; that file already uses synchronized prompt reads and `try/finally`.

## GREEN

- Updated `packages/grid-agent/tests/runtime/test_rpc.py::test_rpc_requires_ack_before_agent_end`
  so fake Pi reads the complete prompt before emitting the deliberately
  unacknowledged `agent_end` event. The assertion remains exact and only
  matches `before prompt acknowledgement`.
- Wrapped that client lifecycle in `try/finally` cleanup.
- Added independent
  `test_rpc_reports_prompt_send_failure_when_provider_exits_early`, which waits
  for a fake provider's exit and asserts only `Pi RPC prompt could not be sent`.
  Cleanup detaches the broken stdin safely before `client.stop()`.
- Focused tests: 2 passed.
- Required 30 repetitions of the synchronized protocol test: 30/30 passed.
- Runtime suite: 72 passed.

## Self-review

- Scope is limited to the permitted grid RPC test file; no production RPC,
  kernel fixture, state, or documentation files were modified.
- The two failure modes have separate tests and separate exact regexes; the
  original protocol assertion was not broadened.
- Provider processes are stopped in `finally`; the early-exit case also closes
  the broken buffered stdin without leaving a finalizer warning or child
  process.

## Reproduction commands

```sh
uv run --project packages/grid-agent pytest packages/grid-agent/tests/runtime/test_rpc.py::test_rpc_requires_ack_before_agent_end packages/grid-agent/tests/runtime/test_rpc.py::test_rpc_reports_prompt_send_failure_when_provider_exits_early -q
for attempt in $(seq 1 30); do uv run --project packages/grid-agent pytest packages/grid-agent/tests/runtime/test_rpc.py::test_rpc_requires_ack_before_agent_end -q || exit 1; done
uv run --project packages/grid-agent pytest packages/grid-agent/tests/runtime -q
```

Commit: `2c2b639` (`test: synchronize RPC protocol violation fixtures`).
