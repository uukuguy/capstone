# M6 Task 1 Report: Trusted Application Case Definitions

## Status

DONE

## Commit

- `79647c5` — `feat: add trusted application case definitions`

## Changes

- Added frozen `CaseStepDefinition`, `CaseDefinition`, and `CaseCatalog`.
- Added strict parsing for the server-built `capstone-catalog/1.0` projection.
- Added bounded validation for case IDs, versions, model constraints, step count, titles, and instructions.
- Added raw SHA-256 instruction digests and canonical UTF-8 `case:sha256:` revisions.
- Added trusted step titles and version/model metadata to the existing pandapower and PyPSA catalog projection.
- Added focused registration, determinism, duplicate, bounds, unknown-field, schema, and lookup tests.

## TDD Evidence

The first focused run failed during collection because `case_definition.py` did not
exist:

```text
ModuleNotFoundError: No module named 'capstone_agent.case_definition'
```

After implementation, the focused tests passed:

```text
uv run --project packages/capstone-agent pytest \
  packages/capstone-agent/tests/test_case_definition.py \
  packages/capstone-agent/tests/test_catalog.py -q

11 passed in 0.02s
```

## Verification

Targeted diagnostics passed:

```text
uv run --project packages/grid-agent pyright \
  packages/capstone-agent/src/capstone_agent/case_definition.py \
  packages/capstone-agent/src/capstone_agent/catalog.py \
  packages/capstone-agent/tests/test_case_definition.py

0 errors, 0 warnings, 0 informations
```

The full Capstone Agent test suite passed:

```text
uv run --project packages/capstone-agent pytest \
  packages/capstone-agent/tests \
  --ignore=packages/capstone-agent/tests/test_registered_workers.py -q

261 passed, 27 skipped, 1 warning in 8.34s
```

The warning is the existing Starlette deprecation warning for importing
`httpx` through `starlette.testclient`. `git diff --check` passed, and the real
`build_catalog()` output was parsed successfully for pandapower and PyPSA cases.

## Concerns

- The full suite retains one pre-existing FastAPI/Starlette deprecation warning.
- Task 2 and Thread persistence were not started or modified.

## Review Fix

The catalog parser now validates incoming data against a fresh projection from
the trusted `catalog.build_catalog()` plus `build_registry()` source path. It
requires the producer's exact application and case fields, identities, model
constraints, trusted titles, summaries, step titles, and instructions. Caller
authored application/case/model identities, aliases, mapping-form instructions,
and altered metadata are rejected while registered pandapower and PyPSA cases
remain accepted. The producer seam is reused rather than adding a second
hard-coded list of domain identities.

Derived step titles now reserve the `Step <ordinal>: ` prefix before truncation,
so the final title remains within the 256-character bound.

Added regressions cover forged application, case, model, instruction, mapping,
and alias projections plus the final derived-title length.

Review-fix verification:

```text
uv run --project packages/capstone-agent pytest \
  packages/capstone-agent/tests/test_case_definition.py \
  packages/capstone-agent/tests/test_catalog.py -q

18 passed in 0.03s

uv run --project packages/grid-agent ruff check \
  packages/capstone-agent/src/capstone_agent/case_definition.py \
  packages/capstone-agent/src/capstone_agent/catalog.py \
  packages/capstone-agent/tests/test_case_definition.py

All checks passed!

uv run --project packages/grid-agent pyright \
  packages/capstone-agent/src/capstone_agent/case_definition.py \
  packages/capstone-agent/src/capstone_agent/catalog.py

0 errors, 0 warnings, 0 informations

uv run --project packages/capstone-agent pytest \
  packages/capstone-agent/tests \
  --ignore=packages/capstone-agent/tests/test_registered_workers.py -q

268 passed, 27 skipped, 1 warning in 8.35s
```

## 2026-10-09: Shared general Pi executor Task 1

Status: complete for the contract and HTTP client scope.
Commit: `0a57acc`.

Owned files:

- `packages/capstone-agent/src/capstone_agent/pi_delegation.py`
- `packages/capstone-agent/tests/test_pi_delegation.py`

Implemented immutable request and result documents with exact versioned schemas.
Documents enforce finite JSON, byte/depth/node limits, no protected fields,
unique message/reference/task identities, and host task/parent/config binding.
History uses `ConversationContext` validation. Dependency results are full
bounded general task results from the same parent Attempt, with distinct task
identities. Sources and artifacts are external observation records with host
identity, task identity, parent Attempt identity, kind, and bounded metadata.
They cannot carry Authority result/evidence references.

Added `GeneralPiExecutor` protocol and `HttpGeneralPiExecutor`. Identity and
capability mappings are defensively copied and immutable. Origin is selected
by the host constructor; requests cannot select an endpoint. An optional
protected control token goes only in the HTTP Authorization header. HTTP
redirects and environment proxy inheritance are disabled.

Transport:

- POST `/tasks`: full request document; response exactly `{task_id}`.
- GET `/tasks/{task_id}`: exactly `{status, events, result}`. Queued/running
  states require null result. Terminal state must match the bound result.
