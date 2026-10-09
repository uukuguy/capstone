# Business Workspace and Agent Resources Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Deliver shared business context, usable native skills/MCP resources in all three Pi roles, and useful input commands.

**Architecture:** The application projects a shared business workspace into immutable task inputs. Pi-native resources have role-specific activation and adapters; Domain Packs remain exclusive to Capstone. Public operations and typed input drive the common App.

**Tech Stack:** Existing Python application/ledger, fixed Pi TypeScript runtime, React/assistant-ui App, registered authorities, isolated native executor and MCP stdio adapters.

**Approved spec:** [Design](../specs/2026-10-09-business-workspace-agent-resources-design.md), approved by the user on 2026-10-09. The user also selected PowerSkills pandapower and PowerMCP as actual integration samples and requires direct Harness enhancement to be assessed and implemented where compatible.

## Global Constraints

- Domain Packs are visible only inside Capstone Agent; delegated Pi and direct Pi receive public business context only.
- Preserve Application → Domain Pack → Kernel → registered Authority ownership and current-run evidence admission.
- No keyword intent selection or fallback. Direct Pi selects business context without entering professional Harness execution.
- Keep Pi-native skill/package/extension configuration; Capstone metadata records role compatibility and adapters, not a second skill format.
- No arbitrary shell, file access or caller-selected endpoints in professional Harness. Native Pi operates only in its isolated task environment.
- Ordinary questions omit unrelated business context. Mixed tasks receive per-goal projections. Direct professional questions receive relevant session objects and materials.
- Context text limit 24 KiB; at most 16 objects and 8 materials. Material size at most 4 MiB, aggregate at most 16 MiB. Task JSON remains at most 256 KiB.
- Public interfaces never expose credentials or Authority internals. Historical or MCP observations do not self-admit as current-run professional evidence.
- Freeze resource versions and business snapshots on acceptance; never silently change them on retry.
- Preserve existing dirty work and main `var/` data. Work in `.worktrees/business-workspace-resources`, integrate to main after review, and rebuild the real local entry point.
- No third-party personal configuration changes. Selected samples may be fetched and installed in project-managed isolated runtimes. Paid Provider calls and remote deployments require separate authorization.

## Delivery map

| Task | Package | Owned deliverable |
| --- | --- | --- |
| 1 | A | Public business context and versioned Pi task contracts |
| 2 | A | Semantic selection, frozen hosted wiring and native context delivery |
| 3 | B | Native resource installation, role profiles and real sample receipts |
| 4 | B | Native input and executable skill/MCP adapters |
| 5 | B | Direct Harness skill integration and Authority-backed MCP structural audit |
| 6 | C | Public operations, capability UI and typed slash/context inputs |
| 7 | A–C | Cross-role actual-entry validation, review, main integration and rebuild |

## Task 1: Public business context and Pi task v2

**Files:** Create `packages/capstone-agent/src/capstone_agent/business_context.py`; modify `pi_delegation.py` in that directory; create `packages/capstone-agent/tests/test_business_context.py`; extend `test_pi_delegation.py`.

**Interfaces:**

```python
@dataclass(frozen=True, slots=True, init=False)
class BusinessContext:
    @classmethod
    def from_document(cls, document: dict) -> "BusinessContext": ...
    @classmethod
    def empty(cls, workspace_id: str, history_cutoff: int) -> "BusinessContext": ...
    def to_document(self) -> dict: ...

def business_context_for(request: IntentRequest, decision: IntentDecision,
                         *, goal_id: str | None = None) -> BusinessContext: ...
```

The document has exactly schema/workspace_id/snapshot_id/history_cutoff/selection/object_refs/goals/constraints/materials/outcomes/coverage. Schema is `capstone-business-context/1`. Selection has `state` (`none`, `selected`, `needs_clarification`) and `source` (`semantic`, `explicit`). Objects have public `object_id`, `display_name`, `kind`, `version`, `relation` and `source`; never copy enabled profiles or raw authority identifiers. Map current/historical IntentRequest objects and selected goal object_refs into this public form. Snapshot is a canonical SHA-256 content identity excluding the snapshot_id itself. Unknown selection refs fail. Use request.thread_id as workspace_id; an empty projection has empty business lists. Do not serialize diagnostic goal prose as instructions.

