# Shared execution foundation — Task 1 bridge baseline

Status: host execution seam and offline SDK checks implemented; production assembly,
persistent action permits and the new frontend/backend task loop remain pending.
Source: `62f443661a207c9a4222630bba1384e13dabdc3d` (subsequent control commits do not change this implementation).

## Implemented and checked

`guardToolExecution` wraps a host-owned tool provider at its execute boundary.
It observes arguments after SDK extension hooks, copies the admitted inputs, fixes
the tool name and execution method, and checks cancellation before/after admission.
Only an explicit accepted decision calls the provider. A safe host explanation is
returned as a tool error so the agent can repair the action or choose other work.
It creates no Authority result and defines no business policy or indicator.

The initial real SDK regression wrote the extension-mutated path without the guard.
After the wrapper was added, the rejected file was absent and the session continued.
Independent review found a mutable provider-method race; a second red/green test
confirmed the fix. The wrapper now captures the execution method at registration.

| Check | Result and scope |
| --- | --- |
| Real SDK bridge | 14 passed: final arguments, native read/bash/edit/write providers, extension tool context, rejection and continued response, stable argument/provider snapshots, abort, persisted reopen and steer |
| Existing protocol/research/worker/native-resource suites | 101 passed, 1 skipped; existing Thread identities, state transitions and worker lease behavior preserved |
| pi-grid-tools suite | 57 passed, including the provider-race regression |
| Earlier SDK probe | Passed; remains a seam probe, not production bridge acceptance |
| Independent review | Mutable-provider issue fixed; targeted follow-up passed with no new blockers |

The SDK tests script model output only. They use actual SDK sessions, extension
hooks, tool execution and temporary disk persistence. They make no external Provider
calls and read no host authentication. Temporary workspaces are removed.

## Existing entry and professional assets

- App: existing Thread entry at local-dev `http://127.0.0.1:5173/`.
- API: existing `/api/v1/threads`, Thread snapshot, events and commands;
  `thread_http.py` binds command/run/thread and idempotency identity.
- Worker: existing `thread_worker.py` claims and runs attempts; its lease and
  research tests remain the baseline. No parallel queue or ledger is introduced.
- Professional cases: reuse existing registered/scripted pandapower and PyPSA
  validation resources. Results/evidence still come through their authorities.
- Frontend: retain existing NetworkView, ResultExplorer and ResearchEvidence;
  new analysis/report and decision views do not replace these assets.

## Remaining boundary and human observation

The current `general-sdk.mjs` launcher still uses an in-memory session and ends after
one prompt. The new wrapper is an opt-in tool-provider seam, not yet connected to
the production inventory. Task 3 must assemble every allowed tool through it and
bind final contract checks, authorization, live lease/goal revision and persistent
permits/receipts. Tests prove the seam works; they do not prove inventory closure,
distributed recovery or user-visible continuous execution.

SDK abort does not imply rollback of an external effect. The test retains an actual
written receipt and reopens session history; it is not an exactly-once distributed
operation guarantee. Existing Python worker tests do not prove a new native
lease-to-permit protocol. That integration remains explicit work.

Task 1 reuses existing Python baseline suites instead of duplicating their fixtures
in a new `test_enterprise_baseline.py`. Task 2 owns identity/Profile integration and
the minimum frontend adaptation. Its first visible milestone must supply a runnable
entry, exact source, sample input, expected result/source display and reconnect check.
This bridge slice alone is not that milestone and does not enable the application
branches for dependent implementation. No new user package or cloud release is made.

## Local integration and running entry

`make check-integration` passed: E2E 39, registered workers 3, offline and scripted
validation, application instantiation and published capability coverage 24/24.
The capture-runtime checks use local scripted providers; no external billed Provider
was called. `make doctor` and documentation link/symlink checks passed.

Canonical local-dev rebuild passed at checkout 711f06a8. Its shipped source is
identical to implementation 62f44366. API and both workers share image
`sha256:ae5adedf87d2ee9b0898a7386b85f48d5136d973c3871c68d296e0fcb25c053b`.
All 1142 shipped files per role match; App reports 62f44366, dirty=false.
Readiness passed and the existing Thread entry loads in a real browser.
Receipt: `runs/shared-execution-baseline/local-identity.json` (ignored operator evidence).
App/workbench sources excluded by Docker packaging are not counted as backend files.
This is local baseline verification, not new enterprise UX acceptance.

## Accepted integration

PR #36 passed both Linux and macOS in CI38881419651 at exact head
`711f06a8d8351d59602776bc8d8dfaac1603f854`. It merged normally into dev
`d8fe6e2738639161525a66bce7a8f0a9588e2872`; the full merge tree equals the tested head.
Task 1 is accepted within the seam and baseline scope above. Task 2 is next;
Task 3 retains production tool assembly and continuous execution acceptance.
The merge does not change the recorded runtime source or any release deployment.
