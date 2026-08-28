# Task 9 Review Findings

## Important

1. Release-source revision binding was circular: receipts and `eval-local.sh`
   accepted the final `HEAD` or `CLIMB_SOURCE_COMMIT`, so state-only commits
   could stale all receipts and tests had a production spoof path.
2. Closure needs two commits: first fix the source/evidence mechanism without
   generated final state, then regenerate app/dist receipts, rerun B-H005, and
   commit refreshed state evidence.
3. Carry-forward evidence was too permissive: prior scores were accepted without
   enough validation of configured hypothesis ownership, session, exact command,
   return code, artifact containment, local-eval shape, and event/row agreement.
4. `sync-cycle.py` had Pyright failures from unvalidated JSON shapes.

## Minor

- Preserve the current dirty `JOURNAL.md` line in the state follow-up.
- Update the task report with the new commits, release-source revision, and
  final run evidence.
