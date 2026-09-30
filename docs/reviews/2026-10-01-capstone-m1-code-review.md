# Capstone M1 Code Review

## Scope

Reviewed the M1 application-root changes from `d6a2657` through `e7f977f`:
the `capstone_agent.hosted` process seam, grid and PyPSA compatibility shims,
boundary checker, tests, and status documents.

## Findings

### MEDIUM — hosted boundary check did not prove delegation

`tools/check_package_boundaries.py` checked for an imported module and a runner
name in source text. An adapter could therefore import the right runner without
calling it, call the wrong runner, or satisfy the check from a comment.

**Disposition:** fixed in the follow-up boundary checker change. The checker
now parses the adapter AST and requires `main()` to call the expected imported
runner with the application factory.

### LOW — hosted test fixture had type errors

The test fixture returned `object()` where the assembly seam expects a
`PiPromptSession`, and the intentional invalid-factory lambda was inferred as
returning `object`.

**Disposition:** fixed by adding a typed minimal session fixture and an explicit
invalid-factory cast at the negative test boundary.

## Verification

M1 had no formal review before this report. The review found no Critical or
High issue. Focused tests, package tests, boundary checks, `make doctor`, and
the local rebuild were already passing; the follow-up fixes add AST-negative
coverage and re-run the affected gates.

## Verdict

**Approved after follow-up fixes.** `capstone-agent` is the hosted application
root. `grid-agent` and `pypsa-agent` remain compatibility/domain adapters and
cannot bypass the root through an unverified hosted or worker entry point.
