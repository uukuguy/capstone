# Multi-Binding Application Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let one Capstone application bind and execute multiple independent Domain Packs through the real Pi path while preserving per-binding authority, credentials, state, evidence, and the existing grid compatibility interface.

**Architecture:** Keep explicit `ApplicationProfile.domains` registration. Prepare each binding into its own workspace, publish a composite tool catalog, and give Pi one application descriptor containing an ordered array of binding descriptors. Route by registered tool name, evaluate answer evidence per binding, and keep cross-binding data sharing denied in this plan. The later PyPSA model-reference plan adds a typed sharing path.

**Tech Stack:** Python 3.12, Pydantic, pytest, Node.js ESM, Node test runner, Pi, existing `capability-agent-kernel`, `@capability-agent/pi-tools`, pandapower and inventory conformance packages.

**Design:** [PyPSA Domain Packs and Multi-Binding Application Design](../specs/2026-09-25-pypsa-multibinding-domain-packs-design.md)

## Global Constraints

- Preserve the four-layer `Application -> Domain Pack -> Kernel -> registered Authority` direction.
- The `grid-agent` compatibility CLI still emits exactly one JSON object with `question_id` and `answer_output` on stdout; warnings and diagnostics go to stderr.
- Model-visible tool parameters never select endpoint, command, protocol, authority, binding, credential, or arbitrary file path.
- Binding IDs, tool prefixes, guide names, workspaces, state, credentials, output payloads, and result/evidence owners remain distinct.
- `DataSharingPolicy(mode="deny")` remains the only allowed sharing mode in this plan. The PyPSA `model_ref` handoff comes in the next plan.
- Existing `capability-agent-runtime/1.0` single-binding descriptors remain readable. Use `capability-agent-runtime/1.1` for a multi-binding descriptor.
- Do not run `make validate-provider` without separate credential and billing authorization.
- Preserve unrelated tracked/untracked work. Stage only task-owned paths, then verify the main checkout's real application entry point.

## File responsibility map

| Responsibility | Files |
| --- | --- |
| Application shape and ordered preparation | `packages/capability-agent-kernel/src/capability_agent/application/profile.py`, `application/composition.py` |
| Collision-free tool and guide registration | `packages/capability-agent-kernel/src/capability_agent/tools/catalog.py` |
| Versioned multi-binding descriptor | `packages/capability-agent-kernel/src/capability_agent/runtime/descriptor.py`, `application/runner.py` |
| Pi validation, materialization, routing | `packages/pi-capability-tools/src/domain-tools.mjs` |
| Per-binding answer admission and evidence | `packages/capability-agent-kernel/src/capability_agent/application/turns.py`, `domain/answer_admission.py` |
| Provider-free and real Pi acceptance | Existing adjacent Python and JavaScript test files, plus `packages/inventory-domain-pack/tests/test_generic_pi_transport.py` |
| Product documentation | `docs/architecture/capstone-framework.md`, `docs/guides/domain-pack-onboarding.md`, `README.md`, `README.zh-CN.md` |

---

### Task 1: Accept several complete bindings at application preparation

**Files:**
- Modify: `packages/capability-agent-kernel/src/capability_agent/application/profile.py`
- Modify: `packages/capability-agent-kernel/src/capability_agent/application/composition.py`
- Test: `packages/capability-agent-kernel/tests/application/test_contracts.py`
- Test: `packages/capability-agent-kernel/tests/application/test_application_composition.py`

**Interfaces:**
- Consumes: existing `DomainBinding`, `DomainRegistry`, `CredentialBroker`.
- Produces: `ApplicationProfile.domains: tuple[DomainBinding, ...]` with length >= 1; `prepare_application(...) -> PreparedApplication` with one `PreparedBinding` per ID.

