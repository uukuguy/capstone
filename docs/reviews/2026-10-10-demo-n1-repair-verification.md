# Demo N−1 outcome repair verification

Status: local repair and final local rebuild pass. Remote
deployment and acceptance have not occurred. No paid Provider request was made.

## Sources and incident evidence

- Existing demo: `ed2524f5774eb105178ba3f52d34ad36706b5cf8`.
- Main backend repair: `eeb00f1241f2c17a68c24cfaccfad5e5030f845a`.
- Portable demo repair: `2ea22668aa15ad8439cc210903aa4c9c677e203b`, branch
  `fix/demo-n1-outcome`. This branch starts at the existing demo and excludes
  newer local workspace, resource and input features.
- Incident: Thread `thr_2e32a4cb4ec67eaf2611`, Attempt
  `attempt_dadf4642048eef59`.

Actual event replay reproduces rejection of a derived context by the exact-base
identity gate. Model derivation completed. AC powerflow has a start receipt but
no completion receipt. No complete N−1 scan or full ranking is available. The
powerflow failure cause remains unknown. Missing output alone does not establish
insufficient data, a solver error or a program error.

## Verified behavior

- Authority verifies bounded derived lineage and engine identity. Foreign roots,
  wrong revisions, missing lineage and invalid artifacts remain rejected.
- A fixed private workspace scope constrains native and host tool invocations.
  A derived calculation does not change the Thread's current model implicitly.
- Independent admitted work can survive a later tool or answer failure. Retained
  text comes from the host. Rejected model prose and unsupported full rankings
  are not published.
- Stable typed causes distinguish input, calculation, capability, invocation,
  service, admission, storage and unknown errors. Transport deadlines establish
  a transport failure, not the missing calculation's outcome.
- Missing tool ends produce unknown receipts on normal completion, failure and
  user cancellation. Cancellation regression failed first, then passes with
  the full Harness/outcome focused suite: 39 tests on each baseline.
  Required storage failures remain fatal. Both ledger implementations validate
  terminal outcomes and admitted references.
- Verified derived results have conservative, explicit partial-scope coverage.
  They cannot establish an exhaustive study without an Authority coverage
  contract. Child results do not overlay a base-model card.
- The App restores partial outcomes and diagnostics. Legacy events remain
  readable. Desktop and mobile presentation checks use controlled fixtures,
  not a live Provider answer.

## Checks

- Main: doctor, types, App build, offline validation, extra release gates and
  E2E pass. E2E covers 39 compatibility tests and 3 registered-worker tests.
  Initial full grid run found a neutral-receipt capability-count regression;
  it was corrected. Final grid repetition passes 928 tests, with 3 skips.
  Capstone passes 1118 tests with 57 skips; App passes 387 tests.
- Portable demo: fresh setup, Pi installation, doctor, types, App build,
  offline validation and E2E pass. E2E covers the same 39 compatibility and
  3 registered-worker tests. Final grid repetition passes 928 tests.
  Capstone passes 592 tests with 45 skips; App passes 350 tests.
- Real hosted Thread derivation and scope tests pass. No Provider credential
  was required. Focused partial-outcome, receipt, lineage and storage tests pass
  on both baselines. App focused regressions pass 57 on main and 56 on demo.
- A portable full-suite run stopped because ignored PyPSA assets were absent.
  The six public pinned assets were copied individually from the verified local
  model library, then checksum-verified. Authentication state was not copied.
  Remaining gates and both `check-fast` runs pass. These full runs started from
  `5fdb024` and `08e8e98`. The final cancellation-only change is covered by the
  separate 39-test Harness/outcome suite and fresh type checks on both baselines.
- Canonical main `make capstone-local-rebuild` passes from backend repair
  `eeb00f1`. API and worker both use
  `sha256:32215bd4bff702e2e52089a91abdaa3be904d03d63707ad53aaf3be2cebdad08`.
  `/health/ready` returns ready. The local App is reachable on port 5173.
- Desktop 1280×900 and mobile 390×844 fixture inspections pass without
  horizontal overflow. The fixture supplies the flex container used by the App;
  it does not submit a command or claim real simulator evidence.
- Ignored receipts and logs: `runs/demo-n1-debug/` on main and `runs/` in the
  portable worktree. They contain no stored Provider credentials.

## Acceptance limits and next release action

The review agent could not launch because its configured model was unavailable.
Manual review and executable gates were used; independent review is not claimed.
The historical missing powerflow receipt cannot be reconstructed by this patch.
The repair has not been tested through an actual paid answer or deployed online.
No acceptance tag has been created.

After final local gates, the next release action is to validate the exact portable
demo repair in cloud-dev, then promote that same source to demo. Readiness, App
health, registered cases, reports, evidence replay and API/worker identity must
pass in each stage. Record separate immutable stage tags only after acceptance.
Existing user data remains in its stage. Provider validation needs separate
authorization. Sleep policy and release-lane redesign remain deferred.

User feedback about startup and mid-conversation recovery is recorded in
[known issues](../status/KNOWN-ISSUES.md). It is not a confirmed sleep diagnosis.
