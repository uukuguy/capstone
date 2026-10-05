# Thread model state repair

## Confirmed defect

The user opened `case24_ieee_rts` in ordinary conversation. The answer said
RTS was open, but the Thread and left topology stayed on IEEE39. The next
AC flow used IEEE39. Read-only inspection of the local ledger confirmed the
mismatch. RTS was registered by the simulator authority; the Web catalog
export omitted it. The earlier statement that RTS was unregistered was wrong.

The earlier [M11 verification](2026-10-05-capstone-m11-cloud-verification.md)
covered restricted scripted execution. It did not prove this ordinary
model-open path. This repair checks native RPC events and normal hosted
application composition.

## Changes

- Export the complete registered pandapower catalog in both hosted roots.
  Keep exact source-backed revisions and short operator labels. Bound cold
  export at 120 seconds, with output-size and process-failure checks.
- Submit model selection and its original activating instruction together.
  Use the accepted ledger cursor. Preserve failed drafts, gate concurrent
  requests, and resume the same pending selection safely.
- Bind each fresh prompt and model-open schema to the selected model.
  Preserve native canonical result references and model identity. Reject
  conflicts and foreign or incomplete context/revision artifacts before commit.
- Preserve lawful PyPSA descendants through a bounded, authority-verified
  parent chain anchored to the selected base revision. Retain typed handoffs.
  Validate arguments after trusted handoff injection; errors retain binding ID.
- Project normal pandapower topology from the prepared gridctl context.
  Resolve branch focus from admitted endpoint evidence and verified assets.
- Associate evidence through verified artifact links. Keep repeated flow,
  rank and query references valid. Preserve N-1 aggregate scenario evidence
  and delayed evidence reads without assigning them by tool-call order.
- Restore exact rollback views and the clicked result's overlay. Deduplicate
  identical SSE/catch-up events and reject conflicts. Generate safe distinct
  page keys while keeping common existing keys.
- Keep model selectors inside the pane and show result actions on touch
  devices. Preserve desktop hover controls.

## Verification

The real-authority regression opens RTS, runs AC flow and ranking, runs a
second flow in the same context, switches to IEEE39 and resolves line 11,
then repeats endpoint resolution after snapshot reconstruction and checks
N-1 aggregate evidence. It checks diagrams, references, exact identity,
focus and retained history. The full exported
pandapower catalog passes snapshot roundtrip and page-key uniqueness checks.

Focused checks passed: App 205 tests/build, topology 59 plus prior views 9,
canonical/binding/page checks 99, JavaScript 45 plus syntax, and full Pyright.
The existing real PyPSA derived workflow was reproduced as a failure and then
passed. Independent final review approved with no open Critical or Important
source findings.

The final capstone-agent suite passed 461 tests, with 32 optional skips.
Real Thread sequence and result projection checks passed 7 tests. Delayed
evidence, repeated result references and N-1 aggregate association passed.

Real HTTP browser acceptance passed for RTS open and flow, IEEE39 endpoint
focus, refresh, earlier-result overlay selection, and a normal iPhone 13 tap.
Selectors fit both desktop and phone panes. Final-source screenshots were
visually checked. Only the isolated test servers and browser sessions were
stopped; temporary test credentials were removed.

The final flow-to-ranking browser case retained one result card, the same
authority result reference, and all 33 line overlay values after refresh.

Local rebuild, readiness and image equality passed. The real API lists
60 pandapower and 21 PyPSA models. Container exporters completed in 16.93 seconds.
The user Thread retains cursor 76 and its stored IEEE39 model. No history was
rewritten. The final API and both workers use image
`sha256:4ae0863461bee0e41eea63ce7ab75402c6f8d93b72e57c7d64745070d1821606`.
Readiness passed and the local App returned HTTP 200.
The stable-source `make check-release` passed with exit status 0. This includes
type checks, App build/tests, backend and Domain Pack suites, 39 E2E tests,
3 registered-worker tests, the 24/24 capability matrix, installed packages
and source installation checks. `make doctor`, changed-document links,
the relative `CLAUDE.md` symlink and `git diff --check` also passed.
Raw receipts: ignored `runs/capstone-thread-model-fix/` and `output/playwright/`.

## Boundaries

No live Provider call, cloud deployment, user-trial promotion or user-history
rewrite occurred. The isolated browser worker uses finite approved instructions
with real authority execution. Provider planning remains separately verified.
Existing incorrect answers stay in history. Cloud development still runs its
earlier verified source.

Pandapower Thread context/revision remains immutable. Revision-changing actions
require application activation; model tools cannot silently replace Thread
identity. Endpoint observations can focus a branch without a calculation card.

Tasks: [repair plan](../superpowers/plans/2026-10-05-thread-model-state-repair.md).
