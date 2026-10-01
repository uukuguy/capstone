# Live Session Checkpoint

> Updated: 2026-10-02 02:15 CST. **Session remains active — M5 implementation is in progress; real-family/live-client acceptance is still open.**

## Current position

- `capstone-agent` remains the only application host. `grid-agent` and `pypsa-agent` are compatibility/migration adapters behind the Capstone boundary.
- M1–M3 are complete and reviewed. M4 is implemented and reviewed: typed Thread catalog, compact Web model/Profile controls, trace toggle, staged controls during active Attempts, and immutable Attempt retry.
- The legacy three-column App remains unchanged. The Thread route keeps the copied light two-column layout, original Capstone header, registered topology, assistant-ui surface, compact Composer, per-answer activity and duration projection.

## M4 evidence

- Plan: `docs/superpowers/plans/2026-10-01-capstone-m4-thread-controls-plan.md`
- Review: `docs/reviews/2026-10-01-capstone-m4-code-review.md`
- Commits: `fed5aec`, `a4262bf`, `7d50c11`, `c48c582`, `15769e5`
- App: 135 Vitest tests passed; TypeScript check and production build passed.
- Capstone: 248 tests passed, 27 skipped, 1 warning; changed Python pyright 0 errors.
- Boundary checker, `git diff --check`, and `make doctor` passed.
- `make capstone-local-rebuild` passed from current backend source; API and worker healthy with image digest `sha256:74b476202172b9837d5d7f7f79b238978b1dec5bc3ce351bcc4a5e8e4a997ecf`.

## M5 implementation checkpoint

- Commits: `a4acef7`, `eb53c11`, `b42dc60`, `0b847b8`, `786dd51`, `fc75f7d`, `40949cd`, `7edc905`, `7bece3c`, `9a505f9`, `2d80311`, `e74a1e2`, `b3edcef`, `ab8f207`, `3ef143d`, `a20b3b1` (typed adapters, hard-gated matrix, production HTTP client, recovery-safe reference TUI, shared catalog, and transport-independent client boundary).
- Focused M5 checks: 43 Capstone/validation tests passed; PyPSA Thread capability tests 5 passed; changed-source pyright and ruff passed; `make doctor` passed; current-source `make capstone-local-rebuild` passed with API image `sha256:a7d96ff6ff3e4f9f4c0be56ff9211105dba9e7e1e5ac1b410672d7ae96828222` and API `/health/ready` healthy. Real HTTP smoke verified a typed Thread catalog with the registered IEEE-39 model.
- `make validate-thread-m5` was run without M5 credentials and wrote an explicit skipped report under ignored `runs/capstone-m5/`, then exited `2` as a setup failure. Set `CAPSTONE_M5_ALLOW_SKIP=1` only for report-only work. No provider command was submitted.
- Both registered families now expose Capstone-owned hosted API/worker entrypoints. `CAPSTONE_HOSTED_APPLICATION=pandapower|pypsa` selects the matching adapter, while each API/Worker pair must remain in one isolated application stage. The remaining M5 blockers are provider-free live acceptance, lifecycle/recovery parity, and final independent review; a composition root alone is not a validation pass.
- Independent review of `bc67286`, `f6e910e`, `caa3c88`, and `d80a0f1` is approved with zero Critical/Important/Minor findings. `make test` currently has 842 passed and one checked-in schema drift failure; local rebuild retry is blocked by an unavailable Docker daemon.
- The current Python Textual TUI is frozen as a protocol/reference client. It is intentionally not the production visual/interaction target; after the M5 protocol gates, create a separate first-class `capstone` client interaction contract and framework evaluation before further UI work.

## Next action: M5 unified validation

1. Run real `pandapower-scripted-task` instructions through a new live Thread and verify catalog, Profile staging, automatic ordinary routing, professional admission, per-answer activity, duration, evidence/result cards, and retry.
2. Run a registered PyPSA model Thread through the same `CapstoneThreadClient` and verify family-specific model/Profile catalog behavior and one-model-one-page projection.
3. Exercise ordinary informational questions with the default ordinary policy and verify no simulator evidence is created for offline answers.
4. Exercise model switching, Profile selection, failure/cancel/retry, SSE reconnect/resync, and the Textual TUI session bridge against the same typed Thread protocol.
5. Exercise both hosted composition roots with provider-free Thread conformance, run `capstone-agent tui` against the HTTP/SSE roots, capture browser/TUI evidence, then run the complete gates before the next design milestone.

## Recovery constraints

- Do not connect Web/TUI directly to Pi, DSH, Domain Packs, or Authority internals; all surfaces use typed Thread snapshots/event pages and `CommandEnvelope`.
- Do not reintroduce `grid-agent.hosted` or `pypsa-agent` as application roots.
- Do not invent model revisions, topology, results, evidence, tool output, or PyPSA model availability. A failed recovery is an immediate stop; never continue from a partial projection.
- Keep the unrelated user change to `.gitignore` untouched.