Materials and outcomes use explicit bounded schemas with public provenance. Keep immutable deep copies and reject nonfinite, oversized, unknown/protected fields. Coverage describes provided/omitted refs and truncation; required context is not silently truncated. A capability-only professional intent with no object reference does not infer objects by keyword.

Extend PiTaskRequest with optional keyword-compatible `business_context`, `resource_profile`, `input` fields. All absent preserves exact `/1` serialization and existing positional construction. All present emits `/2`; partial new fields fail. `input` is `{kind:'text',text:instruction}` or `{kind:'skill_invocation',text:instruction,skill_id,skill_version}`. `resource_profile` has `profile_id`, `revision`. Text must match instruction. Validate BusinessContext separately without weakening protected generic JSON validation. Results remain existing host-issued result semantics.

- [ ] Write tests for empty ordinary projection, selected current/historical object, unknown refs, immutable export, bounds, invalid versions/provenance and injected protected fields.
- [ ] Run the new tests and record the expected failure before implementation.
- [ ] Implement canonical context validation and selected-object projection.
- [ ] Add `/2` round-trip tests while preserving `/1`; reject partial fields, input mismatch, overlarge total envelope and forged result evidence.
- [ ] Run `uv run --project packages/capstone-agent pytest -q packages/capstone-agent/tests/test_business_context.py packages/capstone-agent/tests/test_pi_delegation.py`.
- [ ] Commit only owned paths; record RED/GREEN evidence and interfaces in the task report.

Example acceptance assertion:

```python
document = business_context_for(request, decision, goal_id='g1').to_document()
assert document['object_refs'][0]['display_name'] == 'ieee39'
assert document['object_refs'][0]['version']
assert 'enabled_profiles' not in repr(document)
assert request.to_document()['objects'][0]['model_revision'] not in repr(document)
```

## Task 2: Hosted selection and native context delivery

**Files:** Modify `intent_runtime.py`, `delegated_runtime.py`, `pi_intent.py`, `general_pi_server.py`, `general_executor_composition.py`, `resources/general-context.mjs`; create `context_selection.py` and `resources/context-selection.mjs` for the dedicated native decision tool. Update `deploy/general-pi.Dockerfile` to include new required contract modules. Extend `test_intent_runtime.py`, `test_delegated_runtime.py`, `test_general_pi_server.py`, `test_pi_intent.py` and `test_general_pi_native.py`.

**Interfaces:** Consume Task 1 BusinessContext and PiTaskRequest v2. Frozen direct resources store a source request, checked semantic selection and context snapshot. Delegated goals each derive context from the accepted decision; source request is immutable. General executor advertises `task_schemas` in its capability descriptor. Existing `/1` recovery remains supported.

Direct selection uses a dedicated model decision contract containing selected object/message references and clarification state, without Domain Pack capability names. Reuse the existing intent engine lifecycle/deadline/freeze plumbing, but keep direct selection independent of professional goal authorization. Native builder can expose `build_context_selection` using the managed configuration and exact bounded reference enums. Do not send the full professional IntentRequest to a direct Pi executor. Freeze decision using both ledgers; retry must use saved selection and original task identity.

- [ ] Add failing tests: direct ordinary empty context; direct line query selects current object; direct historical reference selects old object; delegated mixed goals receive distinct relevant projections.
- [ ] Implement native semantic selector and deterministic validation; no topic matching. Preserve current native config conventions.
- [ ] Wire task v2 and capability negotiation. A server without v2 rejects required context instead of dropping it.
- [ ] Add business_context to private native context.json and trusted context extension, preserving history roles and separating data from instructions.
- [ ] Test failed selection, retry after model/resource change, unknown references and domain-content exclusion.
- [ ] Run focused Python tests plus native extension checks; commit and report.

```python
assert direct_request.business_context.to_document()['selection']['state'] == 'selected'
assert direct_request.entrypoint == 'direct'
assert not business_factory_calls
assert retry_request.business_context == original_request.business_context
```

## Task 3: Native resource profiles and selected sample installation

**Files:** Extend `runtime_capabilities.py`; create `runtime_resources.py`, `resource_installation.py`, and focused tests in `packages/capstone-agent`. Add `configs/runtime/agent-resources.json`, versioned sample lock metadata and a project setup entry under `tools/`. Add a sample receipt under `docs/reviews/`.

