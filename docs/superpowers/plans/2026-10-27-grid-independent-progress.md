# Grid and gateway work independent of the next MCP publication

Status 2026-10-27: bounded tool discovery/activation is implemented and verified
through PR69 (`bcd1a5ad`); non-diagram MCP work and Vivaldi product recovery passed.
Authority/broker groundwork is retained; public power-flow integration remains
deferred. Diagram v2, provincial drilldown and query-location acceptance remain
paused under the user's non-diagram-first priority. The user now reports Beijing,
Tianjin, Shanghai, Hubei and Zhejiang grids ready at the gateway. This is gateway
readiness reported by the user, not Capstone diagram acceptance. Use MCP discovery
and the shared viewer when this work resumes; do not hard-code province routes.

> **For agentic workers:** Use subagent-driven-development for the independent
> Authority, menu and diagram units. Preserve other workers' changes.

**Goal:** Complete useful electrical-view and model-import work while the gateway
publishes its next semantic contract. Prepare bounded tool loading without
inventing gateway fields.

**Architecture:** Application-owned artifact transfer and task grants feed a
registered Authority import capability. Native Pi loads only task-authorized tool
schemas on demand. The existing electrical viewer consumes published frozen views.

**Tech stack:** Python/MCP/JSON Schema, pandapower 3.4.0 Authority, Pi SDK and React.

## Constraints

- User approved this work on 2026-10-27; no extra approval gate is introduced.
- Existing Authority admission design governs safe JSON decoding, archive limits,
  typed map identities, demo provenance, task binding and atomic context commit.
- Never modify sibling data-gateway; its files may be read for developer reference.
- Never run a solver through the general executor or fabricate source parameters.
- Real diagram checks use the existing Vivaldi page; no new tabs.
- Record source checks, current-image baseline checks and rebuilt acceptance separately.

## 1. Registered Authority import

Owner: `packages/grid-simulator/src/grid_simulator/` and its tests/resources.

- [ ] Add rejection tests for unsafe object/path JSON, ZIP traversal/links/duplicates,
  corrupt hashes, typed-key mismatch, foreign/revoked/expired grants and map drift.
- [ ] Add a fixed data-only decoder for the supported gateway pandapower tables.
- [ ] Add `model.artifact.import {input_ref}` with a host-installed task binding
  and content-addressed archive/grant inputs. Commit context last.
- [ ] Preserve imported model/revision/map provenance across reload and existing
  analysis/ranking operations. Validate actual demo bundle without claiming real
  operating conditions; persist convergence or failure evidence.

## 2. Application artifact broker and Pack adapter

Owner: new `packages/capstone-agent/src/capstone_agent/gateway_model_artifact.py`,
focused tests and necessary pandapower Domain Pack adapter points.

- [ ] Consume the existing published metadata/chunk contracts behind a fixed
  trusted transport. Stream to private storage; verify identity, offsets, byte
  counts and full digest, without file payloads in model context.
- [ ] Provision the Authority's agreed opaque grant and execution binding; no
  caller paths, credentials or endpoints. Add interrupted-transfer/no-grant tests.
- [ ] Connect only through the selected Pack/Authority capability and retain exact
  imported mapping/quality metadata. No general research permission is implied.

## 3. Bounded tool discovery and activation

Owner: native gateway JS adapter and focused SDK tests; host wiring coordinated
with the application owner.

- [ ] Expose bounded search over already-authorized published descriptions and
  explicit selection of detailed schemas. Do not add business-name routing.
- [ ] Activate tools only within the task grant at a model-loop boundary; keep
  receipt validation, cancellation and failed-call no-replay semantics.
- [ ] Test search, activate then call, invalid names, context budgets and separate
  tasks. Published semantic discovery remains a later adapter, not guessed fields.

## 4. Existing diagram acceptance and integration

- [ ] Read North/East views with bounded preparation checks, exact frozen identity,
  group pagination and all eight streams. Record gaps rather than invent edges.
- [ ] Check existing Vivaldi page for symbols, drilldown, details and restore.
- [ ] Run changed-layer tests, inspect diffs, commit task-owned paths and review
  the combined boundary. Rebuild once after the coherent backend unit.
- [ ] Verify current-image identity/readiness, real tasks, cleanup and canonical
  status records. Integrate through dev PR; do not claim deployment from source tests.
