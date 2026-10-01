# M5 Code Review — Hosted Authority Roots and Interrupted Run State

## Scope

Reviewed commits `bc67286`, `f6e910e`, `caa3c88`, and `d80a0f1`.

Follow-up review also covered `7ea5177`, which guards the TUI sync-error
callback when Textual has already unloaded its screen.

## Verdict

**APPROVE for the reviewed code changes.**

- Critical: 0
- Important: 0
- Minor: 0

The PyPSA hosted API and worker delegate to the shared `capstone_agent.hosted`
process roots. `CAPSTONE_HOSTED_APPLICATION` selects `pandapower` or `pypsa`
for both roles, defaults to pandapower, and rejects unknown values. The selector
does not merge the two simulator environments or expose a second application
state machine. Interrupted run summaries now carry a red danger state, including
terminal-only event replays.

## Verification

- PyPSA package tests: 25 passed.
- Hosted entrypoint tests: 4 passed.
- App focused tests: 26 passed; App suite: 137 passed.
- TypeScript check, Pyright, Ruff, package boundary check, and `git diff --check`: passed.
- `CAPSTONE_M5_ALLOW_SKIP=1 make validate-thread-m5`: produced an explicit skipped
  report because protected live API credentials were absent.
- Follow-up TUI focused tests: 8 passed; Pyright, Ruff, and package-boundary checks passed.

## Remaining M5 gate

M5 remains **OPEN**. Provider-free live Thread matrices for both Authority
families, lifecycle/recovery parity, and browser/TUI live evidence have not run.
The complete `make test` gate now passes. `make validate` remains blocked by the
pre-existing protected `packages/grid-simulator` baseline mismatch. The latest
`make capstone-local-rebuild` could not complete because the local Docker daemon
was unavailable. No skipped result is counted as a live pass.

## Follow-up review of `7ea5177`

**APPROVE** — Critical: 0, Important: 0, Minor: 0.

The callback preserves the recovery freeze state and skips widget access after
screen teardown; the regression test covers the detached-screen boundary.
