# Shared Harness Provider configuration: local verification

## Scope and release gate

Backend source: `188abe3536722623c2e85d596195de6f60401a16`, following the
configuration error classification repair `5dc0cd4`. The user requires local
App verification before further cloud deployment. At local closeout, both
revisions remained local and cloud-dev ran `a1f028d` in normal mode. The user
then authorized deployment of `188abe3`; the subsequent results are in the
[cloud-dev verification record](2026-10-06-harness-cloud-dev-verification.md).
Demo is unchanged.

This closes one shared runtime ownership gap. It does not claim completion of
every remaining compatibility-package cleanup or real Provider acceptance.

## Architecture

The existing [M6 design](../superpowers/specs/2026-10-02-capstone-m6-harness-case-design.md)
section 2.2 keeps Harness inside `capstone-agent` until its public interfaces
and dependency direction stabilize. The independent `capstone-harness`
distribution is a later packaging decision.

`capstone_agent.runtime.resolve_harness_llm` now owns hosted Provider resolution,
application defaults, and safe configuration failure translation. Both
historical hosted adapters call that shared function. The pandapower adapter
also uses the shared environment loader instead of private legacy CLI helpers.
The adapters retain registered authority, Domain Pack Profile and session
assembly; domain state and calculations remain with their existing owners.

Package boundary checks reject direct Provider resolver imports in either
hosted adapter. Configuration failures become the neutral
`HarnessRuntimeConfigurationError`; the shared Thread worker publishes only
`runtime_configuration_invalid`, keeps the prepared model Context, and ends
the Attempt. Actual capability preparation errors retain their existing
rollback behavior. The App gives safe configuration repair guidance.

## Verification

The shared resolver regressions fail before extraction and pass afterward.
Both real family assembly suites pass. The ownership regressions fail before
the new guard, then all 68 boundary checker tests pass. Production type checks
report zero errors. `make doctor` and `git diff --check` pass. Diff review was
performed locally; no independent review result is claimed.
The App production build also passes.

`make capstone-local-rebuild` passes for the exact backend source. API and both
workers use the same image:
`sha256:67f702770383d65f93bb2c7728bd8b8e6649a4d3c41960c04178a9b6825599be`.
API readiness and the existing Vite App pass. Ignored receipts are under
`runs/thread-harness-local-verification/`.
`backend-identity.json` confirms the shared image. `backend-source-hashes.json`
matches all five runtime, Harness, worker and adapter source files against the
committed candidate. The actual Vite source response contains the repaired
configuration guidance.

- `local-missing-configuration.json`: both real hosted factories inside the
  rebuilt worker image publish the safe code and retain their Context. Each
  isolated subprocess uses a deliberately absent test credential and makes
  zero Provider requests. Protected local settings and user sessions remain
  intact.
- `registered-cases/legacy-7f89739eb16f.json`: fresh normal-mode pandapower and
  PyPSA registered cases complete all three turns, report retrieval and evidence
  reads. Public Provider mode is rejected. No Provider request is made.
- `local-private-catalog.json`: the actual private Thread API creates a fresh
  task-owned Thread and returns both registered families, with 81 models and
  no active Attempt. No instruction or Provider request is submitted.
- `pandapower-browser-summary.json` and `pypsa-browser-summary.json`: the actual
  local App source uses each real registered normal factory through a loopback
  host and isolated in-memory ledger. The user's model-list question gets the
  safe configuration failure. Retry creates a distinct Attempt in the same
  Context and preserves an unrelated Composer draft. Refresh restores both
  failures. These browser checks use no Provider, production ledger or existing
  user Thread.

Inspected screenshots:
`output/playwright/harness-local-pandapower-configuration.png` and
`output/playwright/harness-local-pypsa-retry-refresh.png`. The actual App at
`http://127.0.0.1:5173/old` also serves its registered cases and authority-backed
model preview. Its protected private API is covered separately above.

The PyPSA regional preview shows all six buses and seven branches. Both real
App screenshots are under `output/playwright/harness-local-real-app-*.png`.
The test-only loopback host, second Vite process and QA browser are closed.
Existing user App, Compose services, credentials and Threads are preserved.

The consistent final-source `make check-release` passes with exit code 0:
926 grid-agent checks, 178 simulator checks, 471 Capstone checks (34 optional
PostgreSQL skips), 256 App checks, 567 Kernel checks, and 105 pandapower Pack
checks. Grid E2E passes 39 and registered-worker E2E passes 3. The remaining
registered Packs, client, transport and workbench checks pass. Offline,
scripted and application validation, 24/24 capability coverage, clean artifact
installation and source setup all pass. The final log and receipt are
`full-release.log` and `full-release.json` in the ignored receipt directory.
Capture-runtime tests use mock callbacks; no real Provider request is made.
The earlier gate began before extraction and is not the final-source receipt.

## Remaining acceptance

After the local checks, the user authorized cloud-dev deployment. All four
services now run `188abe3` and Provider-free cloud checks pass, as recorded in
the [cloud-dev verification record](2026-10-06-harness-cloud-dev-verification.md).
Ordinary Provider planning has not been tested in this repair. Cloud-dev still needs
its dedicated protected Provider credential and separate authorization for
real Provider smoke calls. Full cloud-dev verification and human acceptance
must pass before any demo promotion.