- [ ] **Step 1: Write failing profile and preparation tests.** Extend the existing complete fixture to construct two distinct bindings with distinct registered manifest prefixes. Assert an empty tuple fails, two bindings pass, preparation order is sorted by binding ID, each gets a distinct workspace/credential lease, and a second-endpoint failure closes the first. Keep duplicate-ID and duplicate-prefix rejection tests.

  ```python
  profile = replace(complete_profile, domains=(second_binding, first_binding))
  assert tuple(binding.binding_id for binding in profile.domains) == (
      second_binding.binding_id, first_binding.binding_id
  )
  prepared = prepare_application(
      profile, registry=registry, workspace=tmp_path / "run", credentials=broker
  )
  assert set(prepared.bindings) == {first_binding.binding_id, second_binding.binding_id}
  assert prepared.bindings[first_binding.binding_id].runtime.tool_catalog_path != (
      prepared.bindings[second_binding.binding_id].runtime.tool_catalog_path
  )
  ```

- [ ] **Step 2: Run focused tests and confirm only the new multi-binding assertions fail.** Run `uv run --project packages/capability-agent-kernel pytest packages/capability-agent-kernel/tests/application/test_contracts.py packages/capability-agent-kernel/tests/application/test_application_composition.py -q`.
- [ ] **Step 3: Replace the two `len(domains) != 1` gates with `len(domains) < 1`; retain unique namespace and complete-Profile validation.** Leave `DataSharingPolicy` restricted to deny. Keep deterministic prepare/cleanup behavior.
- [ ] **Step 4: Re-run the focused tests and commit only these four files.** Expected: zero failures; commit `feat: prepare multiple application bindings`.

### Task 2: Materialize a collision-free composite catalog

**Files:**
- Modify: `packages/capability-agent-kernel/src/capability_agent/tools/catalog.py`
- Test: `packages/capability-agent-kernel/tests/tools/test_composite_catalog.py`
- Test: `packages/capability-agent-kernel/tests/application/test_application_composition.py`

**Interfaces:**
- Consumes: `CoreToolCatalog` and `tuple[BoundDomainCatalog, ...]`.
- Produces: `CompositeToolCatalog.build(...)` for one or more bindings, with a unique tool-name-to-binding map and guide bindings.

- [ ] **Step 1: Add tests for a two-binding catalog.** Check two distinct domain tools and guides resolve to their declared `binding_id`; a duplicate tool name, guide name, context tool name, binding ID, or core namespace fails before provider startup.

  ```python
  inventory = _domain("inventory", "inventory_", tool_name="inventory_asset_list", guide_tool_name="inventory_guide_open")
  grid = _domain("grid", "grid_", tool_name="grid_analysis_powerflow_ac")
  catalog = CompositeToolCatalog.build(core=CoreToolCatalog.default(namespace="agent_"), domains=(inventory, grid))
  assert catalog.require("inventory_asset_list").key.binding_id == "inventory"
  assert catalog.require("grid_analysis_powerflow_ac").key.binding_id == "grid"
  assert catalog.guide_tool_bindings["inventory_guide_open"] == "inventory"
  ```

- [ ] **Step 2: Run the focused catalog tests and observe the one-binding gate failure.** Run `uv run --project packages/capability-agent-kernel pytest packages/capability-agent-kernel/tests/tools packages/capability-agent-kernel/tests/application/test_application_composition.py -q`.
- [ ] **Step 3: Remove only the catalog's one-binding gate.** Preserve the existing unique final-name check, sorted tool materialization, and reserved `agent_` namespace check; add a nonempty-domain check.
- [ ] **Step 4: Re-run focused tests and commit.** Expected: two-binding lookup passes and all collisions fail closed; commit `feat: compose tools from multiple bindings`.

### Task 3: Serialize a versioned multi-binding runtime descriptor

**Files:**
- Modify: `packages/capability-agent-kernel/src/capability_agent/runtime/descriptor.py`
- Test: `packages/capability-agent-kernel/tests/runtime/test_descriptor.py`

