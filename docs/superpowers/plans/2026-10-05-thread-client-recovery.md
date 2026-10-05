# Thread client recovery implementation plan

**Goal:** Preserve drafts and exact command identity on reconnect, and verify
Context-bound rollback views before cloud-dev acceptance.

**Architecture:** The App retains its Composer during same-Thread recovery.
ThreadProjectionStore reconciles original commands through the existing server
idempotency ledger. Topology stays a typed authority projection.

**Tech stack:** TypeScript, React, assistant-ui, Vitest, Python contract tests,
Docker Compose and Railway cloud-dev.

## Constraints

- Preserve unrelated edits and user runtime data.
- Use the exact source for local and cloud verification.
- No Provider call without separate approval.
- Demo promotion requires completed cloud-dev verification and manual acceptance.

## Task 1: Reproduce and repair send recovery

Files: `packages/capstone-app/src/ThreadFixtureApp.tsx`,
`CapstoneAssistantThread.tsx`, `threadProjectionStore.ts` and their test files.

- [x] Add regressions for lost receipts, same-key recovery, intact reconnect drafts,
  accepted receipt plus failed catch-up, and a changed draft while checking results.
- [x] Run `npm test --prefix packages/capstone-app -- --run` with focused files;
  confirm the tests fail for the intended recovery defects.
- [x] Keep same-Thread snapshots and mounted Composer during reconnect; expose
  unresolved receipt recovery with the original command and block fresh sends.
- [x] Clear only the matching accepted draft; preserve rejection and changed drafts.
- [x] Run focused tests, all App tests, and `npm run build --prefix packages/capstone-app`.

## Task 2: Verify rollback and integration

Files: `packages/capstone-app/src/threadProjectionStore.test.ts` and
`threadProjectionStore.ts` only if a defect is reproduced.

- [x] Extend switch/reopen rollback tests with a new Context's own topology.
- [x] Verify live and reload views restore the exact old diagram and layer.
- [x] Fix any reproduced defect and run all App tests. Existing rollback code passed.
- [x] Run relevant server idempotency tests, offline gates and
  `make capstone-local-rebuild`; inspect fresh browser recovery and topology.
- [x] Review the final diff, record results and commit only task-owned paths.

## Task 3: Cloud-dev acceptance

- [x] Stage a clean source archive and preserve the current cloud-dev identities.
- [x] Deploy both workers, API and App to cloud-dev only, with bounded scripted
  validation where needed; never touch demo or user data.
- [x] Verify health, model families, registered cases, reports, evidence replay,
  browser recovery, and equal backend source identity.
- [x] Diagnose the earlier PyPSA concurrent interruption with bounded scripted
  acceptance; record a result or an explicit unresolved limit.
- [x] Restore normal runtime mode, verify health, and give the user cloud-dev
  receipts and the exact candidate revision for manual acceptance.
- [ ] Wait for manual acceptance before demo promotion.

## Task 4: Close the reproduced hosted lease renewal gap

Normal-mode cloud acceptance reproduced the historical PyPSA interruption.
The blocking worker startup sits outside renewal; ready resets the timer and
can schedule the first renewal after the original lease expires. Evidence and
failed session IDs are preserved under `runs/thread-client-recovery/`.

Files: `packages/capstone-agent/src/capstone_agent/host_worker.py` and
`packages/capstone-agent/tests/test_host_worker.py`.

- [x] Add regressions for renewal during blocked startup and evidence reads,
  plus lost-lease fencing and clean renewal shutdown; establish the failures.
- [x] Keep bounded renewal independent of blocking session work, from the
  acquired claim through completion; preserve token fencing and report admission.
- [x] Run focused host/session tests, relevant isolated PostgreSQL checks,
  local rebuild and integration/release gates for the new backend source.
- [x] Commit the repair; preserve rejected 6b8eba8 receipts and stage a clean
  new candidate. Repeat cloud-dev acceptance and normal-mode checks.
- [x] Record the final candidate and request manual acceptance before demo.

Final candidate: `a1f028de4da1951599029b1cb7388e15db449ce8`. Full local release
checks, isolated PostgreSQL regressions and cloud-dev M11/browser/concurrent/
normal acceptance pass. See the
[verification record](../../reviews/2026-10-06-thread-client-recovery-and-cloud-dev-verification.md).
Demo remains unchanged pending the user's manual cloud-dev acceptance.

## Task 5: Verify shared Harness configuration in the local App

The user's normal private Thread failed because cloud-dev workers lack their
selected Provider credential. Configuration failures must retain the prepared
model Context and give a safe repair message. The existing M6 design keeps
Harness ownership inside `capstone-agent` before any independent package split.
The user requires local App verification before further cloud deployment.

- [x] Add failing runtime/UI regressions for configuration classification.
- [x] Centralize Provider resolution and safe configuration translation in
  `capstone_agent.runtime`; both historical hosted adapters delegate.
- [x] Add package guards against direct Provider resolution in those adapters.
- [x] Review and commit the shared Harness adjustment; rebuild the local entrypoint.
- [x] Run full offline release checks and verify both model families in the local
  App, including safe missing-configuration behavior and retained model Context.
- [x] Record local results for user review before cloud-dev deployment.
- [x] Resume cloud-dev validation only after the local-first gate is satisfied;
  dedicated stage credentials and real Provider authorization remain separate.
- [ ] Configure dedicated cloud-dev Provider credentials and complete separately
  authorized real Provider smoke checks before ordinary conversation acceptance.
- [ ] Promote to demo only after cloud-dev validation and manual acceptance.

Local source `188abe3` and focused App evidence are recorded in the
[Harness local verification](../../reviews/2026-10-06-harness-provider-configuration-local-verification.md).
The user subsequently authorized cloud-dev deployment. All four services run
that exact source; Provider-free checks pass. See the
[Harness cloud-dev verification](../../reviews/2026-10-06-harness-cloud-dev-verification.md).
Both worker Provider credentials remain absent, so manual acceptance is pending.
