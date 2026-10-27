# Shared tool composition implementation plan

Goal: let lightweight/DR executors combine authorized gateway calls and local
analysis in one program, then share grounded semantic/data packages.
Architecture: new neutral native capability; reuse current gateway relay, native
UID/process boundary, event receipts and graph artifact input contracts.
Stack: NodeES modules/IPC + Python native capability registration; existing App.

## Unit1: executable composition and packages

Files: resources/tool-composition-policy.json, tool-composition.mjs,
tool-composition-worker.mjs, semantic-data-context.mjs under capstone_agent;
tests/fixtures/tool-composition.test.mjs and semantic-data-context.test.mjs.

- [ ] Write failing tests for two overlapping calls followed by a dependent call;
  assert all argument and call identities, not a sleep-speed threshold.
- [ ] Write failing tests for denied tool selection, call/concurrency budget,
  abort/timeout, process cleanup and no credential variables in worker.
- [ ] Implement `createToolCompositionTool({policy,cwd,catalog,invoke,deadlineAt,
  scope,allowedInputs})`. Expose the program API in the accepted design.
- [ ] Test and implement `saveSemanticContext`/`loadSemanticContext`: derive values
  only from captured call refs, mark literals declared, retain partial/error
  provenance, reject invalid refs, hash tampering and path escape.
- [ ] Run node tests with the real child process and Python; inspect and commit.

## Unit2: actual SDK and host registration

Files: native_tool_composition.py, native_task_context.py, general_pi_server.py,
resources/general-sdk.mjs, deploy/general-pi.Dockerfile and affected tests.

- [ ] Add native root `tool_composition` exact versioned policy. Application
  admission requires the advertised feature and native execution + gateway grants.
- [ ] SDK installs the tool in direct and child execution roles. Its inner calls
  go through existing application/graph wrappers, with distinct call IDs and normal
  source admission. Organizer does not receive native execution permission.
- [ ] Register feature source validation, hash all implementation resources in the
  executor identity, copy modules into the actual Docker image.
- [ ] Test exact registration, unavailable capabilities, forged policies, graph
  child receipts, no duplicate events and unchanged legacy contexts.
- [ ] Add compact guidance/sample code to current feature context/tool description
  for semantic source selection, shared package inputs and minimal preparation.
- [ ] Run focused SDK/host tests and commit the verified unit.

## Unit3: visible integration

- [ ] Check active attempts, canonical local rebuild and scoped cleanup.
- [ ] New Vivaldi conversation in existing tab: real MCP-discovered independent
  operations in one program, dependent local calculation, saved semantic package.
- [ ] DR trial: producer supplies package through existing artifact slot and
  downstream executor loads it without repeated gateway retrieval.
- [ ] Validate real files, provenance, individual process events and mode isolation;
  preserve partial results if a limitation appears. Record actual metrics.
- [ ] Update report, journal, recovery checkpoint and owning design; commit owned
  paths only. Preserve unrelated work and remote/deployment boundaries.