**Interfaces:** `resolve_resource_profile(config_root: Path, role: str) -> ResolvedResourceProfile` provides profile_id/revision, native settings paths, resource descriptors, ready/unavailable reasons and loaded identities. Roles are harness_engine/delegated_pi/direct_pi. Existing RuntimeCapabilityDescriptor consumers remain compatible. Publish immutable resource catalog documents with id/kind/version/source/roles/enabled/ready/reason and required tool IDs; no credentials or local private paths.

Use user-selected sources, pinned to fetched commits: PowerSkills `05bda3a51d5f1ecad888d4d4663c28478c643a7e`, skill path `powerskills-tool/skills/pandapower`; PowerMCP `63341e67ce6ae5650396ab92b2be7f86e3409da1`, pandapower server. Verify these refs and manifests before installation. Keep upstream content in ignored managed storage; keep hashes/source/declared dependencies in versioned configuration. Do not run upstream installer that edits personal client configs.

- [ ] Write failing tests for immutable role resolution, missing dependencies, disabled resources, version changes, path escape and duplicate skill names.
- [ ] Implement native settings/resource discovery using fixed Pi conventions. Capstone metadata only adds roles, required tools and adapter identity.
- [ ] Implement explicit managed fetch/install command with pinned refs and isolated Python dependencies. Existing installed version survives a failed install. No task-time dependency download.
- [ ] Fetch and inspect actual upstream skill, bundled case and server code. Record direct-Harness compatibility: reusable workflow, mismatched tool names, script-only operations, schema/provenance requirements.
- [ ] Run actual sample server tools/list and one bounded read/solve sequence in a private runtime through MCP; store receipt with input hashes and dependency versions. Do not present its sample network as current Capstone model.
- [ ] Verify role profile loading, commit owned source/config/tests/receipt paths and report limitations precisely.

## Task 4: Native executable skills/MCP and typed input

**Files:** Create bounded MCP adapter and role dispatch modules under `packages/capstone-agent/src/capstone_agent/`; add managed Pi SDK input/skill/MCP extensions under its `resources/`; modify `general_pi_executor.py`, `general_pi_server.py`, and professional runtime composition as needed. Add a focused skill adapter under the pandapower Domain Pack when tool semantics belong there; tests beside each owner.

**Interfaces:** Plain input disables native command expansion; explicit validated skill invocation binds exact skill/version and uses native skill loading. MCP connection receives an operator-configured server and publishes exact selected schemas; per-task server state, deadlines and cancellation are isolated. Direct Harness adapter publishes only semantic tools, no shell/file/endpoint tool.

- [ ] Test literal `/...` remains text and skill invocation uses pinned native content. Use Pi SDK `session.prompt` with expandPromptTemplates false for text, true only for validated skill command after collision checks.
- [ ] Implement bounded MCP initialize/list/call lifecycle with actual fixed SDK/protocol support. Validate tool name/schema and result bounds; report unknown side-effect outcome without retry.
- [ ] Connect native Pi tools through a managed extension. Test discovery plus real PowerMCP tool call through Pi with a loopback model response.
- [ ] Validate cross-role isolation, external observation identity, cancellation, missing dependencies and resource version mismatch. Commit and report direct, adapted and delegated-only capability results separately.

## Task 5: Direct professional skill and MCP enhancement

**Files:** Add `packages/grid-simulator/src/grid_simulator/bindings/powermcp_audit.py` and an Authority-owned runner; update `bindings/__init__.py`, analysis registry metadata and result table declarations as needed. Add an original adapter guide to `packages/pandapower-domain-pack/src/pandapower_domain/resources/guides/`, hook actual role/skill loading and tests. Authority code never imports `capstone_agent` or the Kernel.

**Interfaces:** Publish reusable `diagnostic.structural` through the existing `analysis.run` semantic contract. The operator configures a pinned PowerMCP Python/runtime and server; no path/command/endpoint is supplied by the model. The Authority takes its own selected model snapshot, exports a private JSON copy, starts an isolated MCP process, invokes `load_network` then `audit_network`, validates the exact output and records results through existing ResultStore/evidence admission.

```python
AnalysisOperation('diagnostic.structural', 'Structural network audit',
                  'powermcp.audit_network', closed_schema({}), run)
```

