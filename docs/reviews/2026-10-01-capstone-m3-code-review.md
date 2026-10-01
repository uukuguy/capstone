# Capstone M3 Code Review

## Scope

Reviewed the M3 TurnRouter, Harness admission integration, worker composition,
Application policy wiring, router input sanitization, and focused tests.

## Findings and fixes

### HIGH — fixed: explicit professional routing could be downgraded

An injected classifier was previously allowed to return `ordinary` for an
explicit `send_professional` command. The outer `DefaultTurnRouter` now owns
the policy and explicit command kinds always produce explicit plans.

### HIGH — fixed: professional limited answers could be committed

Professional plans now require a non-empty current-run evidence admission with
`authority_backed` mode. Limited, offline, or missing admissions fail with the
stable `capability_required` code.

### MEDIUM — fixed: router configuration and fallback were not auditable

`RouterConfig` records mode, model, and decision schema in every TurnPlan.
Jev modes remain optional and off by default; shadow routing is diagnostic and
cannot change the authoritative plan.

### MEDIUM — fixed: fallback visibility and custom policy wrapping

Bounded fallback events are public. Application-injected classifiers are always
wrapped by the outer policy router, so ordinary enablement and safe fallback
cannot be bypassed.

### LOW — fixed: context validation

TurnPlan and RoutingInput now validate allowed fields, JSON serialization, and
bounded context size before event persistence.

## Verification

- Focused Harness/worker/router/application tests: 33 passed.
- Full Capstone package suite: 243 passed, 27 skipped.
- Pyright on changed M3 sources: 0 errors.
- `python3.14 tools/check_package_boundaries.py`: passed.
- `make doctor`: passed.
- `git diff --check`: passed.
- `make capstone-local-rebuild`: passed; API/worker image rebuilt from current
  source and `/health/ready` returned `{"status":"ready"}`.

## Verdict

**APPROVE after fixes.** M3 keeps classification advisory, preserves the
Capstone application root, and leaves professional result/evidence admission
under the existing Harness/Domain Pack gate.
