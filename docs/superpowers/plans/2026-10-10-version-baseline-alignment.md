# Version baseline alignment implementation plan

**Goal:** Preserve current development, align main runtime with the current verified demo baseline, and manage later framework fixes and experimental features separately.

**Architecture:** Keep Git history and user work. Prepare a source restoration commit on an integration branch; runtime sources return to `ed2524f`, while branch governance and the isolated local-demo management entrypoint stay explicit. No cloud deployment.

**Constraints:** Preserve all existing data and dirty user documents. Never reset or force-push main. Keep API/workers on the same source/image. Do not mark failed manual answer acceptance as stable. Use [VERSION-CONTROL](../../status/VERSION-CONTROL.md) for all branch and release identities.

## Execution

- [x] Preserve main `ca062df` at `archive/dev-before-baseline-20261010`; retain `3e3bbfb` at `fix/framework-answer-chain`. Save the dirty document diff and hashes in ignored operator storage. Reapply pre-incident `e9aca89` onto the aligned foundation at `feat/pi-skills-integration`, so the experimental changes are actually mergeable.
- [x] Create `integration/demo-baseline` in `.worktrees/demo-baseline`. Restore runtime sources and locks from `ed2524f`; preserve documentation, agent rules and separately scoped local-demo deployment management. Remove the experimental resource installation Make target from baseline tooling.
- [x] Check runtime tree equivalence with the demo source, except documented management and five-file minimum contract guards. Run setup, managed Pi installation and doctor before runtime tests.
- [x] Run focused deployment checks and full offline, integration and package/source gates. Resolve 13 inherited type errors on `fix/baseline-contracts`; no authentication state is copied.
- [x] Commit restoration, fast-forward main to the verified runtime basis `2540bdc`, and preserve dirty documents. Confirm original user document hashes before policy annotations. Shared ignore-rule repair `a076b04` also returns to main and the affected experimental branch.
- [x] Rebuild main with `make capstone-local-rebuild`; rebuild local-demo from the aligned clean checkout. Preserve databases, object storage and ignored runtime state. Stop only the unused experimental service after confirming zero unresolved receipts; retain its volumes.
- [x] Verify both actual local entrypoints: each passes three registered cases/nine turns, reports and evidence replay. Six roles have matching contract/source/installed artifact identities. Retained dev510/demo2 Thread snapshots/history and all prior event digests/volumes pass. Record source, images and scope in the [verification report](../../reviews/2026-10-10-version-baseline-alignment.md). No cloud release, acceptance tag or paid question replay occurs.

Feature work resumes from preserved branches only after baseline source and local alignment are recorded. Baseline two must pass formal user-answer acceptance before demo promotion.
