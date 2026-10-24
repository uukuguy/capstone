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
Status: user approved execution. Adapter and native integration are implemented
on feat/enterprise-data-gateway through e39fd6c3, with focused host/SDK checks.
Actual pinned child SDK/HTTP relay/host receipt passes. Real MCP direct discovery,
object/metric/source lookup and five-point query/statistics pass. Local canonical
rebuild and model-driven multi-turn acceptance are in progress, not yet passed.
Execute sequentially in feat/enterprise-data-gateway; do not dispatch agents.

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

- [ ] Write failing tests for missing/disabled configuration, valid authenticated
  discovery, rejected malformed URL/headers, duplicate names, unlisted tools,
  excluded model operations and schema changes after catalog acceptance.
- [ ] Run the focused test file and confirm the new-module failure.
- [ ] Implement the smallest adapter using the already installed MCP client.
  Validate JSON Schema locally without remote reference retrieval. Fixed URL and
  headers come exclusively from the protected connection file.
- [ ] Run the focused file again. Add a secret-canary assertion across every
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

- [ ] Write failing relay tests: another task's grant, expired/revoked grant,
  changed arguments schema, unadmitted tool and model tool are refused.
- [ ] Add cancellation/timeout tests proving upstream completion is not silently
  replayed, and configured-offline state is not published as ready.
- [ ] Add the gateway capability to native context only for enterprise-research
  and only after catalog preparation. Keep existing resource checks intact.
- [ ] Implement bounded requests and credential-free public errors. Confirm no
  endpoint or credential selector is accepted in task payloads.
- [ ] Run new relay tests plus existing general Pi relay and native context tests.
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

- [ ] Write failing tests for actual SDK inventory and allowed_tools agreement,
  including a research child node calling a gateway tool.
- [ ] Verify a fabricated or cross-task receipt is rejected; a valid partial
  gateway response keeps its gaps/provenance and becomes an admitted source.
- [ ] Implement SDK registration and node propagation through the existing
  protected configuration path. Never include upstream credentials.
- [ ] Add explicit gateway receipt admission without loosening the existing
  PowerMCP descriptor/source checks. Persist result bytes through current source
  and artifact mechanisms; keep model prose separate from service facts.
- [ ] Run focused Python and JS tests, existing MCP tests, research runtime
  tests and package-boundary checks. Inspect and commit the complete slice.

## Task 4: Local configuration and real task acceptance

Files to modify:
- compose.yaml: existing general-pi host configuration and protected mount.
- deploy/local.env.example and docs/RUNBOOK.md for protected host file mounting.
Files to create:
- scripts/verify_data_gateway_research.py: real MCP plus App-task verification
  with sanitized receipts, no credential CLI arguments.
- docs/reviews/2026-10-25-enterprise-data-gateway.md: measured acceptance record.

- [ ] Mount the operator connection file read-only in the native host only. The
  browser and native task UIDs must not gain access to it.
- [ ] Exercise capability discovery and one bounded data query using identities
  returned by the gateway. Save full response bytes in ignored run storage.
- [ ] Run make capstone-local-rebuild from the accepted candidate checkout.
  Check readiness and all participating API/worker identities.
- [ ] Submit one real enterprise-research request that discovers data, retrieves
  a bounded window, computes a supported comparison and saves a sourced report.
  No copied answer values or prefilled data fixture may replace tool execution.
- [ ] Ask a follow-up against that same Thread; refresh in a browser and verify
  source records and report bytes remain accessible. Exercise semantic table
  prepare/execute using its actual returned validation fingerprint in a second
  bounded task. Record genuine partial/unavailable outcomes faithfully.
- [ ] Record durations, model/tool counts and exact receipts. Run the scoped
  build-cache cleanup after validation. Commit documentation and verified source.

## Task 5: Dev integration and control closure

- [ ] Update CURRENT-STATE, RESUME-NEXT-SESSION and JOURNAL with exact implemented,
  verified and deferred scope. Update VERSION-CONTROL and regenerate its graph.
- [ ] Use ui-ux-pro-max and a browser to verify current HEAD nodes, ancestry edges,
  readable cards and no overlapping cards after graph generation.
- [ ] Open a PR targeting dev and run its required affected-layer gate. Do not
  dispatch release=true or cloud/demo deployment. Merge after required checks.
- [ ] Synchronize the actual dev checkout and validate its real entrypoint.
  Close only merged temporary refs; preserve recovery branches and user data.

## Separate model-service probe

The user requested a small test after the gateway announced completion. Run
the sibling project's validate_network_models.py as a client with --scopes north
and output under ROOT outputs/data-gateway-20261025/network-models. It exercises
both formats, authenticated chunk download, full hash, SDK load and rejection
of purpose=power_flow. It does not implement Capstone model consumption, alter
gateway backend selection or run an electrical calculation.