- [ ] Write failing Authority tests for a model-bound successful structural audit, unavailable runtime, malformed upstream result, timeout, context/revision mismatch and no model mutation.
- [ ] Implement bounded subprocess/MCP lifecycle and validate pinned runtime/server identity. `res_structural_audit` stores typed severity/code/message/element/index findings; metadata includes upstream commit, tool schema hashes, input digest, runtime versions and count/status. No raw upstream object crosses Authority boundary. Pin the sidecar to pandapower3.4.0 as well, which upstream permits, to avoid silent snapshot conversion by a different library version.
- [ ] Let existing `analysis.run` bind context/revision and persist result/evidence. Explicitly expose missing dependency as unavailable; never fabricate an empty successful audit. Keep grid-simulator pandapower3.4.0 pin; external solver version is recorded separately.
- [ ] Mark result field provenance as PowerMCP, not pandapower's native result columns. Validate structural audit coverage, including topology dependencies; upstream's omitted topology check cannot become a successful complete audit. Sanitize the runner parent environment because MCP stdio SDK inherits selected parent variables.
- [ ] Author a concise Capstone adapter guide based on upstream workflow concepts; do not vendor unlicensed PowerSkills text. Bind its declared operations to existing published gridctl tools plus optional structural audit, with truthful missing-operation status.
- [ ] Prove a Harness task actually loads the selected guide and calls the semantic tool, whose Authority backend actually calls PowerMCP. This is distinct from delegated Pi execution.
- [ ] Run focused simulator/pack/Harness checks and real isolated MCP sample; commit and report.

## Task 6: Shared operations and useful input controls

**Files:** Add resource/operation/context API projections in `thread_application.py`, `thread_http_api.py` and focused modules; extend existing command and thread client/protocol; add `ThreadCommandMenu.tsx`, `ThreadContextPanel.tsx`, resource selection components and tests under `packages/capstone-app/src/`; integrate Composer and existing themed controls.

**Interfaces:** Public operations include id/scope/input schema/role/availability/reason/revision. Input submission carries typed text or skill invocation and explicit context selection. Backend validates from accepted resource/operation snapshot. Context previews bind draft hash, workspace snapshot and configuration revision.

- [ ] Add tests for role-independent public model/data actions and role-dependent execution operations; server rejects stale catalog claims.
- [ ] Implement `/skills`, `/skill:<name>` and `/context` only. First two discover/bind actual ready skills; context shows relevant public objects/materials, explicit includes/excludes and optional semantic preview.
- [ ] Preserve original draft, selected mode and task skill metadata across reconnects and failed receipt recovery; use existing command idempotency protocol.
- [ ] Implement keyboard completion, IME guard, Escape/outside dismissal and touch operation. Completion Enter must not also submit. No automatic command parsing in paths/code/body text.
- [ ] Test mode change invalidates incompatible pending skill without erasing text; context changes invalidate preview; API reports actual accepted context in details.
- [ ] Remove blanket Pi disablement for common application operations. Do not enable Case/calculation without corresponding runtime capability.
- [ ] Run focused App tests/types and API tests; commit and report.

## Task 7: Integration, actual entry verification and delivery

**Files:** Extend provider-free validation scripts/tests; update architecture/runbook and bilingual product facts; create `docs/reviews/2026-10-09-business-workspace-resources-verification.md`.

- [ ] Validate approved scenario matrix: unrelated ordinary/weather, business-related weather, selected/historical model, mixed goals, resource availability, real skill/MCP calls, source identity, revision change, unknown slash and mobile draft preservation.
- [ ] Run Capstone tests/types/boundaries, App tests/types, required integration/package gates and isolated PostgreSQL checks. Record skipped optional paid/remote checks.
- [ ] Obtain task reviews and final whole-change review; fix Important/Critical findings with covering tests.
- [ ] Integrate accepted commits to main without overwriting pre-existing dirty files or runtime data.
- [ ] Run `make capstone-local-rebuild` from main, verify API/worker source identity and App readiness, and exercise actual two entry points with controlled Provider responses and real sample tools.
- [ ] Update current architecture for allowed public material copies and direct context selection. Align README/README.zh-CN if product facts change. Record exact verified versions and limits.

## Progress and review evidence

Task reports and diff packages live under ignored `.superpowers/sdd/business-workspace/`.
The main checkout JOURNAL owns durable decisions and commit records; workers do not modify pre-existing status documents.
Each task gets an independent spec/quality review before completion. Final review covers the entire implementation range.