**Interfaces:**
- Consumes: validated per-binding `RuntimeDescriptor` values from `descriptor_from_endpoint(...)`.
- Produces: `CompositeRuntimeDescriptor(domains: tuple[RuntimeDescriptor, ...]).as_json() -> dict[str, object]` with schema `capability-agent-runtime/1.1`; `write_runtime_descriptor` accepts either descriptor type.

- [ ] **Step 1: Test one-binding v1 byte/shape compatibility and a two-binding v1.1 payload.** Require identical application ID, run ID, application workspace, and core capture paths across members; require unique binding IDs, guide names and tool prefixes. Reject paths escaping each binding workspace and any inconsistent shared core path.

  ```python
  composite = CompositeRuntimeDescriptor(domains=(grid_descriptor, inventory_descriptor))
  payload = composite.as_json()
  assert payload["schema"] == "capability-agent-runtime/1.1"
  assert [item["bindingId"] for item in payload["domains"]] == ["grid", "inventory"]
  assert grid_descriptor.as_json()["schema"] == "capability-agent-runtime/1.0"
  ```

- [ ] **Step 2: Run descriptor tests and confirm the new type is missing.** Run `uv run --project packages/capability-agent-kernel pytest packages/capability-agent-kernel/tests/runtime -q`.
- [ ] **Step 3: Extract a private `RuntimeDescriptor` domain serializer, then add `CompositeRuntimeDescriptor`.** Reuse current path, digest and endpoint validation for each member. Do not construct JSON by mutating a v1 payload after validation. Keep the v1 `as_json()` result unchanged.
- [ ] **Step 4: Re-run tests and commit.** Expected: v1 regression and v1.1 security cases pass; commit `feat: serialize multi-binding runtime descriptor`.

### Task 4: Register and route all selected Pi tools

**Files:**
- Modify: `packages/pi-capability-tools/src/domain-tools.mjs`
- Test: `packages/pi-capability-tools/test/domain-tools.test.mjs`

**Interfaces:**
- Consumes: `capability-agent-runtime/1.0` with one domain or `/1.1` with a nonempty `domains` array.
- Produces: one frozen validated runtime, one model-request capture registration, one pair of core tools, and one capability/guide tool group per domain.

- [ ] **Step 1: Add a two-domain descriptor fixture and failing tests.** The fixture has separate catalog/guide roots and executables. Assert both tools register and call only their own runner, both guide tools read only their own roots, core tools register once, and duplicate names, swapped paths, undeclared binding or endpoint fields in model parameters fail.

  ```js
  const runtime = validateRuntimeDescriptor({
    schema: "capability-agent-runtime/1.1",
    application,
    core,
    domains: [gridDomain, inventoryDomain],
  });
  assert.equal(runtime.domains.length, 2);
  assert.equal(runtime.domains[0].bindingId, "grid");
  assert.equal(runtime.domains[1].bindingId, "inventory");
  ```

- [ ] **Step 2: Run `node --test packages/pi-capability-tools/test/domain-tools.test.mjs` and observe the exact-one-domain failure.**
- [ ] **Step 3: Add `/1.1` validation and replace `selectedBindingRuntime` use at extension registration with an ordered loop over validated bindings.** Keep `buildCapabilityRequest` and `createCapabilityTool` bound to a selected immutable domain runtime. Configure capture and core context/decision tools once, outside the loop. Validate all catalogs and guide digests before any registration.
- [ ] **Step 4: Re-run the JavaScript tests and commit.** Expected: v1, legacy and v1.1 cases pass; commit `feat: route multiple domain tools in Pi`.

### Task 5: Wire the default application Pi path to the composite descriptor

**Files:**
- Modify: `packages/capability-agent-kernel/src/capability_agent/application/runner.py`
- Test: `packages/capability-agent-kernel/tests/application/test_runner.py`
- Test: `packages/inventory-domain-pack/tests/test_generic_pi_transport.py`

**Interfaces:**
- Consumes: prepared bindings and `CompositeRuntimeDescriptor` from Task 3.
- Produces: `AgentApplication._default_pi_transport(...)` that launches one Pi session with a v1.1 descriptor when multiple bindings are selected. The existing one-binding path stays v1.

