# Live Session Checkpoint

> Updated: 2026-11-03 19:32. Active lock-wake follow-up; do not treat the task as closed.

## Active candidate and permission

PR91 implemented observation recovery, bounded native slots, queued cancellation
and truthful UI. It merged into actual dev/origin-dev c3a0c472 after explicitly
approved CI41624694112 passed4m02s and final live UI/refresh checks passed.
That CI authorization is consumed.

Late deterministic audit found a lost wake when all matching accepted thread
rows were locked: SKIP LOCKED returned None, then no second wake followed unlock.
Real PostgreSQL regressions FAIL on c3a0c472 at capacities1/2.
Follow-up fix8dd51d0b1745da3440a00267e4e7037717396a88 is committed locally on
fix/capacity-lock-wake-20261103 in .worktrees/capacity-wake.

The user explicitly approves ONE new macOS session-capacity CI and dev merge
after page verification. Publish this candidate and use that approval once.
Source code is complete and reviewed; no new model calls are needed.

## Correction and evidence

InMemory/PostgreSQL services expose a read-only pending-state predicate with the
same family eligibility as claims. Serial and parallel workers rescan after the
existing interval only when matching accepted work remains. Empty queues still
wait without SQL polling. No leases, task retries or business tool choices added.

100 focused worker/ledger/cancellation checks with real isolated PostgreSQL pass
in18.94s; types0 errors. Both real-PG capacity cases and pure-memory CI regressions
now pass. Independent CLI review found no actionable defect by inspection; its
own generic .venv test command did not run, correctly selected tests did.
Report:docs/reports/2026-11-03-capacity-wake-followup.md.
/tmp/capstone-capacity-wake-{final,types,review,rebuild}.log.
Temporary PG container capstone-capacity-wake-test-pg removed after tests.

## Current local runtime

Local-dev backend is TEMPORARY candidate8dd51d0b; actual dev stillc3a0c472.
Canonical rebuild ready, API/worker imagedcce6b252911cc1154d6bbd124de3295785550c63ece6f75bfb07398e5ebc261.
Native imagedc430bff unchanged; App productb7dd440c/repositoryc3a0c472 unchanged.
Native slots2 in root ignored local.env; default1 in source. Running worker has
pending-state reader. No Provider calls were made for this follow-up.
Use original root local.env, its absolute auth directory and root verified assets.
No credentials copied. Preserve original root var and all named volumes.
Candidate cache cleanup receipt:.capstone-agent/cache-maintenance-20261103-193120-37642.log.

## Next actions

1. Finish root/candidate control sync and pending-wake graph inspection.
2. If the new CI approval arrives, publish final candidate, create dev PR and
   run precisely the existing session-capacity gate once. Merge only on pass.
3. Fast-forward actual root dev, canonical rebuild from root, verify original
   artifacts and changed worker entrypoint, refresh actual dev graph and close branch.
4. Preserve both passed and sleep-interrupted earlier model evidence. Do not
   rerun models or broaden to full release/professional suites.

## Preserved work

Root has final PR91 control/report/plan snapshots; copy their owned updates into
the follow-up delivery before publishing, preserving journal append-only order.
Do not overwrite these with older candidate snapshots. Root graph/register now
also show the follow-up source and temporary deployment.
Unrelated docs/reports/2026-11-01-summer-session-audit.md stays untracked/unmodified.
Original control stashd23dafb19e2173fe0ed4c741f4fccba875872cd5 is recovery only.
Former PR91 worktree state preserved under
.capstone-agent/recovery/execution-capacity-20261103-c3a0c472/.
Real earlier CSV, event and UI evidence:root runs/execution-capacity-20261103/.
Main0b68c607, intranet25c71f85 and cloud/demo unchanged. Research server disconnected;
do not probe or deploy. No full release or business-query speedup claim.
