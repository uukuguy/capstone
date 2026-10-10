# Coherent history browsing implementation plan

> Execute with subagent-driven-development and a final independent review.

**Goal:** Restore and browse complete short conversations without internal tool events forcing users into separate pages.

**Architecture:** The App owns bounded history restoration and reading position. Keep the existing public API, durable ledger, live command cursor and Authority evidence contracts. Use the existing pagination rather than enlarging API responses. This implements the user's accepted requirement to browse upward naturally while retaining the latest conversation and reading position.

**Tech stack:** TypeScript, React, assistant-ui, Vitest.

## Global constraints

- Source branch `fix/issue-1-history` starts at main `d70fc27` and later synchronizes the reviewed CI prerequisite before integration.
- No Provider requests, cloud changes, raw artifacts, user-data mutation or authentication copies.
- Preserve the current bounded retention: 1024 events and 8 MiB; history cursors remain validated. Do not preload unlimited pages.
- Historical reading never alters the live event cursor or simulator result admission.
- Preserve drafts, fold state, current model and reading position while loading earlier history. New live events cannot erase a loaded view.
- User-facing partial or loading failures retain already available conversation and a retry action.
- Real local-dev/local-demo rebuild and entry verification are required before claiming the repair is effective.

## Task: coherent restoration and continuous browsing

Owner: implementation worker owns `packages/capstone-app/src/threadProjectionStore.ts`, `CapstoneAssistantThread.tsx`, related focused tests and a small history helper if needed. Root owns governance and publication; reviewer owns independent review.

- [x] Reproduce the observed case with four questions, many tool events, and 128-event pages; verify the short conversation currently needs manual paging and may start mid-answer.
- [x] Add failing regressions for bounded initial restoration, page-boundary question/answer pairing, superseded loads, upstream history failure and unchanged live cursor.
- [x] Restore enough recent complete conversation for the existing display window, subject to current event/byte limits and bounded calls. Keep remaining history available on demand.
- [x] Replace manual older/newest view swapping with incremental upward loading within retained bounds. Preserve newer messages and viewport anchor; keep a keyboard-accessible load/retry control. A return-to-latest action moves reading position rather than discarding loaded conversation.
- [x] Cover drafts, fold overrides, focus, loading reentrancy, thread switches and bounds with meaningful tests. Update obsolete segmented-window assertions only where the user-facing requirement intentionally changes them.
- [x] Run focused tests, full App suite and build/type checks; self-review; record exact evidence and commit task-owned changes only.
- [ ] Independent task and whole-branch review; fix findings before PR. Then sync prerequisites and recheck before maintainer-confirmed integration.
- [ ] Rebuild and validate both real local environments after integration, preserving their separate state. Keep Issue open until its actual acceptance is complete; no cloud release is authorized here.
