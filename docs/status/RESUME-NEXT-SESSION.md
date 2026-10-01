# Live Session Checkpoint

> Updated: 2026-10-01 10:10 CST. **Session remains active — M5 implementation is in progress; real-family/live-client acceptance is still open.**

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

- Commits: `a4acef7` (typed catalog/HTTP/result/matrix adapters, Make target, TUI pending-control regression), `eb53c11` (MatrixSession type correction).
- Focused M5 checks: 12 passed; changed-source pyright 0 errors; App 135 tests and production build passed; `make doctor` passed; `make capstone-local-rebuild` passed with image `sha256:a6ab7113a1edc4d64763e34024d858c47cab8f3573106d06215048bb4be595da`.
- `make validate-thread-m5` was run without M5 credentials and wrote an explicit skipped report under ignored `runs/capstone-m5/`. No provider command was submitted.
- The current Compose hosted Thread is still assembled by the pandapower compatibility adapter and uses the Provider-backed runtime. PyPSA has a Thread assembly helper but no equivalent hosted API/worker entry. These are real M5 blockers, not acceptable skipped passes.

## Next action: M5 unified validation

1. Run real `pandapower-scripted-task` instructions through a new live Thread and verify catalog, Profile staging, automatic ordinary routing, professional admission, per-answer activity, duration, evidence/result cards, and retry.
2. Run a registered PyPSA model Thread through the same `CapstoneThreadClient` and verify family-specific model/Profile catalog behavior and one-model-one-page projection.
3. Exercise ordinary informational questions with the default ordinary policy and verify no simulator evidence is created for offline answers.
4. Exercise model switching, Profile selection, failure/cancel/retry, SSE reconnect/resync, and the Textual TUI against the same typed Thread protocol.
5. Add the provider-free hosted conformance entry points for both registered Authority families, wire a live TUI HTTP/SSE adapter, capture browser/TUI evidence, then run the complete gates before the next design milestone.

## Recovery constraints

- Do not connect Web/TUI directly to Pi, DSH, Domain Packs, or Authority internals; all surfaces use typed Thread snapshots/event pages and `CommandEnvelope`.
- Do not reintroduce `grid-agent.hosted` or `pypsa-agent` as application roots.
- Do not invent model revisions, topology, results, evidence, tool output, or PyPSA model availability. A failed recovery is an immediate stop; never continue from a partial projection.
- Keep the unrelated user change to `.gitignore` untouched.
