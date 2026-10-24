# Live Session Checkpoint

Updated2026-10-25. Active closeout; no release or final handoff.

## Accepted source and remaining work

PR56 merged into dev as e72722fc after required macOS PR gate40119881315
passed in35m37s. Product head e8bfb5ae; merge tree is identical. Additional
release40119884971 was cancelled at the user's explicit direction. Do not restart
release suites for this development merge.

The main repository is now actual dev, clean at e72722fc. Canonical rebuild,
ready200, API/3worker imageb7d91d2822a4 and directed pin/Escape verification passed.
App PID21218 serves root packages/capstone-app; old Vite14792 was stopped.
Scoped cache cleanup passed. Evidence: root ignored
outputs/git-recovery-20261025/dev-entry-verification.json. No new Provider benchmark.

Control branch docs/workspace-integration-closeout is in .worktrees/dev-macos-ci.
It contains boundary discipline68841d4a, checkpointfa918f66, dev-only gate rule
e13ceb4a and is merging accepted dev. Resolve only the five control-doc conflicts;
all runtime changes come from dev and must remain byte-identical. Reconciled six
preserved design/control documents, cache10/20/50 and old accepted network policy.
Finish this docs-only PR, synchronize root dev, close merged branch refs.

## Preserved Git work

Root's109original dirty/untracked paths were inventoried and saved byte-for-byte
(109/109 checks) in recovery/root-before-dev-20261025: sourcebffe1b7c and
documents6c8f531e. This is unvalidated historical recovery, never a dev feature.
Original feat/work-attempt-binding c9e57152 and PR50 remain preserved; recovery branch
was pushed. Do not merge that unvalidated recovery snapshot into dev.
Research Model's one journal line was committed as275dc00f; no research code change.
Old dev edits remain in stashc306060c; do not reapply it wholesale.

Seven generated research/browser files were copied with hashes to ignored
outputs/git-recovery-20261025/generated-artifacts; originals remain in place.
Two exact local .git/info/exclude patterns cover their generated directories.
The withdrawn account/team proposal is being archived as documentation, not
implemented. Preserve its original while aligning the old implementation worktree.

## Deferred requirements

URL-named workspace partitioning and name display; same URL opens the same space;
different names isolate catalogs; no-thread URL is a normal home/selection entry.
Refined home/missing-session design and small sidebar refresh icon remain pending.
No login/team scheme or workspace selector is delivered by this branch.
Cloud/dev demo deployments and main release baseline remain unchanged.
