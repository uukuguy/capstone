# Conversation intervention delivery boundary

Owner: capstone-app for readers and controls; capstone-agent/harness for admission.
Destination: dev. Design: [accepted contract](../specs/2026-11-17-conversation-intervention-design.md).
Status: combined execution reader implemented on feat/execution-details-20261117;
189 focused App checks, typecheck and143 scope checks pass. Canonical rebuild
and saved-record browser acceptance on5174 pass. Durable intervention remains unimplemented.
Design branch: docs/conversation-intervention-20261117, based on dev 4e81c5f6.

## A. Combined execution reader

Implementation uses a React Portal to retain the existing assistant runtime and
process/answer components. The right reader owns live following; manual history
reading suspends following. Product/model proposals do not replace this selected tab.
Standalone entries retain their previous process/answer ordering.

- [ ] Extract a shared execution-detail rendering seam from
  `packages/capstone-app/src/CapstoneAssistantThread.tsx`, retaining `AttemptActivity`
  and full answer behavior. Keep existing standalone rendering supported.
- [ ] Add `执行详情` to `ThreadWorkAdapter.tsx` resource views, alongside products.
  Source selection uses Thread/Attempt identity. Mainline links select that identity.
- [ ] Preserve manual history selection, folds, scroll and tab state. New events
  indicate updates rather than replace the inspected source. Offer `回到当前`.
- [ ] Move full answers after process records in the same reader. Mainline uses
  neutral completion/status receipts; do not fabricate semantic summaries.
- [ ] Extend `CapstoneAssistantThread.test.tsx` and adapter tests for a completed
  attempt followed by a running attempt: opening the former must retain its answer
  and tool records after the latter updates. Check close/reopen and missing sources.
- [ ] Run focused App tests and typecheck; canonical local rebuild; inspect the
  existing browser tab with real historical/current records at desktop/narrow widths.

## B. Durable intervention

- [ ] Map command admission in `capstone_agent/thread_service.py`, native worker
  continuation and `capstone_agent/harness.py` before changing the public protocol.
  Record transaction ownership, lease fencing and actual tool-cancellation boundaries.
- [ ] Implement persisted ordered instructions with idempotent submission, explicit
  admission receipts, atomic withdrawal and stopped-queue preservation. Do not use
  a browser-only buffer or reinterpret polling as execution acknowledgement.
- [ ] Test admission versus withdrawal and stop, duplicate retries, worker restart,
  stale leases and an uncancellable in-flight operation before enabling UI submission.
- [ ] Integrate the divider status strip and independent send/stop. Show pending
  instructions inline; source-link admission and redirection to execution details.
- [ ] Real acceptance: submit while a tool runs, change the next action at a safe
  boundary, verify products and refresh recovery; ensure stop cannot trigger an
  automatic restart from queued instructions. Audit IME and keyboard behavior.

## C. Dependent Mission work

Mission naming and legacy Goal compatibility, intent-only creation, dynamic equipment
and organizational intervention depend on the single-Agent admission mechanism.
They are accepted design scope, not delivered by reader relocation. No requirement
to create multiple Agents merely to establish a Mission.

## Recovery and integration

Do not change cloud/demo or claim runtime acceptance for this design branch. Preserve
the real PR137 execution artifacts. Obtain per-run CI approval only after concrete
implementation and focused local acceptance. Integrate accepted changes through dev;
record source, verification and runtime identity separately. Current next action is A.
