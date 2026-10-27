# Shared tool composition and semantic data packages

Implementation feedback: plain binding metadata is retained as `declared`;
only fields selected by an actual issued call ref and JSON pointer are `observed`.
Package saves publish unique paths and serialize product-manifest updates.
Large program returns use bounded saved-file projections across both model and
host transport. Issued refs may be reused within one session; separate DR nodes
continue to require explicit saved package inputs.

User approved implementation on2026-10-28. This implements the shared mechanism
discussed in the core evolution notebook; the earlier same-task comparison stays
frozen. The existing enterprise application selects a versioned neutral execution
capability. No business tool names, regions, metrics, SQL or task workflow are fixed.

## Execution

Publish `agent_tools_execute` only when the task has the registered composition
capability, ordinary bash/write permission and gateway grants. DR organizers keep
their organization-only role; isolated execution nodes and the lightweight loop
use the same tool. Historical contexts without the capability retain their grant.

Input: `program` (async JavaScript body), `tools` (explicit admitted gateway tool
names), optional business `purpose`, `concurrency`, `max_calls`, `timeout_ms`.
The program runs in a separate Node process under the existing native task UID,
workspace and network policy, with a clean environment and no gateway/provider
credentials. This reuses the existing native execution boundary, not a JS VM as
a security boundary. The process group and pending calls stop on cancellation or
timeout. Budgets are versioned in `tool-composition-policy.json`.

Program API:

- `await tools.call(name, arguments)` returns `{ref, ok, status, data, gaps,
  provenance, value}`. `value` is the normalized source Result, not invented rows.
  Calls use the existing protected gateway relay and exact published Schema;
  each has a distinct ID, host receipt and normal start/end events. The relay's
  application grant and source identity checks remain authoritative.
- `tools.describe(name)` exposes the selected published contract without a new
  network connection. `Promise.all`, normal loops and data-dependent argument
  passing compose known operations. Calls have a bounded concurrency and budget;
  errors do not cause automatic retries. Code can handle known pagination or
  return an observed limitation for the next reasoning step.
- `await python(code, data)` executes local Python with JSON stdin and returns
  its stdout; it has the same native workspace rights and clean environment.
  This combines authorized retrieval with existing analysis/rendering libraries.
- `print(text)` reports bounded progress; `return value` returns the program's
  result. Large tool data stays in task-local files and packages, not the next
  model prompt. Program output is bounded through the existing result projection.

## Reusable semantic data

`await saveContext(name, {bindings, datasets})` builds a self-contained
`capstone-semantic-data/1` JSON artifact from actual observed calls. Dataset entries
use `{name, call: result.ref, pointer}`; source fields use
`{call: result.ref, pointer}`. Literal bindings use `{value}` and remain explicitly
declared/unverified. Unknown bindings remain unknown. The host derives selected
values from captured source results, keeps original receipt/provenance/status/gaps
and content hashes, and never converts these into Authority results.

The package retains normalized source Results and selection pointers instead of
fragile sibling filenames. Large upstream resource/dataset handles remain handles;
no business files become full-file base64 messages. Actual file and processing
budgets remain separate. The package is listed as a support product without
overwriting existing primary products. `await loadContext(path)` checks the schema
and source hashes and exposes `{bindings, datasets}` for local work.

DR producers return the package as a normal artifact output; consumers explicitly
select its result slot through existing read-only input materialization. They can
reuse the same object/metric/unit/source/window/aggregation facts and data without
another discovery/query. There is no cross-attempt global cache or silent source
version equivalence. Contract revision is not a data revision.

## Acceptance

Focused tests cover real process isolation/cleanup, overlapping calls, dependent
arguments, errors, cancellation, budgets, grant/schema validation, separate child
events, context evidence derivation and tamper detection. SDK/host tests verify
publication and both execution roles. Rebuild and real Vivaldi new-conversation
trials use MCP-discovered operations with both lightweight and DR modes, save a
data package and reuse it in a downstream calculation. Record call count, model
responses, source identity and products. Do not claim a speedup from unequal tasks.
