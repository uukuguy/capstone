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

- [ ] Add regressions for lost receipts, same-key recovery, intact reconnect drafts,
  accepted receipt plus failed catch-up, and a changed draft while checking results.
- [ ] Run `npm test --prefix packages/capstone-app -- --run` with focused files;
  confirm the tests fail for the intended recovery defects.
- [ ] Keep same-Thread snapshots and mounted Composer during reconnect; expose
  unresolved receipt recovery with the original command and block fresh sends.
- [ ] Clear only the matching accepted draft; preserve rejection and changed drafts.
- [ ] Run focused tests, all App tests, and `npm run build --prefix packages/capstone-app`.

## Task 2: Verify rollback and integration

Files: `packages/capstone-app/src/threadProjectionStore.test.ts` and
`threadProjectionStore.ts` only if a defect is reproduced.

- [ ] Extend switch/reopen rollback tests with a new Context's own topology.
- [ ] Verify live and reload views restore the exact old diagram and layer.
- [ ] Fix any reproduced defect and run all App tests.
- [ ] Run relevant server idempotency tests, offline gates and
  `make capstone-local-rebuild`; inspect fresh browser recovery and topology.
- [ ] Review the final diff, record results and commit only task-owned paths.

## Task 3: Cloud-dev acceptance

- [ ] Stage a clean source archive and preserve the current cloud-dev identities.
- [ ] Deploy both workers, API and App to cloud-dev only, with bounded scripted
  validation where needed; never touch demo or user data.
- [ ] Verify health, model families, registered cases, reports, evidence replay,
  browser recovery, and equal backend source identity.
- [ ] Diagnose the earlier PyPSA concurrent interruption with bounded scripted
  acceptance; record a result or an explicit unresolved limit.
- [ ] Restore normal runtime mode, verify health, and give the user cloud-dev
  receipts and the exact candidate revision for manual acceptance.
- [ ] Wait for manual acceptance before demo promotion.
