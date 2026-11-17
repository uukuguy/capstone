# Control task board implementation plan

Owner capstone-app. Branch feat/control-task-board-20261117 targets dev5c8fe6d1.
User accepted task board / runtime lanes / diagnostic trace perspectives.
This delivery connects the task board to existing Control data; later perspectives
need Control event history and must not display fixture telemetry as live data.

## Scope and acceptance

- Replace the existing stage list with four status columns and a task inspector.
- Keep creation, revisions, uncertain command identity/retry, verification and acceptance.
- Reuse delegated Thread/Work navigation; do not build a second conversation component.
- Pending, active, delivered and verified map to board columns. Cancelled records
  are separate terminal history, never successful completion. Paused/failed/blocked
  remain explicit badges and do not claim active computation.
- Selection uses goal/objective/task revisions. Same-version refresh preserves cards
  and focus. Goal switching rejects late responses and hides wrong-goal controls.
- Product work is App-only. Parallel scheduling and Control event history are excluded.

## Delivery

- [x] Write focused projection, selection, command and late-response regressions.
- [x] Implement typed presentation mapping and task board/inspector.
- [x] Connect existing panel and preserve current commands and session entry.
- [x] Run focused App tests/types and inspect an actual local browser.
- [ ] Record exact verification and remaining limits before integration.

Candidate browser verification must reuse the existing tab. Rebuild through the
canonical local entrypoint before current-runtime acceptance. No cloud/demo update.
This implementation preserves the accepted three-perspective direction; the existing
sheet is the first entry integration, not acceptance of the full workspace shell.

Local evidence: 74 App tests/types and 123 scope checks pass. Candidate5174 reads
six actual Goals; accepted two-stage Goal opens the original Thread/Work. Card DOM
survives refresh; desktop/narrow layouts checked; no execution commands were sent.
Root backend (unchanged product source) canonical rebuild passed readiness and
API/three-worker identity d68d26ab, scoped cache maintenance completed. Candidate
App comes from this worktree, not actualdev5173. CI and integration remain pending.
