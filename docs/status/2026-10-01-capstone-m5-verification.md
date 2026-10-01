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

## Environment blockers

- `make validate` remains blocked by the pre-existing protected-path baseline
  mismatch for `packages/grid-simulator`; the baseline was not changed.
- `make capstone-local-rebuild` could not complete because the local Docker/
  OrbStack socket became unavailable after one BuildKit EOF; no deployment pass
  is claimed.
- Interactive browser/TUI screenshots remain an operator-stage check; both
  clients consume the same typed Thread snapshot/event page and their focused
  projection suites passed.

## Recovery baton

The next M5 follow-up is to rerun the provider-free command after any Authority
or Thread protocol change, then repeat the Docker rebuild when the local runtime
is available. Do not update the protected-path baseline without its owning
source revision.
