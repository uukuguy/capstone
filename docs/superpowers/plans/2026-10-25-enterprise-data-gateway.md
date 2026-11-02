# Enterprise data gateway implementation plan

**Goal:** Run enterprise-research tasks against data-gateway production data,
with protected credentials, admitted sources and persistent reader-facing products.

**Architecture:** A host-owned Streamable HTTP MCP adapter supplies a fixed,
task-scoped catalog through the existing native Pi control boundary. Research
organisation and presentation remain in their current components. The gateway
owns all backend selection and switching.

**Tech stack:** Python MCP client and httpx, existing HTTP host/relay, Pi SDK
JavaScript tools, current Thread/Work/source/artifact contracts and Vite App.

Design: [integration contract](../specs/2026-10-25-enterprise-data-gateway-design.md).
Status: local functional acceptance passed on runtime2f9c6b56. Real series,
semantic prepare/execute, same-Work follow-up, exact numeric checks and browser
preview/reload/download passed. Dev integration and required PR checks remain.
Execute implementation sequentially in feat/enterprise-data-gateway. A read-only
review agent was attempted under requesting-code-review but could not launch;
manual review is recorded without claiming independent review.

## Constraints

- Do not read gateway databases or source exports. Use MCP exclusively.
- Do not add Capstone database-backend controls or source-switching logic.
- Keep gateway credentials in protected host configuration.
- Keep local PowerMCP contracts and professional Authority admission unchanged.
- Enable research data operations only; six model operations remain excluded.
- Retain existing research controller, products, sources and recovery paths.
- Make coherent, verified commits at each task boundary; inspect Git status.
- Scope dev checks to the changed consumers. No release workflow is required.

## Task 1: Remote resource configuration and accepted catalog

Files to create:
- configs/runtime/data-gateway.json: credential-free resource ID, namespace and
  explicit research tool allowlist taken from the observed MCP schema.
- packages/capstone-agent/src/capstone_agent/data_gateway_mcp.py: protected
  connection loading, MCP discovery, immutable accepted catalog and schema checks.
- packages/capstone-agent/tests/test_data_gateway_mcp.py: real local HTTP MCP
  fixture and catalog/configuration boundary tests.

Interface: DataGatewayMcp accepts a protected connection-file Path and public
policy. prepare() returns public tool schemas, tool hashes and catalog revision;
call(tool_name, arguments, accepted_catalog) returns the full MCP result and a
host receipt. Neither public return value includes authentication headers.

- [x] Write failing tests for protected/missing configuration, valid authenticated
  discovery, rejected non-HTTP URLs, unlisted tools,
  excluded model operations and schema changes after catalog acceptance.
- [x] Run the focused test file and confirm the new-module failure.
- [x] Implement the smallest adapter using the already installed MCP client.
  Validate JSON Schema locally without remote reference retrieval. Fixed URL and
  headers come exclusively from the protected connection file.
- [x] Run the focused file again. Add a secret-canary assertion across every
  returned catalog/error document. Commit this adapter and its tests together.

## Task 2: Protected host relay and capability admission

Files to modify:
- packages/capstone-agent/src/capstone_agent/general_pi_server.py
- packages/capstone-agent/src/capstone_agent/general_pi_relay.py
- packages/capstone-agent/src/capstone_agent/native_task_context.py
Files to create:
- packages/capstone-agent/tests/test_data_gateway_relay.py

Interface: a task-bound gateway route uses the existing host relay origin and
short-lived grants. It accepts only a public tool name, JSON arguments and call
identity; the task's admitted catalog supplies all upstream configuration.
Capability discovery publishes the same names/schema revision used at execution.

- [x] Write failing relay tests: another task's grant, expired/revoked grant,
  changed arguments schema, unadmitted tool and model tool are refused.
- [x] Add inflight cancellation checks and reuse the existing lease deadline tests;
  unknown completion is not replayed and unavailable configuration is not ready.
- [x] Add the gateway capability to native context only for enterprise-research
  and only after catalog preparation. Keep existing resource checks intact.
- [x] Implement bounded requests and credential-free public errors. Confirm no
  endpoint or credential selector is accepted in task payloads.
- [x] Run new relay tests plus existing general Pi relay and native context tests.
  Inspect the exact diff and commit this boundary.

## Task 3: Native tool registration, research nodes and source receipts

