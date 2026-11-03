# Live Session Checkpoint

> Updated: 2026-11-03 11:02. **Session remains active — not a final handoff.**

User request: tag current state, merge main, then deploy latest to intranet.
Server SSH/sudo Docker is reachable. Preserve data and disable intranet management.

## Git and CI

- Actual dev HEAD3c923666; task-owned control edits pending commit.
- Tag milestone-managed-resources-20261103-771259a7 pushed and fixed at771259a7.
- PR87 release/managed-resources-20261103 → main, remote head263bad9f; NOT merged.
- Main remainsd4b59a0f; local reference was advanced to match accepted remote.
- CI41563425683 failed stale governance tests. CI41564504216 failed51 type errors.
- Third approved CI41566986778 cancelled after local reproduction of a frozen-clock legacy test hang.
- Fourth CI NOT approved. Do not update PR head or start a run without new approval.
- Repairs9a3f75db,6c7722e8,263bad9f,ee625f38,3c923666.
- Scope/evidence: docs/reports/2026-11-03-main-intranet-release.md.

## Verification and runtime

- Backend3016 passed/191 skipped; App1502 passed; Kernel663 passed; E2E39 passed.
- Split release targets completed: simulator, packs, inventory, PyPSA, offline/scripted/application validation, package artifacts and source setup.
- Original aggregate was interrupted for diagnosis; do not call it a passing aggregate.
- Types, doctor, protected paths and whitespace passed.
- Canonical local rebuild and scoped cache maintenance completed.
- Local backendb0402ca2/nativecd364dbf, source identity9a1083e9; ready and App reachable.
- Intranet still70c42dab. No main merge or remote deployment occurred.
- Logs: runs/main-intranet-release-20261103/.

## Next action

Finish control snapshot and inspect existing Vivaldi control tab. Obtain fourth
macOS/Linux release CI approval, update PR87 and merge only on success. Then
deploy exact accepted source to existing intranet project. Return main history
and control records to dev through a separate PR; its focused macOS CI also
needs explicit approval. Deployment authorization does not approve CI.

## Constraints

- Local HTTP checks need NO_PROXY=127.0.0.1,localhost; proxy502 failures were environmental.
- No automatic summer-case replay or full model install-and-use acceptance claim.
- Keep tag fixed; never count cancelled/failed CI as passed.
- Preserve unrelated docs/reports/2026-11-01-summer-session-audit.md and all user data.
