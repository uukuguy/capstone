# Live Session Checkpoint

> Updated: 2026-10-02 22:30 CST. **M5 provider-free Thread matrix, lifecycle/recovery checks, and independent M1–M5 review are complete; Docker/protected-path environment gates remain open.**

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

- Commits: `a4acef7`, `eb53c11`, `b42dc60`, `0b847b8`, `786dd51`, `fc75f7d`, `40949cd`, `7edc905`, `7bece3c`, `9a505f9`, `2d80311`, `e74a1e2`, `b3edcef`, `ab8f207`, `3ef143d`, `a20b3b1`, `a4f8546`, `bc67286`, `f6e910e`, `caa3c88`, `d80a0f1`, `d7d2f07`, `f36119b`, `0541c9b`, `7ea5177` (typed adapters, hard-gated matrix, production HTTP client, recovery-safe reference TUI, shared hosted roots/selector, schema and Pyright gate fixes, and interrupted-state UI protection).
- Focused M5 checks: 43 Capstone/validation tests passed; PyPSA Thread capability tests 5 passed; changed-source pyright and ruff passed; `make doctor` passed; an earlier rebuild produced a healthy API image, but the latest rebuild attempt is blocked by the unavailable Docker daemon. Real HTTP smoke verified a typed Thread catalog with the registered IEEE-39 model.
- `make validate-thread-m5` was run without M5 credentials and wrote an explicit skipped report under ignored `runs/capstone-m5/`, then exited `2` as a setup failure. Set `CAPSTONE_M5_ALLOW_SKIP=1` only for report-only work. No provider command was submitted.
- Both registered families now expose Capstone-owned hosted API/worker entrypoints. `CAPSTONE_HOSTED_APPLICATION=pandapower|pypsa` selects the matching adapter, while each API/Worker pair must remain in one isolated application stage. Validation-only `ProviderFreeThreadHost` now drives both families through the real HTTP projection, Thread worker, Harness admission, Domain Pack executors, and Authority references.
- Independent M1–M5 review is recorded at `docs/reviews/2026-10-02-capstone-m1-m5-independent-code-review.md`; its two Important and two Minor findings were fixed in `497338d` and the remediation is documented. Full `make test` previously passed across the listed Python, Node, App, PyPSA, boundary, and verification targets. `make doctor`, `make check-types-validation`, and `git diff --check` pass. `make validate-thread-m5` remains report-only without credentials; `make validate` is still blocked by the pre-existing protected `packages/grid-simulator` baseline mismatch, and `make capstone-local-rebuild` is blocked by the unavailable Docker daemon.
- `validation/run_m5_provider_free.py` and `make validate-thread-m5-provider-free` pass the pandapower and PyPSA rows in their isolated project environments. `validation/test_m5_lifecycle.py` passes selection activation, retry lineage, and cursor-gap resync checks. The current Python Textual TUI is frozen as a protocol/reference client; it remains outside the provider-free matrix's visual target.

## Next action: environment-gated release verification

1. Run `make validate-thread-m5-provider-free` after any Thread/Authority change; reports remain under ignored `runs/capstone-m5/provider-free/`.
2. Repeat `make capstone-local-rebuild` when the Docker/OrbStack socket is available; do not claim a deployment pass from an old image.
3. Resolve the pre-existing `packages/grid-simulator` protected-path baseline mismatch through its owning source revision; do not edit the baseline as part of M5.
4. Keep future answer-display modes, structured ResultProjection UI, and feedback persistence deferred until the main Thread protocol gates remain stable.
5. Require an independent code review before declaring every future M stage complete.

## Recovery constraints

- Do not connect Web/TUI directly to Pi, DSH, Domain Packs, or Authority internals; all surfaces use typed Thread snapshots/event pages and `CommandEnvelope`.
- Do not reintroduce `grid-agent.hosted` or `pypsa-agent` as application roots.
- Do not invent model revisions, topology, results, evidence, tool output, or PyPSA model availability. A failed recovery is an immediate stop; never continue from a partial projection.
- Keep the unrelated user change to `.gitignore` untouched.
