# M6 Task 3 Idempotency Fix Report

## Finding and change

`apply_application_transition` hashed only its command. Reusing the same
idempotency key and command with a changed application state or event document
therefore returned the original accepted receipt.

Added `application_transition_hash` as the shared neutral transition hash. It
canonically serializes the command, nullable opaque state, and ordered event
documents, and both the in-memory and PostgreSQL implementations use it. State
and event changes now produce `idempotency_conflict` before any write.

The in-memory and PostgreSQL regression checks cover a same-command retry with
changed state and changed events. Existing duplicate receipt and atomic-state
checks remain in place.

## Verification

- Focused transition and PostgreSQL tests: 3 passed, 6 skipped.
- Full `packages/capstone-agent/tests` suite: 294 passed, 28 skipped, 1 existing
  Starlette deprecation warning.
- Ruff on the two changed implementation modules and two test modules: passed.
- Pyright on those modules: 0 errors, 0 warnings.
- PostgreSQL coverage requires `CAPSTONE_TEST_DATABASE_URL`; it was not set in
  this environment, so the database tests were skipped.
- `git diff --check`: passed.

## Scope

The transition port remains bounded and application-opaque. No deployment,
Provider, authority, CLI output, or evidence behavior changed. Existing
`.gitignore` and `docs/status/JOURNAL.md` modifications were left untouched and
unstaged.
