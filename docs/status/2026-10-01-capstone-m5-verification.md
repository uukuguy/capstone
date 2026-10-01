# Capstone M5 Verification

Date: 2026-10-02 (Asia/Shanghai)

## Scope

M5 validates one-run Thread behavior across the registered pandapower and PyPSA
Authority families. The provider-free host is validation-only: it injects a
deterministic `PiPromptSession` below the production `PreparedKernelPiSessionFactory`.
The HTTP projection, Thread worker, Harness admission, Domain Pack executors,
Authority references, and event contracts are unchanged production paths.

## Provider-free live matrix

Command:

```text
make validate-thread-m5-provider-free
```

Results:

- `pandapower-static-analysis`: catalog passed; 3 professional Attempts passed;
  ordinary Attempt passed; current-run result/evidence and explicit tool source
  were observed.
- `pypsa-business-cases`: catalog passed; registered regional case passed with
  model and operations tools; ordinary Attempt passed; no pandapower-only labels
  were required.
- Reports are written under ignored `runs/capstone-m5/provider-free/`.
- Each provider-free row now persists `m5-provider-free-summary.json` beneath its supplied artifact root; stdout remains the same bounded JSON projection and stderr announces the exact report path.

## Lifecycle and recovery

`validation/test_m5_lifecycle.py` verifies selection activation, failed Attempt
retry with a new immutable Attempt ID and preserved Turn ID, and cursor-gap
`resync_required` handling through the typed HTTP client.

## Client parity and focused gates

- Capstone Thread/TUI focused tests: passed (including teardown recovery guard).
- App projection tests/build: passed in the M5 checkpoint.
- Provider-free matrix tests: passed in the grid-agent and pypsa-agent project
  environments (the opposite Authority row is skipped in each isolated env).
- `make doctor`: passed.
- `git diff --check`: passed.
- `make capstone-local-rebuild`: passed from the current source; API and worker
  are healthy and use image digest
  `sha256:774057c2dcae2c054e9f8e8f6080f42076d97a0904d08c7aab4d42c49ff03876`.
- The local App is reachable on port 5173 and the API readiness endpoint is
  healthy. PostgreSQL accepts connections inside the Compose container.
- `make test-e2e`: 39 passed. The provider-free scripted transport now accepts
  an explicit model answer for zero-step informational questions; admission
  continues to validate and annotate the answer without rewriting reader-facing
  text. The focused transport/admission regression and the full E2E suite pass.

## Release gate status

- `make validate`: passed, including protected paths, offline/scripted/application
  validation, and the `24/24 (100%)` capability matrix.
- `make check-release`: passed end to end, including Pyright (0 errors), all
  package suites, 39 E2E tests, 3 registered-worker tests, clean-wheel install
  smokes for grid and PyPSA, npm package self-tests, and source-setup checks.
- The protected `packages/grid-simulator` digest is now recorded by the separate
  baseline commit `61c183e`; the current expected tree is
  `6c4baa0fcafee336956f963e5d9af510d1b90dc4`.
- The clean-wheel closure fix `962e991` includes
  `capstone-model-capability-spi`, which is required by the application wheel.
- npm install reports three existing dependency audit warnings and four blocked
  install scripts; these are warnings from the isolated smoke environment and do
  not fail the release gate.
- Interactive browser/TUI screenshots remain an operator-stage check; both
  clients consume the same typed Thread snapshot/event page and their focused
  projection suites passed.

## Recovery baton

The provider-free zero-step offline answer contract is resolved. Rerun the
provider-free matrix after any Authority or Thread protocol change. Protected
source digests are current; future digest changes still require their owning
source revision and a separate baseline-only commit.
