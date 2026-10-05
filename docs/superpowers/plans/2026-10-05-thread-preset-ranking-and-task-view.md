# Thread preset, ranking, and instruction view repair

Goal: Execute presets on one click and bind each instruction to its own grid view.

The user authorized complete local repair and verification. The user added
an explicit requirement for a grid-view action in each answer's icon row.
This extends the active repair; no deployment or Provider call is required.

Design: Keep the existing preset send action. Protect projection loads and
streams by generation. Retry a definite stale-cursor rejection once only
after synchronization and unchanged model, profile, run, and idle state.
Carry bounded prior result references for exact Context retrieval, with
fresh authority admission. Generate ranked focus through the registered
authority. Restore each instruction's validated diagram and layer from
public events. A graph icon selects that instruction's view locally;
it does not activate a historical model. New accepted instructions return
to the latest view. Missing or invalid views have no graph action.

Alternatives: Reusing the latest whole-model overlay loses instruction
scope. Re-running old instructions to restore their views changes evidence
and can incur cost. Event-backed view selection preserves original facts.

- [x] Reproduce stale preset and missing ranking focus with failing tests.
- [x] Fix load, stream, single-create, and bounded stale retry behavior.
- [x] Add prior-reference retrieval and authority-backed ranking focus.
- [x] Add per-instruction graph retention and answer-row selection tests.
- [x] Verify direct preset, full flow, rank-only reuse, old-view selection,
  latest-view return, reload, and phone layout in the local browser.
- [x] Resolve independent review findings and run repository scope gates.
- [x] Rebuild the real local entry point, record checks, and commit repairs.

Files: App projection store, Thread workspace, assistant answer actions,
model pane, and their tests; neutral Attempt/Harness contracts and tests;
pandapower application network provider and real-authority sequence tests.
No domain semantics enter the Kernel. Raw authority rows remain private.

Evidence is stored under ignored runs/capstone-thread-model-fix and
output/playwright. Existing user Threads and local data remain intact.

Deferred by the user: reduce repeated model name/status blocks and replace
the always-visible large switch dropdown with an on-demand model directory.
This is a later layout task. It does not block this repair.
