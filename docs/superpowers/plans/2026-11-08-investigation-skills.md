# Investigation skills implementation plan

Goal: make the six accepted investigation methods available on demand and show actual skill use in the existing execution process.

Architecture: application-owned native resources provide immutable skill packages. The native tool boundary admits skill loads and model-reported application records. Existing persisted tool events carry bounded public records; the App projects those records without treating them as Authority evidence.

Dependency: this branch starts at 7ea164de on the unmerged execution-lifecycle candidate. Do not overwrite its runtime or infer dev integration. No CI approval exists.

- [ ] Register six local native skills in configs/runtime/agent-resources.json and general-pi/settings.json. Test both general roles, content identities and exclusion from professional roles in test_runtime_resources.py.
- [ ] Implement resources/investigation-skills.mjs with on-demand load and bounded model-reported phase records. Test unknown skills, changed bytes, report-before-load and honest verification state with node:test.
- [ ] Wire native registration and grant admission in general-sdk.mjs and general_pi_server.py. Preserve public skill metadata through delegated_runtime.py and existing persisted events; check scope and bounded fields.
- [ ] Project skill records in the existing process UI. Test loading versus application, failures, ordering and snapshot replay. Use the accepted conversation components.
- [ ] Run focused Python, Node and App tests, typing, doctor and diff checks. Rebuild only when ready for live acceptance; use the existing browser tab, real model/tools, saved products and refresh recovery. Run scoped cache maintenance after use.
- [ ] Record verified results, remaining gaps and exact branch/runtime identities. Commit owned paths. Update canonical dev control and graph with UI skill and browser checks at the integration boundary. Push/PR/merge waits for explicit CI approval if it starts CI.

Acceptance distinguishes installation, loading, model-reported application, checks and delivery. Six skills share task state; Provider-specific rules remain provider resources. Source retries, permissions, reference identity and asynchronous continuation stay mechanically enforced.
