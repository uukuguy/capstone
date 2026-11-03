# Live Session Checkpoint

> Updated: 2026-11-03 11:02. **Session remains active — not a final handoff.**

User request: tag current state, merge main, then deploy latest to intranet.
Server SSH/sudo Docker is reachable. Preserve data and disable intranet management.

## Git and CI

- Actual dev HEADa8685cbf; task-owned control updates pending commit. Preserve unrelated untracked report.
- Tag milestone-managed-resources-20261103-771259a7 pushed and fixed at771259a7.
- PR87 release/managed-resources-20261103 → main, remote head263bad9f; NOT merged.
- Main remainsd4b59a0f; local reference was advanced to match accepted remote.
- CI41563425683 failed stale governance tests. CI41564504216 failed51 type errors.
- Third approved CI41566986778 cancelled after local reproduction of a frozen-clock legacy test hang.
- Fourth CI41570458423 failed macOS on obsolete dsv4 default expectation; remaining Linux cancellation requested. Later focused macOS dev-return CI remains approved.
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

Control snapshot and existing Vivaldi control tab inspected. Fourth
macOS/Linux release CI41570458423 failed. Async user question asks explicit
one-time main scoped-gate exception (161 resource/runtime checks,2–5min) versus
a new full dual-platform run. No answer yet; do not infer approval from delay.
If scoped exception is approved, use a milestone/ head so the existing focused
matrix runs on both platforms for main; do not claim full release acceptance.
The candidate a8685cbf adds the fixed host-runtime test to that milestone gate.
Merge only after the approved gate passes. Then
deploy exact accepted source to existing intranet project. Return main history
and control records to dev through a separate PR; its focused macOS CI has
explicit approval. No additional runs are authorized.

Linux amd64 candidate image preparation is active under .capstone-agent/main-intranet-25c71f85/.
Backend/app builds completed through ab-multi and existing proxy7897. Backend imageba233b82, Appa0b7d4f9.
Native Docker import hit layer depth. Rootfs/OCI exported; import_native.py preserves original runtime config in a single-layer image5abc0e56.
Native offline smoke22 capabilities/24 packages/15 commands passes. Image archive/checksums exec48306 is active.
OCI/rootfs/config/import receipts remain in the preparation directory. No intranet activation yet.
Server stages are /home/dmdba/capstone-intranet/releases/25c71f85/.
Transfer and SHA verification passed; Docker load/offline smoke active exec29105,
log /tmp/capstone-intranet-preload-25c71f85.log. Activation script is staged but
requires acceptance.json with confirmed main merge and accepted CI before running.
Do not replace containers before main integration. Existing intranet source70c42dab.

Correction: the full local rebuild target was incompletely covered earlier. It
now has135 consumer passes/3skip plus208 installer passes and4 failures in
test_user_local_offline.py. Those sources match existing main; root cause unknown.
Full release acceptance is NOT passed. See KNOWN-ISSUES and corrected report.
Do not activate intranet until main accepts this exact candidate.

## Constraints

- Local HTTP checks need NO_PROXY=127.0.0.1,localhost; proxy502 failures were environmental.
- No automatic summer-case replay or full model install-and-use acceptance claim.
- Keep tag fixed; never count cancelled/failed CI as passed.
- Preserve unrelated docs/reports/2026-11-01-summer-session-audit.md and all user data.
