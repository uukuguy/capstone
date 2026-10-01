# Capstone M4 Code Review

**Scope:** M4 Thread catalog, Web typed projection, compact model/Profile/trace controls, and immutable Attempt retry behavior (`fed5aec..15769e5`).

## Initial findings

The independent review found four issues: two Important and two Minor.

1. Model/Profile controls were incorrectly disabled during an active Attempt even though the Thread service stages these changes for the next Turn.
2. A partially populated catalog could omit the active snapshot model and leave the model selector without a valid active option.
3. Turning off the global trace projection left a dead per-answer “查看运行过程” action.
4. Interrupted Attempts lost the answer-level retry action because composer disabled state was coupled to retry availability.

## Fixes applied

- Model switching and Profile replacement remain enabled for a live current Thread while ordinary message submission stays blocked; pending state is shown by the typed snapshot.
- The active snapshot model is merged into catalog options when absent, using bounded snapshot metadata as fallback.
- The per-answer activity action is hidden when trace visibility is disabled.
- Retry is independently available for live, nonhistorical terminal Attempts, including interrupted Attempts, and submits the original `attempt_id` through `retry_new_attempt`.

## Verification

- Web regression tests after fixes: 33 focused tests passed; full App suite: 135 tests passed.
- TypeScript check and production build passed.
- Capstone Python suite: 248 passed, 27 skipped, 1 warning.
- Changed Python files: pyright 0 errors.
- `python tools/check_package_boundaries.py`: passed.
- `git diff --check`: passed.
- `make doctor`: passed.
- `make capstone-local-rebuild`: passed; API and worker healthy from current source, image digest `sha256:74b476202172b9837d5d7f7f79b238978b1dec5bc3ce351bcc4a5e8e4a997ecf`.

## Verdict

**PASS — no unresolved Critical or Important findings.**

M4 is ready to proceed to M5 unified real-client verification. The review did not change the ownership boundary: Web controls use typed Thread projections and `CommandEnvelope`; they do not connect directly to Pi, DSH, Domain Packs, or Authority internals.
