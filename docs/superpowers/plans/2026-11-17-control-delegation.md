# Stage B — Durable Control delegation

Owner: capstone-control; consumers: capstone-agent and capstone-app.
Branch: feat/control-delegation-20261117. Destination: dev.
Basis: approved [Control design](../specs/2026-11-16-capstone-control-design.md),
sections4,5 and stageB. StageA merged through PR125 at4f511d46; exact local
closeout receipt is in root ignored runs/agent-goal-acceptance-20261116/.

## Outcome and implementation choices

One durable Goal organizes several ordered Tasks. Each Task delegates to an
autonomous Agent through a versioned public contract. Tasks can use single-shot
or bounded goal execution. A later Task can run in a fresh Thread and consume
explicit immutable product references from its accepted predecessor. The Goal
records execution delivery, Task verification and user acceptance separately.

Use a separately owned Python package, packages/capstone-control, assembled by
the application in the existing backend. Its core does not import Agent ledger
internals. A host-owned adapter calls public Thread create/command/read/product
operations. Control stores its own PostgreSQL records and durable operation
intents. No second Agent continuation loop: Control dispatches one delegation;
Agent owns all Attempts until delivery or an explicit control request.

Alternatives considered: placing Control in ThreadService would mix ownership;
an independent network service now would add deployment complexity without
improving the contract. A package with a public port preserves later separation.
Public task-board claiming and timer/event inbox delivery remain stagesC/D.

## Required contracts

- capstone-control-goal/1: workspace, stable goal_id, revision, objective,
  acceptance criteria, finite total delegation budget and deadline, ordered
  Tasks, status and user-acceptance record. Objective edits preserve history.
- Task: task_id/revision, objective, delivery requirements, predecessor IDs,
  explicit agent_id, execution mode and bounded budget. Dependencies release
  only after verified delivery. A failed or uncertain delegation never silently
  retries. Manual re-delegation consumes a new generation and budget.
- capstone-agent-delegation/1: operation_id, exact Goal/Task revisions,
  generation, agent_id, objective, context references, permission scope and
  budget. Binding includes thread_id/work_id. No text-based identity matching.
- Observe/Deliver bind the exact execution identity and immutable products;
  sequenced progress is observable before completion. Completion without a
  persisted answer or required products fails verification.
- Pause/Cancel/Steer are durable intents with idempotent operation IDs and
  expected revisions. Cancel first prevents new dispatch, then reconciles Agent
  acknowledgement. Active old generations cannot deliver into revised Tasks.
- Accept names exact Goal revision and product versions. Agent completion is
  never user acceptance. Only the authorized application user can accept.

All requests reject unknown fields, booleans as integers, invalid deadlines,
cross-workspace references, stale revisions and idempotency-key content conflicts.
An operation replay returns its original receipt. Persist dispatch intent before
calling Agent; retry the same operation after process loss. Agent adapter must
provide deterministic creation/admission identity so a crash cannot duplicate a
Thread, Work or execution. No transaction lock spans model or network execution.
Bounded context contains only task instructions, accepted summaries, source
identities and resource references. No full-chat/file copying or Authority claim
promotion. Validate access again at delegation and resource admission.

Implementation precision: Goal.revision is the CAS/storage version, including
observations. Goal.objective_revision is the semantic version bound by
Delegation.goal_revision; Task.revision binds the phase contract. Optional
Task.required_products lists explicit plain file names. Host byte/hash checks
may release these declared products; prose requirements are not interpreted by
keyword code. Tasks without this deterministic policy await explicit phase
verification. Final semantic acceptance remains a distinct user action naming
the exact saved product versions, with the application actor recorded.

## Unit1 — Control domain and transactional persistence

Create capstone-control package, contracts.py, service.py, store.py and tests.
Start with failing state/contract tests. Implement Goal/Task lifecycle,
revision-bound operations, idempotency receipts, budget reservation and ordered
dependency release. Add memory and PostgreSQL stores with equivalent transaction
semantics and workspace isolation. Tests cover stale edits, replay/conflicts,
concurrent dispatch selection, deadline/budget, late delivery and restart.
Keep PostgreSQL schema initialization idempotent and additive.

## Unit2 — Public Agent delegation adapter and durable reconciliation

Add a public idempotent Agent delegation entry and observation projection, with
host-owned binding checks. Use normal create/command admission and saved-product
access paths; do not write private Thread rows from Control. Implement adapter
port and maintenance drain. Fault-injection tests cover crashes before/after
Agent admission and before binding persistence, duplicate observations, Agent
waiting/failure/unknown outcome, cancellation racing admission, and revised Goals.
Add two-stage tests that prove a new Thread reads the original resource bytes.
Worker maintenance runs with the browser closed; progress remains bounded.

## Unit3 — Application assembly and existing workspace interaction

Add application-scoped /api/v1/control routes and workspace authorization.
Expose Goal creation, status, ordered stages, controls, exact delivery and user
acceptance through the accepted enterprise workspace, reusing existing composer,
conversation, product and source viewers. Do not create a second chat UI.
Goal/Task selection opens its bound existing Thread; acceptance identifies the
actual immutable products. Preserve ordinary standalone /goal behavior.
Test refresh, conflicts, pending drafts, old snapshots and cross-workspace denial.
Update dependency/build allowlists and add a focused macOS development gate.

## Unit4 — Real acceptance and dev integration

Use real model/tool execution for a two-stage synthetic task. Stage1 saves a
random-marker draft without leaking its bytes to chat; stage2 runs in a new
Thread, reads the admitted original reference and saves a report with matching
hash/marker. Verify Control delivery, Task verification and explicit user
acceptance remain distinct. Exercise active cancellation/revision, operation
replay, API/worker restart between stages and budget stop. Retain failed trials.
Rebuild through make capstone-local-rebuild; inspect existing Vivaldi tab and
screenshots against the accepted design. Run focused local and authorized macOS
CI, merge via dev PR, rebuild actual dev and verify its real entry. Preserve
data and other deployments. Update canonical worklist/register/overview and
journal at coherent boundaries. Final self-merge receipts stay in ignored runs.

## Completion evidence

StageB is complete only with package/contract boundary tests, PostgreSQL restart
and race evidence, two real fresh-Thread stages with original-byte downloads,
observed progress, confirmed revocation, version/idempotency rejection, bounded
budgets, exact product acceptance, browser refresh, focused CI and actualdev
integration evidence. A working state machine alone is not stage acceptance.
