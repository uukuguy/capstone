# Live Session Checkpoint

> Updated: 2026-09-05 23:00 CST. **Session remains active — not a final handoff.**

## Active correction: assurance is not application failure

Latest user failurec87f71ad answered question4 without tools. Root cause was
runner aborting a valid committed limited turn, plus Domain replacing its text.
Main working tree now retains unverified text with a Chinese warning, continues
limited turns, and maps limited honestly in the compatibility report. Existing
protocol/reference/commit failures remain fatal; typed domain-tool errors may
be committed as limited. Policy explains current-turn
retrieval of existing run evidence without recalculation.
Actual final-source run1999fd31 (65752) completed9/9, exit0: q4limited, q9
lineage_verified with9 result/9 evidence refs; all9 committed admission hashes
verified. Full33200 reached inventory old continuation assertions; only two test
assertions changed, no inventory business code. Inventory118+1 and Workbench154
pass; E2E4964 passed37 and exited0. Protected tree baseline updated only for that test delta;
commit then run make validate. All older "no paid run performed" notes below
are superseded by the user's explicit actual-rerun authorization and these runs.

## Fourth-question discovery classification repair

The user's run-20260905t133022z-c081b57c passed question3 but failed question4:
successful operation list/describe were incorrectly counted as missing-evidence
execution. Main now exempts only successful stateless capabilities explicitly
declaring evidence_required=false; no tool-name whitelist or new API.
Regression2509 failed before correction; admission11/controller26/type checks
pass after correction. Full main gates3997 exited0: doctor/test/E2E36,
validate7+10+8 and coverage24 passed. Repair48fb64f is committed directly in main.
No test process remains active.
The earlier live Provider nine-question workflow is still NOT verified complete.

## Guide admission regression repair (supersedes historical closure below)

Working directly in main after69a1ca9. Real run
run-20260905t120836z-92084c98 failed on question3 after a successful guide read.
The minimal fix preserves current-turn published-guide reader text with
guide_access_verified (not semantic/numerical verification), retaining existing
authority evidence admission. Main doctor/test/test-e2e36/validate7+10+8 and
coverage24 passed (chain11027 exit0). Final four-turn regression84521 also
passed: both real user guide questions followed by real powerflow; projector15
and type checks pass. Final review approved; repair0a04daa is committed in main,
post-commit doctor passed. No repair process remains active. Do not treat this as proof the
real Provider nine-question workflow passed. No paid Provider calls authorized.

> Updated: 2026-09-05 20:04 CST. Main delivery closure checkpoint.

## Delivered in main
Accepted optimization source1c32c0a is fast-forwarded into the main checkout.
make application resolves via analysis-generic to the public AgentApplication;
uv import checks confirmed Application, Kernel and pandapower Domain Pack load
from main, not .worktrees. Main dependencies and managed Pi runtime updated with
make setup and make install-pi. AGENTS now requires main delivery/regression
unless the user explicitly requests branch-only delivery.

## Verification
- Main doctor, entrypoint mapping, application-instantiation2/2, make test passed.
- First68429 E2E:30 passed/1 failed (scripted test inherited local model).
- Fixed only two test env settings to pin model alongside provider; original
  assertions and user configuration retained. No production code change.
-79559 exit0: focused1, fullE2E31, business7/7+10/10+8/8, capability24/24, doctor.
- Reports: main runs/validation-*.json. No active test process.
- No paid Provider or remote publication performed.

## Preserved and deferred
- Old main baton edit preserved in stash named
  pre-integration main recovery baton preserved; not dropped.
- Untracked docs/superpowers/plans/2026-08-31-capstone-framework-guide.md intact.
- Old optimization worktree retained solely to preserve unaccepted OP13 source,
  tests, kernel uv.lock and journal note; these did not enter main.
- OP08 strict JSON extension and OP13 writer DEFERRED; legacy default unchanged.
- No runs/var/auth data deleted or copied from another worktree.

## Next action
Use make application from the main repository with the desired Provider/model.
Implementation and main regression are complete; no automatic C.2, cleanup or
new performance work. The final main commit after1c32c0a records this closure
and the test isolation correction; resolve its hash with git log.