- [ ] **Step 1: Test that a two-binding default provider path writes one v1.1 descriptor containing both catalog/guide paths.** Assert `RuntimePaths.binding_id`, `tool_catalog_path`, and `guide_index_path` are unset for multi-binding launches so no ambient single-domain routing leaks into Pi. Assert existing one-binding runtime paths and descriptor stay unchanged.
- [ ] **Step 2: Run focused runner and inventory Pi transport tests and confirm the default Pi `len(bindings) != 1` failure.** Run `uv run --project packages/capability-agent-kernel pytest packages/capability-agent-kernel/tests/application/test_runner.py -q` and `uv run --project packages/inventory-domain-pack pytest packages/inventory-domain-pack/tests/test_generic_pi_transport.py -q`.
- [ ] **Step 3: Build one per-binding descriptor in sorted binding order and serialize through `CompositeRuntimeDescriptor`.** Put the composite descriptor and Pi session under the application run's `core` runtime directory. Populate `RuntimePaths.domain_search_paths` from the validated union of per-binding search paths; use the descriptor as the only multi-binding routing source.
- [ ] **Step 4: Re-run focused tests and commit.** Expected: both bindings reach the default Pi extension with no legacy environment selector; commit `feat: launch multi-binding Pi application`.

### Task 6: Admit a multi-source answer without weakening evidence ownership

**Files:**
- Modify: `packages/capability-agent-kernel/src/capability_agent/application/turns.py`
- Modify: `packages/capability-agent-kernel/src/capability_agent/domain/answer_admission.py`
- Test: `packages/capability-agent-kernel/tests/application/test_turns.py`
- Test: `packages/capability-agent-kernel/tests/application/test_runner.py`

**Interfaces:**
- Consumes: current-turn result/evidence ownership, per-binding `AnswerAdmissionDecision`.
- Produces: an application-level aggregate decision and a versioned sidecar that records per-binding decisions; `read_answer_admission_metadata(...)` remains compatible with sidecar `/1.0` and `/1.1`.

- [ ] **Step 1: Add tests for two distinct current-turn binding references and two claims, each owned by one binding.** Assert both authorities validate only their own refs. Reject one claim containing refs from two owners, unknown bindings, missing current-turn refs, and an unqualified claim with two selected bindings. A mixed assured/limited evaluation must keep the submitted answer and report limited aggregate assurance, with both per-binding results retained.

  ```python
  finalized = controller.submit(
      handle,
      answer_output="Both systems were checked.",
      referenced_bindings=("grid", "inventory"),
      result_refs=(grid_result_ref, inventory_result_ref),
      evidence_refs=(grid_evidence_ref, inventory_evidence_ref),
      claims=(grid_claim, inventory_claim),
      duration_seconds=0.1,
  )
  assert finalized.referenced_bindings == ("grid", "inventory")
  ```

- [ ] **Step 2: Run focused turn/controller tests and confirm the new assurance assertion fails.** The current `_admit_answer` exact-one guard is caught by the advisory fallback and produces `limited`, so the test should expect a verified two-binding decision and fail on that assertion. Run `uv run --project packages/capability-agent-kernel pytest packages/capability-agent-kernel/tests/application -q`.
- [ ] **Step 3: Collect and validate one admission decision per selected binding, then compute a conservative aggregate.** Aggregate as `authority_backed/lineage_verified` only if every decision is lineage verified; as `offline_information/<same assurance>` only if every decision has that identical offline assurance; otherwise use `limited/limited`. Record a new `capability-agent-answer-admission/1.2` sidecar with an ordered `bindings` object whose entries contain `mode`, `assurance`, and `diagnostic_codes`, plus the existing answer/run/turn digest binding. Keep single-binding sidecars on their present schema and the primary answer commit independent of advisory evaluation failures.
- [ ] **Step 4: Re-run focused tests and commit.** Expected: two-source commit and replay pass; cross-owner claim and tampered sidecar fail; commit `feat: admit evidence from multiple bindings`.

