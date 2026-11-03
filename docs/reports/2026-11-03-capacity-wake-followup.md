# Pending work after a busy thread lock

Follow-up to PR91, based on dev c3a0c472. Candidate branch:
fix/capacity-lock-wake-20261103. No new CI or push is approved.

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
Canonical candidate rebuild and artifact preservation are checked before CI.
Main/intranet/cloud/demo are unchanged. A separate focused CI approval is
required before publishing this new source revision.
