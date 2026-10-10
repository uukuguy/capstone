# Version baseline alignment implementation plan

**Goal:** Preserve current development, align main runtime with the current verified demo baseline, and manage later framework fixes and experimental features separately.

**Architecture:** Keep Git history and user work. Prepare a source restoration commit on an integration branch; runtime sources return to `ed2524f`, while branch governance and the isolated local-demo management entrypoint stay explicit. No cloud deployment.

**Constraints:** Preserve all existing data and dirty user documents. Never reset or force-push main. Keep API/workers on the same source/image. Do not mark failed manual answer acceptance as stable. Use [VERSION-CONTROL](../../status/VERSION-CONTROL.md) for all branch and release identities.

## Execution

- [ ] Preserve main `ca062df` at `feat/pi-skills-integration`; preserve `3e3bbfb` at `fix/framework-answer-chain`. Save the current dirty document diff and file hashes in ignored operator storage.
- [ ] Create `integration/demo-baseline` in `.worktrees/demo-baseline`. Restore runtime sources and locks from `ed2524f`; preserve documentation, agent rules and separately scoped local-demo deployment management. Remove the experimental resource installation Make target from baseline tooling.
- [ ] Check runtime tree equivalence with the demo source, except documented local deployment management. Run setup, managed Pi installation and doctor in the isolated checkout before runtime tests.
- [ ] Run focused local deployment checks and required offline integration gates. Inspect failures; resolve setup failures without copying authentication state.
- [ ] Commit the baseline restoration, fast-forward main to the prepared commit while retaining dirty documents. Verify preserved document hashes and the source tree.
- [ ] Rebuild main with `make capstone-local-rebuild`; rebuild isolated local-demo from the aligned clean integration checkout using `CAPSTONE_DEMO_SOURCE_DIR`. Preserve existing databases, object storage and ignored runtime state.
- [ ] Verify both real local entrypoints, role identity and registered cases/report/replay without paid Provider calls. Record exact source/image, ports and acceptance limits in VERSION-CONTROL and a verification report. No cloud tag or stable product acceptance claim without corresponding checks.

Feature work resumes from preserved branches only after baseline source and local alignment are recorded. Baseline two must pass formal user-answer acceptance before demo promotion.
