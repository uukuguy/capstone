# Live Session Checkpoint

> Updated: 2026-11-01. Known Capstone findings closed to the full-business rerun boundary.

## Current boundary

User asked to fix known findings until a full “迎峰度夏” rerun is needed.
Do not automatically replay that historical task. No CI without user approval.
No push, PR, merge or other deployment. Reuse existing browser tabs.

Dev implementation0db2803a is rebuilt and ready. API and all workers share
image f56538f8b2f355038bdaeb1f8e7714fd6e3b82a178aa9daf4ba6fd0da0028713.
Cleanup receipt .capstone-agent/cache-maintenance-20261101-164236-92101.log.
App product remains c00bfb15; other three deployments unchanged.

## Implemented and checked

- b8ae7ba1: exact identity search, bounded labelled partial matches, activation
  state, and guidance that known names and composition need no redundant load.
  68 Node and3 runner checks passed.
- 898f0134: one task-scoped resolver for direct-call references across composition
  read, inspect, follow and context saves.86 Node and34 relay checks passed.
- 0db2803a: normalize structured roots; preserve recorded transport-prefix paths
  and explicit raw-file pointers.64 focused checks passed. Cross-task references,
  altered files and failed-source actions remain rejected.

Real empty-session acceptance: thr_ecb9987a715958b77bf7,
attempt_7fe8e93e4f9f9d45, work_8eb146febb32e2943cb8.
Completed21.885s; first LLM1.017s;4 LLM responses/4 tool executions/zero errors.
Discovery and check once each; no search/load/repeated retrieval.
JSON2269bytes downloaded and SHA256 verified:
1dbf1c106fe51cbe36f99153bd8fe3df22ce3fecddd5dcc0ed0af866191d322f.
Evidence runs/lightweight-normalized-reference-20261101/.
The model reused a saved file; focused tests cover opaque-reference root reuse.
Do not claim the real trial exercised that exact model-selected path.
Existing Vivaldi validation tab points to this thread, no new tab opened.

## Gateway boundary

Reconnected18001, read initialization then discovery/check/full contract.
Same instance3db5bb96-2c27-4d97-8584-346bc4a18656; publication is now
2026-11-01T16:34:18.989104+08:00, consistent in all three responses.
Historical frozen snapshots remain unchanged.

Prior attempt_f27ce0c18e08e7aa used invented concept “gateway contract check”.
Discovery provides concepts[].id, but concept's input schema is an unconstrained
string and its error has no request_id or recovery source. Coordination note:
docs/reports/2026-11-01-gateway-selector-followup.md.
Prepared only, not externally sent. No fixed concept names/routes added.
Earlier source-table gaps remain in
runs/summer-session-audit-20261101-new/gateway-followup.json.

## Next acceptance

Full summer task is needed to judge business planning, repeated discovery,
retrieval counts and recovery over a long execution. Short metadata acceptance
cannot prove those outcomes. Preserve concurrency4 and current source selection.
Business content/PPT polish remain deferred.

Control register and overview updated for this boundary. Preserve unrelated
untracked docs/reports/2026-11-01-summer-session-audit.md.
