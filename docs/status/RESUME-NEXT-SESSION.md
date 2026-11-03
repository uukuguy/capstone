# Live Session Checkpoint

> Updated: 2026-11-03 19:00. Active implementation checkpoint; not a completed release.

## Current task

User approved execution reliability and concurrency/queue design.
Product candidate b7dd440c on feat/execution-capacity-20261103 in
.worktrees/execution-capacity. Actual root dev/origin-dev f7d40163;
main0b68c607. No push, PR or CI was started. No new CI approval exists.
An async question for one macOS focused CI (3–6min) is pending; merge only after
the approved gate and final page verification. Elapsed time does not grant approval.

Implementation: exact observation read-budget recovery; configurable native
slots (library default1, local2); immediately terminal unleased cancellation;
thread-first skip-locked claim order; truthful queued process-card labels;
focused session-capacity CI route. No business routing or automatic retry.

## Verified and incomplete

- Final Python focused gate411 pass/32 platform skips in41.17s, with real isolated PostgreSQL.
-216 App direct-consumer tests and TypeScript pass; Python focused types zero errors.
-131 CI/governance contracts pass; scope selector returns session-capacity.
- Independent Codex CLI review found no clear actionable regression by inspection;
  reviewer did not run tests. Built-in agent spawning was unavailable.
- Awake real A/B native tasks overlap53.82s, complete55.15s/53.82s including deliberate45s sleep.
- Followups47.36s/46.08s read original15B CSVs; four downloads match exact bytes/hash.
- Waiting taskthr_1918434cbe41e1527980 cancels immediately without attempt_started;
  other tasks remain running. Running cancellation also completed.
- Original queued browser screenshot exposed contradictory process-card wording;
  corrected-card regression passes. Final corrected-card LIVE screenshot/refresh
  acceptance is STILL PENDING: Mac sleep and AX permission_denied interrupted it.
- Do not claim overall business speedup, full summer replay or final UI acceptance.

Read docs/reports/2026-11-03-execution-capacity.md and the accepted plan before proceeding.
No more repeated model trials were started after the second sleep interruption.

## Local runtime

Local-dev temporary sourceb7dd440c, actual App identityb7dd440c, local-dev.
API/worker image421ce00d8fd821c7b3ca0157fccbf44127dc8fe8fad73c6f0cb92969114b86c8.
Native imagedc430bffe525e9a028041976ac424818f141319bb2e5bbab02e99a32c73213ff.
Canonical rebuild/ready/same-image check passed. Native slots2.
Final log:/tmp/capstone-capacity-rebuild-ui.log.
Scoped cache maintenance applied; worktree receipt
.capstone-agent/cache-maintenance-20261103-141803-13648.log.
Dedicated tmpfs PostgreSQL test container was stopped and removed.

Use DOCKER_CONTEXT=orbstack, COMPOSE_PROJECT_NAME=capstone, original root
deploy/local.env and root verified PyPSA assets/root resource policy.
DO NOT override the absolute gateway auth directory in local.env.
A wrong empty test mount and omitted helper COPY were corrected.
No credentials were copied into the worktree; user data/named volumes retained.

## Next actions

1. Finish control/report synchronization and inspect regenerated actual-dev graph
   only if the existing GUI tab is accessible. Record an AX block, never infer pass.
2. When graphical access is available, finish corrected queued-card/refresh
   verification with bounded work. Preserve successful and sleep-interrupted receipts.
3. Candidate is ready for review of its local changes; request separate approval
   for one macOS session-capacity CI before any push/PR. UI gap remains explicit.
4. Merge dev only after approved focused gate and accepted local scope, then update
   actual dev graph and close branch. No main or remote deployment in this task.

## Recovery references and ownership

Root runs/execution-capacity-20261103/: acceptance helper, real events, CSVs,
download hashes, queued cancellation and sleep-interrupted evidence.
/tmp/capstone-capacity-*.log: selected tests, builds and independent review.
Source commits:f0e8728e/e7d7fbc2/692fa36e/fcad0a76/7616f389/b7dd440c.
Task-owned control/report/design/plan edits exist in root and candidate as recorded
by git status. Preserve unrelated docs/reports/2026-11-01-summer-session-audit.md.
No CI approval from an earlier task carries over.

Research server remains disconnected: no probes.
Intranet25c71f85 and its acceptance tag remain unchanged; cloud/demo unchanged.
