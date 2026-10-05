# Live Session Checkpoint

Updated: 2026-10-05 20:20 CST. Local follow-up repair is complete.
This is a recovery checkpoint, not a final handoff.

The user requested complete repair of stale presets and ranking-to-grid
linkage, then added an answer-row icon for each instruction's grid view.
The repair is verified locally and ready for task-owned commit on main.
Plan: [repair plan](../superpowers/plans/2026-10-05-thread-preset-ranking-and-task-view.md).
Evidence: [repair review](../reviews/2026-10-05-thread-preset-ranking-and-task-view.md).

Presets execute directly. Superseded loads/streams cannot erase new events.
Definite stale rejection has one bounded synchronized retry. Prior result
references require exact Context and fresh authority admission. Ranked
focus/values come from the authority, with supported contract bounds.
Numeric layers use the matching completed Attempt's references. Each answer
can restore its own graph; current/old-model views and colors stay separate.
New sends/retries return to the current view. Cancel/retry numbering is correct.

Verification: backend465 passed/32 optional skips; real projector70 passed;
real multi-turn rank-only sequence; final App222 passed and build; Pyright,
doctor, diff, relative symlink, full make check-release exit0. Full gates
include E2E39, registered-worker3, validation, installs and source setup.
Final App-only refinements passed their own full test/build checks.
Final make capstone-local-rebuild exit0. API and both workers share image
sha256:c3a9cd294bddfb952213564fff382e6331a4f3fde4a74650847d01624813a3eb.
Six modified backend files match the running API. Readiness, App200, and
catalog pandapower60/PyPSA21 pass. Original user Thread stays IEEE39/cursor76.

CLI browser checks: preset accepted once despite late old snapshot; RTS full
33-line flow then rank3; only rank/evidence retrieval in the new turn and
same result ref; old full-flow restoration; return/reload; old IEEE35 colors
without changing active RTS; phone390 has no horizontal page overflow.
Independent review has no open finding. Receipts: runs/capstone-thread-model-fix.
Screenshots: output/playwright/thread-task-*. Test servers, session and auth
file were removed. Normal local ports8767/5173 remain running.

No external Provider call, cloud release, or user-history rewrite occurred.
Finite Pi decisions with actual gridctl do not prove arbitrary live Provider
planning. The user deferred redundant model-area/dropdown simplification;
that work is recorded in the plan and remains a later layout task.

Next: refresh the App to use the repair. Start further work from the user's
next instruction. Do not repeat completed gates without a new reason.
After committing, append the commit hash to the journal and this checkpoint.