### Task 7: Prove real two-binding composition and update product documentation

**Files:**
- Test: `packages/inventory-domain-pack/tests/test_multi_binding_application.py` (new)
- Test: `packages/pi-capability-tools/test/domain-tools.test.mjs`
- Modify: `docs/architecture/capstone-framework.md`
- Modify: `docs/guides/domain-pack-onboarding.md`
- Modify: `README.md`
- Modify: `README.zh-CN.md`

**Interfaces:**
- Consumes: Tasks 1–6 and the existing pandapower/inventory registered authorities.
- Produces: a provider-free two-turn application conformance path using both real authorities, a default Pi extension smoke, and accurate published multi-binding documentation.

- [ ] **Step 1: Add a scripted two-turn acceptance test.** Assemble pandapower and inventory bindings explicitly. In turn one, call one real tool from each binding, then commit two separately owned claims. In turn two, reuse allowed bounded context, call both authorities again, commit, build report, and replay. Assert each `domains.<binding_id>` payload and current-run evidence belongs to its binding.
- [ ] **Step 2: Add a real default Pi startup smoke with both catalogs and guides.** Use the repository's managed Pi runtime after `make setup`, `make install-pi`, and `make doctor` in an isolated worktree. Assert Pi exposes both namespaced tool sets and one `agent_` core set; no external provider call is needed.
- [ ] **Step 3: Update architecture, onboarding, and both READMEs together.** State that explicit multi-binding assembly works and sharing remains denied until the separately planned model-ref handoff. Keep README headings, commands and shared facts aligned; retain grid CLI compatibility wording.
- [ ] **Step 4: Run the repository gates.** Run focused Python/Node tests first, then `make doctor`, `make test`, `make test-e2e`, `make validate`, `make test-packages`, `git diff --check`, and `test -L CLAUDE.md`. Expected: all exit 0; the real `grid-agent run --offline` stdout still has exactly the two compatible fields.
- [ ] **Step 5: Integrate accepted commits into the main checkout and verify its real application entry point.** Preserve unrelated work and commit only these task-owned paths with `feat: verify multi-binding application composition`.

## Program sequence after this plan

Passing Task 7 proves independent multi-binding composition. It does not enable
sharing a `model_ref`. Each following row becomes its own detailed implementation
plan before code changes; its exit gate is independently reviewable.

| Order | Distribution(s) | Required result and exit gate |
| --- | --- | --- |
| 2 | PyPSA authority distribution and `pypsa-network-modeling-domain-pack` | A registered, pinned PyPSA authority stores immutable models; typed model creation/derivation/inspection produces current-run `model_ref`; a source-to-target handoff receipt is checked by policy and authority. Two-turn installed-wheel acceptance proves one authorized handoff, and stale/foreign-run/wrong-target/tampered refs fail. |
| 3 | `pypsa-power-operations-domain-pack` | Fixed-model dispatch, unit commitment, selected security-constrained OPF, and dispatch-to-AC-validation are separately published only after real solver calls, per-result objective/status typing, evidence, replay, and an application acceptance using the modeling pack. |
| 4 | `pypsa-capacity-planning-domain-pack` | Capacity expansion, multi-period and stochastic planning, MGA, and a capacity-plus-commitment workflow have distinct objective and scenario contracts; planning-to-operation handoff retains model revision and investment lineage. |
| 5 | `pypsa-sector-coupling-domain-pack` | Curated cross-carrier model patches and energy-balance results are published after a model-to-planning-to-sector workflow proves carrier units, conversion signs, revision lineage, and evidence. |

The three later PyPSA pack names may be reserved as buildable package shells in
Order 2, with a coverage manifest marking every operation `planned`. A shell
has no runtime Profile, registered capability, or application binding. Each
later order adds its own exact version pin, semantic contracts, focused tests,
clean-wheel conformance, repository gates, and main-checkout entry-point check.
