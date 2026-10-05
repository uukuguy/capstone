# Thread preset, ranking, and instruction view repair

Scope: local repair of the user's stale preset and full-flow-to-ranking
screenshots, plus the requested per-answer grid-view action.

## Findings and repairs

- An older overlapping load could erase newer events and reset the cursor.
  Loads, event reads, and streams now reject superseded generations.
  StrictMode shares one Thread creation request. Presets still execute on
  one click. A definite stale rejection gets at most one synchronized retry,
  only if Context, selection, run, page, and idle state remain unchanged.
- Ranking did not publish task focus. A bounded application observer retains
  rank query metadata, then rechecks the admitted result through the registered
  authority. Focus IDs and numeric values come from those returned rows.
  The application does not contain fixture line numbers or answer data.
- The App rejected numeric network layers with an empty reference allowlist.
  It now accepts them against the matching completed Attempt/result references.
  A current subset wins over an older full-result overlay. Endpoint and
  transformer focus do not inherit unrelated full-network colors.
- Fresh Attempts lacked prior retrieval references. They now receive at most
  eight newest unique candidates for the exact Thread, Run, Context, model,
  revision, and implementation family. Public namespaced references use the
  same grammar as result projections. A prior reference is not pre-admitted;
  published retrieval and evidence tools must admit it in the new Attempt.
- Each answer can select its own validated diagram and layer. The App retains
  up to 64 available Attempt views from public event history and checks matching
  diagram/layer Attempt identity. Old Contexts remain read-only. Selecting a
  historical full-flow answer also restores that answer's admitted colors.
  Graph selection sends no calculation or model-activation command. New sends
  and accepted retries return to the latest view. Cameras reset by Attempt.
  Instruction numbers exclude cancellations and preserve retry lineage.

## Verification

Regression evidence includes failing tests for overlapping loads, duplicate
creation, rank focus, old-overlay precedence, public-reference grammar,
ranking bounds, per-answer graph actions, historical colors, and numbering.
Independent review checked Context replay and cross-Attempt isolation.

- Backend: 465 passed, 32 optional skips; full Pyright passed.
- Real authority projector: 70 passed. Hosted multi-turn sequence passed,
  including a rank-only turn with fresh admission of the existing result.
- Browser: one preset click produced one accepted instruction; a delayed
  old snapshot did not erase the answer. RTS full flow colored 33 lines.
  The next ranking instruction focused and colored three authority-returned
  lines. Old-answer selection restored full flow; latest return and reload
  retained the subset. An old IEEE answer restored its 35-line colors while
  the active calculation model stayed RTS. Phone width 390 had no horizontal
  page overflow. The grid badge identifies the selected instruction.
- The rank-only browser receipt contains exactly result.branches.rank and
  evidence.get, with the same result reference as the preceding flow. It
  contains no analysis.powerflow.ac.run call. Returned line IDs were 8,17,9;
  these are computed data, not product constants.

- Final App: 222 tests and production build passed. Doctor, relative
  CLAUDE.md symlink and diff checks passed.
- Full make check-release exited 0, including 39 E2E tests, three registered
  worker tests, offline/scripted validation, package installs and source setup.
  The final App-only refinements also passed their full 222-test gate and build.
- Final make capstone-local-rebuild exited 0. Readiness and App HTTP 200 passed.
  API and both workers share image
  sha256:c3a9cd294bddfb952213564fff382e6331a4f3fde4a74650847d01624813a3eb.
  All six modified backend source files match the API image byte for byte.
  The real catalog has 60 pandapower and 21 PyPSA models. The original user
  Thread remains IEEE39 at cursor 76. Acceptance servers, browser session,
  and temporary test credentials were removed.

Logs and service receipts are
under ignored runs/capstone-thread-model-fix, with task- prefixes. Screenshots
are under output/playwright/thread-task-*. Independent reports are
ranking-followup-review.md and ui-followup-review.md in the receipt directory.
No review finding remains open.

## Limits and deferred work

Browser decisions were finite Pi-compatible test sessions over real gridctl
execution through the normal hosted application/Harness path. No external
Provider was called. This does not prove arbitrary live Provider planning.
No cloud release or existing user history rewrite occurred.

The user deferred model-area simplification. Repeated model name/status
blocks and the large always-visible switch dropdown remain a later layout
task. This repair does not expand deployment or Provider authorization.
