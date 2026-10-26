# Gateway Self-description Implementation Plan

> **For agentic workers:** Use subagent-driven-development for independent units.
> Preserve other workers' changes and user data.

**Goal:** Consume dynamically published gateway tools and semantics without
business-tool name lists or a fixed business call sequence.

**Architecture:** Keep connection trust and grants in the Application. Consume
published schemas and semantic contracts through the existing MCP bridge. Keep
specialized views and Authority result admission separate from generic calls.

**Tech Stack:** Python MCP client, JSON Schema, native Pi JavaScript bridge,
existing Thread/Attempt receipts and React views.

## Global constraints

- Owning design: `../specs/2026-10-27-gateway-self-description-design.md`.
- Do not edit sibling data-gateway or invent its unpublished metadata fields.
- No automatic retries after remote execution may have started.
- Preserve per-task grants, exact receipts, credentials and Authority boundaries.
- Use focused development checks; reuse the existing Vivaldi tab.

## Unit 1: Isolate publication checks by called tool

Files: `packages/capstone-agent/src/capstone_agent/data_gateway_mcp.py` and
`packages/capstone-agent/tests/test_data_gateway_mcp.py`.

- [x] Add regressions: add, change or remove another admitted tool after prepare;
  call the unchanged tool and assert one actual remote call.
- [x] Retain rejection tests for called-tool change/removal and forged catalog.
- [x] Replace full-catalog equality in `call` with complete called-tool equality:
  `live['tools'].get(name) != schema`. Preserve pre-call validation and grants.
- [x] Run the focused MCP tests, inspect the diff and commit this unit.

Implemented in `44228b91`; follow-up `425be8c6` keeps publication rejection
tool-scoped in both host and SDK, without automatic replay. MCP plus electrical
provider checks: 55 passed in 3.97 seconds. SDK checks: 8 passed in 0.30 seconds.

Host preparation in `5fa5a559` binds explicit task tool subsets and enforces them
on every call. The model receives only those tools. Generic guidance now uses
published preconditions and composition conditions, without electrical business
sequences. Static business admission remains until Unit 2 consumes published
permissions. These source changes are not yet rebuilt or accepted in Vivaldi.

## Unit 2: Consume published permissions and semantic discovery

Files: runtime gateway policy, `data_gateway_mcp.py`, `data_gateway_relay.py`,
`general_pi_server.py`, `native_task_context.py`, `resources/general-mcp.mjs`
and their focused tests. Final field-level edits depend on gateway publication.

- [ ] Capture the live MCP publication without secrets and map its actual
  operation permissions, semantic discovery and result contracts to the design.
- [ ] Replace business-name admission with trusted-service/grant evaluation.
  Add unknown-effect and ungranted-operation rejection tests before implementation.
- [ ] Activate on-demand discovered tools at explicit loop boundaries, retaining
  the exact task grant and contract identity. Test new tool activation without
  config edits, forged grants, revocation and stopped-task isolation.
- [ ] Replace electrical-job name special cases with the published resource-scope
  mechanism only when it can enforce equivalent ownership; keep adapter rendering
  separate. Test cross-task references and valid current-task job access.
- [ ] Preserve output schema and semantic detail availability in model context,
  using bounded references/pages instead of whole-catalog context expansion.
- [ ] Run the changed bridge, relay and admission tests and commit the unit.

## Unit 3: Real contract-only acceptance and integration

- [ ] Test multiple fresh tasks using only MCP-provided discovery and semantics;
  include valid alternative compositions and invalid joins from the design.
- [ ] Record actual tool/model counts, discovery/context size and end-to-end
  latency; do not equate successful fixtures with real agent acceptance.
- [ ] Rebuild the coherent backend change once using the canonical local command;
  verify current API/worker identity, readiness and scoped cache cleanup.
- [ ] Inspect the existing Vivaldi session, record remaining gaps, update the
  canonical status/control records, and integrate via the normal dev PR gate.
