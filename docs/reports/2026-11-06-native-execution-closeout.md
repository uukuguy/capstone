# Native execution release closeout

User requested closeout, tag and main integration on 2026-11-06. CI is not yet
approved. No branch push, PR creation/update, merge or release tag has occurred.

## Exact sources and isolation

- Current dev:6c55e6eed7c7988ef14baa9959dd9cd65e6d410e.
- Current main:0b68c6073c0440b2197dd4daa730127079e70b9b, ancestor of candidate.
- Existing local-dev runtime:984131e388244ee4cf24e1d13c2af4a41f87ede4.
- Consolidated source/evidence parent:7295d6d57270bb0be55fbaf191838e61730a5c92.
- Runtime repair source:faa9bcc05a93ae73865012bdb6b890ed9fe344a0.
- Diagnostic archive/fixture repair source:6c54b0778c334a1c9644999b1bc10b6e57117d1f.
- TUI test scheduling repair source:a8fbf683 (current code candidate).
- Integration branch:uukuguy/native-execution-release-20261106.
- Orca checkout:/Users/sujiangwen/orca/workspaces/capstone/native-execution-release-20261106.

The original dev checkout's mixed changes, normal index, ignored runtimes and
user data are preserved.1313runtime inputs matched the recorded candidate before
release repairs. No authentication state was copied into the isolated checkout.

## Scope

Thinking previews and bounded durable writes, frozen model/reasoning selection,
direct native conversation entry, explicit Domain Pack grants, startup diagnostics,
single-binding publication reuse, structured independent calls and bounded cursor
chains. The original source consolidation had153files/20first-parent commits.
Current code candidate differs from dev in 158 paths after release repairs
(23 commits including evidence; 7181 insertions/703 deletions before final control docs).

## Local verification and repairs

The first type gate found 49 errors. These were corrected without suppressing the
gate. Repairs make optional bound-model contexts explicit, retain the full empty
catalog tuple without credentials, reject invalid report roles safely, type the
timing relay, expose the preview service contract and use the same lease validator
for preview and execution. Existing dynamic factory attributes and writer delegation
remain compatible.

New error-path tests failed before implementation (3failed/2passed), then passed.
Related focused checks passed 184 on Python3.14 and 184 on Python3.12 (11.02s).
Type checks on Python3.12:0 errors/0 warnings. Fresh make setup/install-pi/doctor
completed. First GitHub Pi fetch timed out; a stale shallow lock was preserved and
the retry fetched the exact pinned public Git commit from the existing local object
cache using process-scoped Git configuration. No credentials or ignored auth state
were copied. Pi remains pinned to b79e4cc834970cca69daebffab7df1da7d1e52c4.

First full local `UV_PYTHON=3.12 make check-release` at faa9bcc0 failed in 892.41 s.
Grid CLI997passed/3skipped (511.05s), simulator279passed/2skipped (187.81s),
governance61passed/2skipped; capstone-agent3142passed/197skipped/1failed (165.95s).
The failure fixture omitted the terminal source_status now required for continuation
files. The fixture was updated; the production terminal-only filter was preserved.
Focused file/debug consumers passed32/28platform skips. This is not a passing full
aggregate receipt. The next component run at6c54b077 passed3142/197skips but failed the TUI fixed80ms wait.
The same TUI module passed12tests in isolation, and implementation review shows timer,
worker and UI callbacks must all complete. a8fbf683 replaces the fixed sleep with
a bounded2s condition wait;12tests pass. The full agent component then passed 3143 tests/197 skips in 162.12 s
at a8fbf683 (exit 0); all remaining release targets then completed with exit 0. Already passing unrelated CLI/solver checks
are not repeated. Both failed aggregate receipts remain recorded.

The structured reviewer channel rejected unavailable defaultmodelgpt-6.1-luna.
Fallback `codex review` completed using the user's defaultgpt-6.1-sol and identified
one P2: unbounded raw diagnostic retention in conversationArchive.6c54b077 separates
diagnostic replay into an explicit event_buffer_bytes budget, preserves message
bodies/routing identity and avoids sorting tool/Thinking diagnostics for intent
projection. The new bound regression failed first, then related App104tests passed;
App typecheck/build passed. A stale test returned diagnostic data through the public
history RPC; it now tests the intended live diagnostic stream without weakening
public-history validation. Follow-up `codex review --commit 6c54b077` completed: no actionable regression
found in the patch or direct consumers; reviewer inspected but did not run tests.

Remaining checks: App 1527, Kernel 663, workbench 156, E2E 39,
registered workers 3 passed. Offline/core/full static validation passed 7/10/8;
application instantiation passed 2; capability matrix passed 24/24. Independent
wheel/sdist/npm package installation, installed Authority/model operations,
frozen source setup, App build and final doctor all passed. The remaining-target
process started at 6c54b077; a8fbf683 changed only the TUI test, outside these targets.
This is split local release evidence, not one clean aggregate run. No CI has run.
App build retains the existing large-chunk warning; there is no build error.

Control graph was re-laid out and checked at 1920px: no horizontal overflow,
exact candidate ancestry edge from984131e3, actual dev HEAD and runtime source
remain distinct. UX search did not yield diagram-specific guidance; manual visual
inspection checked card readability, connector attachment and crossings.

Private logs and exact timing receipts:
`.capstone-agent/release-closeout-20261106/` in the original checkout.

## Known limits

Local runtime984previously passed six independent chains ×two dependent pages,
12source calls, overlap4,0tool errors and real CSV download/replay. This is not
acceptance of every complex research task or proof that a model always selects
optimal concurrency. Release repairs are not yet deployed to local-dev.

data-gateway local runtime was missing grid_database; its29observed gateway errors
remain an external assistance item. The user chose to forward the report manually.
No gateway source/runtime, intranet63/66, cloud or demo environment is changed here.

## Integration and tag procedure

1. Complete local candidate checks and preserve exact evidence.
2. Request explicit approval for the dev PR CI: macOS, current product gate
   (`make check-pr` plus governance/setup), estimated15–30minutes. The wide gate is
   justified by the accumulated Application/Kernel/Domain/runtime/App changes;
   it is not an ordinary single-layer edit.
3. Push/create the candidate-to-dev PR only after approval. Merge after its gate
   passes, then synchronize the actual dev checkout while preserving mixed work.
4. Request a separate approval for main PR release CI: macOS+Linux,
   `make check-release` plus setup/governance, estimated30–60minutes. No automatic
   second run is authorized by approval for the first.
5. Merge dev into main through PR after checks pass. Create and push an annotated
   `milestone-native-execution-20261106-<short-main-merge-sha>` tag at that exact
   accepted main commit. Record source, CI receipts and limits in its annotation.
   This is a software milestone tag, not cloud/demo deployment acceptance.

PR descriptions are prepared locally. No CI was started during preparation.
