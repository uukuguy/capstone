# Framework answer correction and local demo verification

Status: local deployment and integration checks pass. No new cloud
promotion. The user requires stopping after local demo verification to discuss
parallel development lanes.

## Verified causes and correction

GBnetwork completed all 28 tools. Its optional result projection retained the
whole diagram's internal target IDs, producing 97,559 bytes against a 64 KiB
limit. Generic ValueError recovery reclassified successful observations and
calculations as unknown failures. Registered local GBnetwork replay reproduces
the old error. Full graph validation followed by target compaction produces
41,182 bytes and preserves the valid answer with zero false blockers.

Reference rejection has a dedicated exception. Optional presentation errors
preserve admitted text and Authority references. The complete terminal event
budget can omit optional cards; required answer/evidence persistence failures
remain fatal. Rejected model conclusions never reappear in a fallback answer.

RPC chooses the final assistant message, excluding pre-tool narration. The
application renders admitted, typed Domain Pack facts into a formal partial
answer and displays it before distinct blockers. Domain Packs retain units,
limits, scenario meaning and scope. The renderer does not infer completion,
coverage or a risk ranking. Audit diagnostics remain intact.

The actual saved substitute results replay as two projections of 32 and 14
scenarios. The line7 replay reports line11 at 103.329% against its model limit
100%, plus the recorded voltage violation. Terminal messages fit their budget.
These are offline replays of the user's admitted results, not new Provider runs.

## Source and local separation

Main correction: `0287c86`. Portable demo correction: `3e3bbfb`, based on the
prior demo repair. It excludes newer main workspace and input features.

Existing local development remains at App 5173 / API 8767. New demo uses Compose
project `capstone-demo-local`, App 15173 / API 18767, separate images, PostgreSQL
and object-store volumes, private bucket and operator/storage credentials.
Its protected backend reuses the existing Provider credential only under the
permitted function-validation exception. Agent checks make zero Provider calls.
No user data or authentication state is copied into the demo checkout.

Cloud demo remains at verified rollback `ed2524f`, recorded in the
[release and rollback report](2026-10-10-demo-n1-release.md).

## Checks and limits

- Main grid suite: 929 passed, 3 skipped. Main Capstone suite: 1128 passed,
  57 skipped. Main App: 388 passed. Types and doctor pass.
- Portable focused admission/Harness/runtime suite: 103 passed. Types pass.
- New deployment-entrypoint checks verify source identity, project/port
  isolation, protected credentials, retained configuration and dirty-source
  rejection.
- Saved N−1 and line7 result replay and registered GBnetwork calculation make
  zero Provider calls.
- Remaining main test targets pass after the initial finalization and budget
  regressions were corrected. Main E2E and offline validation pass. Both main
  and portable source types pass.
- Portable Capstone: 602 passed, 45 skipped; Kernel: 568 passed; Domain Packages:
  113 passed; App: 351 passed; compatibility E2E: 39 passed; registered-worker
  E2E: 3 passed. Portable offline/scripted validation and capability matrix pass.
- Final main rebuild passes. Local demo API and both workers share image
  `sha256:c7db2c33df899449f94fa65f780b06fbaec30ee51b10362cd625a20227cef9f9`.
  Eight changed Python source files match the clean candidate in all roles.
- Three local registered cases pass nine turns, reports and evidence replay
  through the demo App proxy. Preparation and LAN readiness pass. Actual desktop
  and 390-pixel mobile pages show clean source `3e3bbfb` without mobile overflow.
- New entrypoint also rejects a reachable App from another source. Required
  deployment checks pass; a Vite health check was corrected to use `/` rather
  than the hosted static App's `/health` route. A LAN probe passed with direct
  routing after an inherited network proxy caused the first timeout.
- Independent reviewer launch failed because the configured agent model is
  unavailable. Manual review and executed tests are recorded; no independent
  review acceptance is claimed.

Ignored receipts and logs are under `runs/demo-n1-debug/`. The repair does not add
generator-outage capability, certify a global severity ranking, change sleep
policy, or define the future development-lane workflow.

Local demo: `http://192.168.2.5:15173/` or `http://127.0.0.1:15173/`.
Acceptance is Provider-free. Live model answer quality remains for user trial;
no paid question was repeated automatically. Implementation stops here as
requested, before the parallel-lane discussion.
