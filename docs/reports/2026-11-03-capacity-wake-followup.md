# Pending work after a busy thread lock

Follow-up to PR91, based on dev c3a0c472. Candidate branch:
fix/capacity-lock-wake-20261103. The user approved one focused macOS CI and
dev merge after final page verification on 2026-11-03.

## Reproduction and cause

The thread-first SKIP LOCKED claim avoids blocking unrelated work. However,
both the serial and concurrent wake-driven loops treated an empty claim as an
empty queue. If a metadata/cancellation transaction held the accepted thread
row, that claim was skipped. After the row unlocked, no new wake was guaranteed.
The accepted task could remain waiting until another request arrived.

Two real PostgreSQL regressions hold all accepted thread rows, wait for claim
scans at capacities1/2, release the locks without another wake, and require all
three tasks to execute. Both fail on c3a0c472 and pass with this change.

## Correction

- Read only whether matching accepted/unleased attempts still exist. This
  query takes no claim or thread lock and returns no business data.
- After a skipped scan, retry after the existing poll interval only when that
  predicate is true. Keep implementation-family filtering identical to claims.
- If the queue is empty, keep wake-driven idle behavior without repeated SQL.
- Preserve slot bounds, cancellation, shutdown, lease fencing and model behavior.
  This is admission polling, not a model/task retry.

## Verification

100 focused worker/ledger/cancellation tests pass in18.94s with real isolated
PostgreSQL. This includes serial/concurrent row-unlock recovery, pure in-memory
recovery for CI, family separation, and existing empty-queue behavior.
Focused source types pass with0 errors. Independent Codex CLI inspection found
no actionable defects; its own test command used a missing generic .venv and did
not run tests. The correctly selected project test command above passed.

Receipts:/tmp/capstone-capacity-wake-{final,types,review}.log.
Temporary database:capstone-capacity-wake-test-pg, loopback32769, tmpfs only.
No Provider calls or new model trials were used for this follow-up.
Canonical candidate8dd51d0b rebuild passes readiness and API/worker image equality:
dcce6b252911cc1154d6bbd124de3295785550c63ece6f75bfb07398e5ebc261.
Native imagedc430bff and the App productb7dd440c remain unchanged. The running
native worker exposes the new pending-state reader. Scoped cache maintenance
applied; receipt:.capstone-agent/cache-maintenance-20261103-193120-37642.log
in the candidate worktree. Temporary PostgreSQL container stopped and removed.
Main/intranet/cloud/demo are unchanged. The approved CI covers the existing
session-capacity route and its direct consumers; no release gate is authorized.

## Dev integration

The approved macOS CI41629449461 passes in3m05s:355 Python checks/92
environment skips,216 App checks, focused types and changed-document links.
Governance232 passes/2 skips overlaps that scope and is not added to its count.
PR92 merged as7ad2529a3626b2fec36577acbc83906195d19e63. Actual root dev
fast-forwards to that revision, identical to the tested eca9913d tree.
The control page was inspected in the existing browser tab before merge.

Actual dev canonical rebuild passes readiness; API/all workers share image
cad0d7eaf3797c4931fb8f3731a65fb49bd2b2cad25d9145376df585cf47ba3e.
Running native worker exposes the pending-state reader. Ten actual dev capacity
checks and doctor pass. Four retained CSV downloads match original bytes/SHA-256.
App /__capstone-build reports product8dd51d0b/repository7ad2529a, dirty=false;
its product revision includes the backend fix, while presentation code is unchanged.
Scoped cache cleanup applies, receipt:
.capstone-agent/cache-maintenance-20261103-194636-75168.log.
The merged local/remote branch and worktree are closed; runtime recovery stays
under .capstone-agent/recovery/capacity-wake-20261103-7ad2529a/runtime/.
Post-merge control snapshots remain task-owned local changes to record the actual
merge/runtime/graph without starting another CI or embedding a snapshot's own hash.
Actual dev overview regenerated without remote probes and inspected in the
existing browser tab: current HEAD node, merged source edges and exact local-dev
source are visible. Changed links, CLAUDE symlink and whitespace checks pass.
