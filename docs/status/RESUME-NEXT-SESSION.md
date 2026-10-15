# Live Session Checkpoint

> Updated: 2026-10-15. Active work; not a final handoff.

## Current instruction and scope

User requests fixing the remaining problems on `fix/user-local-network-view`,
then merging normally into `dev`. Active worktree is
`.worktrees/dev-trial-deployment`; pre-follow-up source anchor is5e3627a.
The two defects are later-turn PyPSA result projections and AC validation of a
saved dispatch. Plan: [PyPSA follow-up](../superpowers/plans/2026-10-15-pypsa-runtime-followup.md).

Do not repeat offline release suites. Run focused regressions and one targeted
original regional conversation with the already authorized DeepSeek OPENAI_*
configuration. Required dev PR Linux/macOS checks still apply. No bypass.

## Implementation owners and design

- offline_review_supported owns application preparation/session projection,
  PyPSA model binding and related tests. A neutral optional revision resolver
  validates every result's own authorized model lineage/revision. Each result
  is projected against its actual verified context, preserving Pack equality
  and existing host-only verified-context admission. No PyPSA imports enter
  the framework Kernel. Baseline catalog revision must remain unchanged.
- offline_provider owns Authority power_operations, its tests and the AC
  contract/guide scope. PyPSA1.3.0 reads generators_t.p_set; writing computed
  generators_t.p was overwritten. Apply saved schedules to input p_set.
  Verify actual non-slack outputs, third-snapshot backup increment and slack
  loss balance. Fail explicitly for unsupported scheduled Store/StorageUnit/
  Link/Process components instead of claiming to verify unsaved schedules.
- Root owns planning, control documents, candidate runtime, review, PR/merge
  and canonical dev checkout integration. Workers do not commit concurrently.

## Immutable delivery and graph

Current user package is sourcee2eaee2403cb6d780b3f7564da86e0d083890673,
root `runs/user-local-offline/capstone-delivery-e2eaee2`, three files.
Archive bytes1368607944; SHA256
9d7c3b215b9c45631bf3142aaad8f8066ba43831380b43b2ccf8146ee1eebfe7.
Single install/readiness and six AMD64 roles passed; instance29377 is stopped.
Runtime packages matched tested28020aa. Preserve the delivered artifact unchanged.
No new package was requested by the current fix-and-merge instruction.

7c19766 is withdrawn and not deliverable. Evidence is retained at root
`runs/user-local-offline/capstone-withdrawn-7c19766`; original files/hash remain.
Do not restore or distribute the old delivery directory.

The graph has12 important nodes. e2 is an independent visible delivery focus,
with README/archive/SHA/report links. Withdrawn7c and documentation606 belong
in history, not separate nodes. Update graph and canonical register at phase
boundaries; check both worktree and root entry points. Source/verification/
merge/deployment states must remain distinct.

## Prior verified evidence

- Graph scene/camera fixes61a418d:106 backend and109 App tests plus browser checks.
- Shared handoff fix28020aa:16 contracts/82 checks, independent review.
- Original three-turn AMD64 OPENAI candidate28020aa: baseline/growth dispatch
  optimal1300/1900 and both AC calls converged. Actual projection failure and
  AC schedule inconsistency remain evidence for the present regressions.
- Raw ignored evidence: `.capstone-agent/regional-handoff-candidate-live.json`
  and its sibling directory of records/snapshots/verified Authority documents.
  Candidate29375 is stopped with data retained. Operator checker interpreter
  error was separated from the successful first dispatch; never resend it.
- README1–9 actually ran on7c;10–12 were not run. Full generator N1 study/ranking
  remains unverified. Do not turn request completion into full business acceptance.

## Integration and data preservation

PR27 merged normally as37529efa2f0b0e10f641a65706b330b1d94255af after required CI.
origin/dev points there. Root dev HEAD remains1d0b280. Root has task-owned pending
control/tooling copies synchronized from the fix worktree; preserve them before
fast-forwarding. Preserve untracked reports/plans and append-only journal data.
Never overwrite unrelated work or delete/migrate root var data.

After focused fixes and review: freeze source, test one isolated regional candidate,
record actual results, create dev PR, pass required checks, merge, preserve pending
root copies, fast-forward dev, and use make capstone-local-rebuild for its real
entry point. API and both workers must share the tested source/image.

Existing19173 installation is user data and remains untouched. local-dev previously
runsb7e68dd; local-demo/cloud-demo remainfaa6af9, cloud-dev24d9a32. No cloud/demo
or Ubuntu VM validation/deployment is authorized by this task. Do not change them.
Keep credentials in environment/private ignored state; never log values or copy
ignored authentication state into a fresh worktree.
