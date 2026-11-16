# Stage B local verification

Owner: capstone-control; consumers: capstone-agent and capstone-app. Branch
feat/control-delegation-20261117 targets dev through draft PR126. This is a
development record. Integration and final source verification remain open.

## Ownership and contracts

Control owns its PostgreSQL Goal aggregate, semantic objective revision, Task
dependencies, delegation budget and operation receipts. Its core imports no
Agent ledger. The application assembles an Agent port; the Agent registry owns
idempotent Thread/Work admission and execution-side controls. Harness Attempts
remain under the Agent Work. General process artifacts remain distinct from
Authority evidence. No Domain Pack or solver contract changed.

Goal.revision is the CAS/storage revision. Delegation.goal_revision names
Goal.objective_revision; Task.revision names the phase contract. Exact product
references and workspace grants bind later Tasks to original bytes. Final user
acceptance is independent of execution completion and byte verification.

## Focused local checks

Source8d292962:183 backend/governance checks passed with a disposable PostgreSQL
database in18.62seconds;71 App checks passed in8.97seconds; TypeScript passed.
Separately23 verification-configuration checks passed. Reconciliation tests
reproduced the bound-execution deadline gap before the fix and now pass for
single and goal execution. Existing tests cover concurrency, lost acknowledgements,
revocation races, late observations, workspace/version rejection, immutable
resource admission, UI drafts, operation replay and background dependency release.

## Real model and saved products

Local runtime source995c06a8, Goal
goal_b600ce4290e3d95cdb4dfae171f40925: two distinct Threads, one completed Attempt
each. Downloads verified original181bytes/SHA419f88114b5aadf2fdf9fc0cd9fa8a92a74253e4cca75484b91ce7f4d404b8e4
and report3369bytes/SHA3d51f627ae820864778a20a0202101ae854265f815889ec8c956a221d7a10b60.
The report contains the actual random marker, original hash and length. One
host-qualified cross-Thread input receipt persisted. Explicit browser acceptance
changed delivered revision11 to accepted revision12, recording workspace:open
and the exact product descriptors. The first failed native single-input trial
is retained; it did not silently reset budget or start phase2.

Source3770e892, Goalgoal_e19b58506e67d464cfdd28e3a4a0a5fa was created through
the existing Vivaldi workspace. At phase2 dispatching, the persisted intent
existed, the Agent registry had no admission, and no native Attempt was active.
The native worker was restarted at that verified boundary. It continued phase2
without duplicate execution: two distinct Threads, one completed Attempt each,
two total delegations, one qualified original-input receipt. Original33bytes
and final1846bytes were downloaded and hash/marker/length matched. API restart
and browser refresh restored the same delivered Goal and products. Acceptance
remained null, proving that restored completion does not accept for the user.

Source3770e892, Goalgoal_dea8ead1fde03c75d11d6289313a3945: pause acknowledged
only after current_attempt became null. Resume retained the same Work and
increased attempts_admitted from1 to2. Revision2 revoked the old execution
before admitting a distinct Thread. Cancel stopped the new execution. Exact
operation replay returned identical receipts for all four controls. Two total
delegations were consumed; no budget was reset.

Source3770e892, Goalgoal_d7bd3c46b320c864a587ac14dd50fbe2: max_delegations1
stopped with delegation_budget_exhausted after one verified15-byte product.
The dependent Task retained pending state with no delegation.

Source8d292962, Goalgoal_48bb4df10d239d2f4ae6998741bf1d4a: a real single-shot
Attempt was observed running before its55-second deadline. Control revoked the
same operation on expiry, waited for current_attempt=null, and settled paused
with deadline_exhausted. Exactly one delegation was admitted. No delivery or
user acceptance was recorded. deadline-result-4.json and the before/after
snapshots retain this active-execution proof.

Receipts, downloaded bytes, full exact synthetic identities and retained failed
trials are in the root ignored runs/control-delegation-20261117 directory.
They contain no Provider credentials. The ordinary10 pinned sessions remain
visible after refresh. Cloud, demo and intranet deployments were not changed.

## Review and remaining gates

Independent reviewer dispatch failed with Unknown model gpt-6.1-luna. There is
no independent review pass. A direct source review inspected Control storage,
reconciliation and state transitions, Agent admission/controls, resource grants,
application assembly and UI state. It found and fixed active-delegation expiry;
the red/green tests above retain the reproduction.

CI43926983198 passed focused execution but failed governance because the new
package was absent from pyright source roots. Fix84b789f4 reproduced and resolved
that failure locally; macOS CI43927606440 passed. Latest source and documentation
will receive the same focused gate. Canonical rebuild8d292962 passed readiness,
API/three-worker identity at imageca5031fdaef4f12f79c083e4e169691a9f4ffa9e6e0cc5d6624cc22dcddf2c9a
and scoped cache maintenance. The accepted restartGoal restored after rebuild
with actorworkspace:open and exact products. Active-deadline stop passed as
recorded above. Current-head CI, dev merge, actualdev rebuild/5173 restoration
and canonical dev control graph remain open.
