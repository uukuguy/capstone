# Control runtime observation and diagnostic navigation

Owner capstone-app. Branch feat/control-runtime-views-20261117 targets dev
dc6ada7b (PR136 event layer accepted; actual local-dev read smoke passed).
Implements the approved three-perspective design in the existing Control sheet.

## Delivery contract

- Keep the board mounted when switching perspectives; retain selected task.
- Runtime shows current Control/task states separately from a fixed event prefix.
  The control lane shows actual Control events; task lanes link exact recorded
  task versions and delegation bindings. No fabricated duration or model trace.
- Diagnosis presents source event identity, Control sequence, accepted observation
  sequence, before/after records and exact old/new execution links. These source
  sequences are distinct. Returning restores the event and runtime reading position.
- Event reads are manual-refresh, fixed-watermark pages of 50, capped at 500 loaded
  records. No background request may replace historical selection. Current Goal
  polling remains separate. Missing history and failed reads remain explicit.
- Workspace and Goal switches isolate loaded events; rejected or late responses
  never populate another Goal. Existing conversations/products remain the readers.
- No backend change, Agent trace reconstruction, replay execution or parallel
  scheduler is claimed. CI needs a separate approval after local acceptance.

## Implementation and verification

- [ ] Add bounded typed Control-event parsing and scoped transport; test wrong
  identity, nonmonotonic sequences, invalid bounds and exact query cursors.
- [ ] Add ControlWorkspaceViews, runtime lanes and diagnostic event details; test
  history gaps, exact binding links, fixed pagination, late response protection,
  same-event return and board selection preservation.
- [ ] Integrate ControlGoalPanel with three perspective controls; preserve existing
  commands, drafts, uncertain retries and original Thread navigation.
- [ ] Run App types and focused consumers; inspect desktop/narrow candidate in
  the existing browser tab against the accepted design. Real existing Goal reads
  prove legacy compatibility; real recorded events prove event navigation.
- [ ] Record candidate, add a focused macOS gate, update control overview, commit
  verified owned paths. Integrate through dev PR only after new CI approval.