- DELETE `/tasks/{task_id}`: cancellation; response is bounded JSON.
- Events require unique stable `event_id`; cumulative polls are deduplicated.
- NodeControl and request-budget checkpoints bound polling and response reads.
  A parent stop, lease callback error, deadline, malformed response, or failed
  transport cancels in `finally`. An unconfirmed cancellation adds an unknown
  remote-state note without replacing the original parent error.

TDD evidence:

1. Initial focused run failed at collection because the implementation module
   was absent, as required by the task brief.
2. Initial implementation passed 22 focused tests.
3. Added malformed shape, cancellation failure, and slow response checks. Four
   tests failed for the expected missing validation/lifecycle behavior.
4. Fixed these failures; focused tests passed 31/31.
5. Final adjacent checks passed: 130 tests, 1 skipped. Command:
   `uv run --project packages/capstone-agent pytest packages/capstone-agent/tests/test_pi_delegation.py packages/capstone-agent/tests/test_conversation_context.py packages/capstone-agent/tests/test_request_intent.py -q`.
6. `git diff --check` passed for the task-owned paths before commit.

Fake loopback HTTP tests cover both entrypoints, identical identity, header
authorization, cancellation, parent deadline, request time budget, oversized
response, and event replay. Tests made no Provider calls.

Limits: this task proves the host contract and client lifecycle. It does not
prove container isolation, native Pi execution, source quality, Provider
behavior, or deployment readiness. Those remain in the later executor and
integration tasks. No automatic retries are present. A transport failure may
leave an unknown remote state if cancellation cannot be confirmed.

Appended the commit record to `docs/status/JOURNAL.md`. Recovery checkpoint
ownership stays with the parent agent because this task changes only its
assigned contracts, and the wider delivery remains active.

## 2026-10-09: Task 1 lifecycle review fixes

Status: implemented. Commit: `d540dc7`.

Read the current general Pi Task 1 review after its stale M6 report was replaced.
Fixed all three findings in the same two owned files.

- Cancellation has a separate 0.5-second monotonic cleanup budget. DELETE
  and status reads check it, with network operation timeouts at most 0.1
  seconds and limited by the remaining budget at each request. A continuous
  slow response cannot extend cleanup indefinitely. A blocked socket operation
  can delay the next checkpoint by its bounded operation timeout.
- DELETE must return exactly `{task_id, status: "cancellation_requested"}`.
  This confirms acceptance only. The client then polls GET under the same
  cleanup budget until the result reaches a terminal status. The full result
  contract, task identity, executor identity, and matching status are checked.
  All protocol terminal statuses mean execution has stopped. An already
  completed task can therefore confirm stop. `cancel(task_id)` has no parent
  request argument, so it validates the terminal result's parent identity
  shape rather than claiming a separately known parent binding.
- Unconfirmed stop, wrong-task receipt, malformed result, or cleanup timeout
  adds an unknown-state note while retaining the original parent exception.
- Parent control and task deadline are checked after each event callback and
  immediately before a terminal result is accepted.

Novel tests first reproduced seven expected failures: invalid cancellation
receipts, continuous slow DELETE, and callback cancellation/deadline bypass.
After the acceptance-versus-stop distinction was confirmed with the parent,
three further failing tests reproduced missing terminal polling, wrong-task
terminal acceptance, and absent verification of an already completed task.

Verification:

- Focused executor suite: 41 passed.
- Executor plus context and intent suites: 140 passed, 1 skipped.
- Task-owned `git diff --check`: passed before commit.
- No Provider calls, server edits, or deployments.

Required server contract: DELETE acknowledges the request with the exact
receipt above; GET must retain the full bound terminal task result after
cancellation. A cancellation flag alone must not mark the task stopped.
The commit journal line was appended. Parent retains shared checkpoint ownership.

## 2026-10-09: Task 1 response-header deadline fix

Status: implemented. Commit: `ba0d6ce`.

Read the updated Task 1 re-review. Its novel slow-header finding reproduced:
the first regression took 1.33 seconds against a 0.5-second cleanup budget.
The body checkpoint could not interrupt the synchronous header read.

The transport now runs a private `httpx.AsyncClient` exchange inside the
synchronous worker-thread API. `asyncio.wait_for` bounds the whole fetch,
including connection and response headers. Every call receives the remaining
task or cleanup budget. A 25-millisecond async watchdog runs the parent
checkpoint while network work is pending. Cancelling the fetch task closes
its async client and stream; cleanup awaits that task rather than abandoning
a live network request. Existing socket operation timeouts, JSON bounds,
request identities, terminal confirmation, and unknown-state notes remain.

The novel loopback test sends a complete status line and then slow header
bytes, requiring cancellation to fail within 0.75 seconds. A socket failure
also yields the required bounded unknown state, so the test accepts transport
failure as well as cleanup timeout. The original regression failed on elapsed
time; the async transport passed it. Existing slow-body coverage remains.

Verification: combined executor/context/intent suite passed 141 tests with
1 skip. This includes 42 executor tests. Task-owned diff check passed.
No Provider calls, server changes, or deployments were made.

The parent clarified that the current `NodeControl` contract requires a
finite numeric deadline. The obsolete optional-deadline suggestion was not
implemented. The sync API runs in worker threads; it does not support callers
that invoke it directly from an already running asyncio loop.

Appended the commit journal line. Shared recovery checkpoint ownership remains
with the parent agent while integration work continues.