Files to create:
- packages/capstone-agent/src/capstone_agent/resources/general-data-gateway.mjs
- packages/capstone-agent/tests/test_data_gateway_research.py
- packages/capstone-agent/tests/fixtures/data-gateway-research.test.mjs
Files to modify:
- packages/capstone-agent/src/capstone_agent/general_pi_executor.py
- packages/capstone-agent/src/capstone_agent/general_pi_server.py
- packages/capstone-agent/src/capstone_agent/resources/general-sdk.mjs
- packages/capstone-agent/src/capstone_agent/resources/enterprise-graph-runtime.mjs

Interface: public data_gateway_<upstream name> tools use applicationToolAdmission,
guardToolExecution and the existing research beginTool/endTool lifecycle. The
adapter's host receipt binds task/attempt/call, accepted schema, arguments and
result hashes. Isolated nodes receive the same catalog and their own grants.

- [x] Write failing tests for actual SDK inventory and allowed_tools agreement,
  including a research child node calling a gateway tool.
- [x] Verify a fabricated or cross-task receipt is rejected; a valid partial
  gateway response keeps its gaps/provenance and becomes an admitted source.
- [x] Implement SDK registration and node propagation through the existing
  protected configuration path. Never include upstream credentials.
- [x] Add explicit gateway receipt admission without loosening the existing
  PowerMCP descriptor/source checks. Persist result bytes through current source
  and artifact mechanisms; keep model prose separate from service facts.
- [x] Run focused Python and JS tests, existing MCP tests, research runtime
  tests and package-boundary checks. Inspect and commit the complete slice.

## Task 4: Local configuration and real task acceptance

Files to modify:
- compose.yaml: existing general-pi host configuration and protected mount.
- deploy/local.env.example and docs/RUNBOOK.md for protected host file mounting.
Files to create:
- scripts/verify_data_gateway_research.py: real MCP plus App-task verification
  with sanitized receipts, no credential CLI arguments.
- docs/reviews/2026-10-25-enterprise-data-gateway.md: measured acceptance record.

- [x] Mount the operator connection file read-only in the native host only. The
  browser and native task UIDs must not gain access to it.
- [x] Exercise capability discovery and one bounded data query using identities
  returned by the gateway. Save full response bytes in ignored run storage.
- [x] Run make capstone-local-rebuild from the accepted candidate checkout.
  Check readiness and all participating API/worker identities.
- [x] Submit one real enterprise-research request that discovers data, retrieves
  a bounded window, computes a supported comparison and saves a sourced report.
  No copied answer values or prefilled data fixture may replace tool execution.
- [x] Ask a follow-up against that same Thread; refresh in a browser and verify
  source records and report bytes remain accessible. The first real task also
  exercised semantic table prepare/execute and retained its query fingerprint;
  do not repeat that covered path in an extra table-only model task.
- [x] Record durations, model/tool counts and exact receipts. Run the scoped
  build-cache cleanup after validation. Commit documentation and verified source.

## Task 5: Dev integration and control closure

2026-10-25 scope correction requested by the user: keep development CI bounded.
Add a native-runtime scope in tools/ci_scope.py and verify.yml, with semantic
MCP-only dependency checks. Retain foundation, SDK, authorization and deployment
consumers; unknown/solver changes still expand to product and release remains full.
Verify classifier failures, mixed changes and downstream lock changes. Fix the
gateway test's startup-before-grant ordering; prove authorization and revocation
still work with service initialization longer than the test's grant lifetime.

- [x] Update CURRENT-STATE, RESUME-NEXT-SESSION and JOURNAL with exact implemented,
  verified and deferred scope. Update VERSION-CONTROL and regenerate its graph.
- [x] Use ui-ux-pro-max and a browser to verify current HEAD nodes, ancestry edges,
  readable cards and no overlapping cards after graph generation.
- [x] Open a PR targeting dev and run its required affected-layer gate. Do not
  dispatch release=true or cloud/demo deployment. Merge after required checks.
- [x] Synchronize the actual dev checkout and validate its real entrypoint.
  Close only merged temporary refs; preserve recovery branches and user data.

## Separate model-service probe

The user requested a small test after the gateway announced completion. Run
the sibling project's validate_network_models.py as a client with --scopes north
and output under ROOT outputs/data-gateway-20261025/network-models. It exercises
both formats, authenticated chunk download, full hash, SDK load and rejection
of purpose=power_flow. It does not implement Capstone model consumption, alter
gateway backend selection or run an electrical calculation.
