# Workstream C Inventory Reference Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an independently packaged read-only inventory authority and Domain Pack that execute through the unchanged kernel and generic Pi transport.

**Architecture:** `inventory-reference-service` owns registered inventory data, deterministic calculations, current-run artifacts, and the `inventory-capability/1.0` executable. `inventory-domain-pack` owns installed contracts, guides, policy, executor, artifact-authority adapter, projectors, and the public `DomainRuntimeProfile`; provider-free integration tests exercise the existing generic Pi transport without modifying protected framework paths.

**Tech Stack:** Python 3.12, Pydantic 2, Typer, pytest 9, Hatchling, uv, Node 22, `@capability-agent/pi-tools`, Make, climb tracked state.

## Global Constraints

- Do not modify `packages/capability-agent-kernel/`, `packages/pi-capability-tools/`, kernel event/replay modules, or `packages/trajectory-workbench/`.
- Preserve the existing `grid-agent` stdout envelope, `gridctl`, `grid-capability/1.0`, `grid_*` tools, runs, and current-run evidence behavior.
- Inventory is read-only: no mutations, approvals, tenant routing, idempotency, compensation, or asynchronous operations.
- The model receives only semantic `inventory_*` tools plus bounded guide/context/decision tools; never expose shell, generic files, Python, or raw catalog objects.
- Domain facts originate at `inventoryctl` and are admitted only through `InventoryArtifactAuthority` for the current run.
- Every task uses TDD: focused red test, minimal implementation, focused green test, task-owned commit, project-state journal.
- Provider validation is excluded unless the user separately authorizes billed credentials.
- Finish on `main`; do not leave a temporary branch or worktree.

---

## File ownership map

### New reference-service package

- `packages/inventory-reference-service/pyproject.toml` — distribution metadata and `inventoryctl` entrypoint.
- `packages/inventory-reference-service/src/inventory_reference/models.py` — request, response, catalog, and typed error models.
- `packages/inventory-reference-service/src/inventory_reference/catalog.py` — installed catalog loading and canonical revision.
- `packages/inventory-reference-service/src/inventory_reference/artifacts.py` — canonical JSON persistence and reference construction.
- `packages/inventory-reference-service/src/inventory_reference/operations.py` — fixed read-only dispatch.
- `packages/inventory-reference-service/src/inventory_reference/cli.py` — strict stdin/stdout protocol.
- `packages/inventory-reference-service/src/inventory_reference/resources/catalogs/warehouse-a.json` — registered reference catalog.
- `packages/inventory-reference-service/tests/` — service unit and protocol tests.

### New domain-pack package

- `packages/inventory-domain-pack/pyproject.toml` — distribution metadata and exact owning dependencies.
- `packages/inventory-domain-pack/src/inventory_domain/resources.py` — installed resource materialization.
- `packages/inventory-domain-pack/src/inventory_domain/capabilities.py` — contract source and descriptions.
- `packages/inventory-domain-pack/src/inventory_domain/execution.py` — fixed subprocess executor and environment scrubbing.
- `packages/inventory-domain-pack/src/inventory_domain/authority.py` — no-follow current-run artifact verification and answer audit.
- `packages/inventory-domain-pack/src/inventory_domain/models.py` — inventory projection state models.
- `packages/inventory-domain-pack/src/inventory_domain/projection.py` — projector registry.
- `packages/inventory-domain-pack/src/inventory_domain/profile.py` — `build_inventory_profile()`.
- `packages/inventory-domain-pack/src/inventory_domain/resources/capabilities/*.json` — four model-facing contracts.
- `packages/inventory-domain-pack/src/inventory_domain/resources/policy/system-policy.md` — model execution policy.
- `packages/inventory-domain-pack/src/inventory_domain/resources/guides/` — bounded inventory guide.
- `packages/inventory-domain-pack/tests/` — profile, executor, authority, projector, and installed-resource tests.

### Repository integration

- `tools/check_package_boundaries.py` and `tools/tests/test_check_package_boundaries.py` — package ownership gates.
- `tools/test_package_artifacts.sh` and `packages/grid-agent/tests/contract/installed_smoke.py` — wheel build/install smoke.
- `tools/test_inventory_pi_transport.mjs` — provider-free generic Pi execution proof.
- `Makefile` — focused inventory and Workstream C gates.
- `README.md`, `README.zh-CN.md`, `docs/RUNBOOK.md`, and the canonical architecture/status documents — aligned product documentation.
- `docs/status/climb/*` and `tools/climb/*` — new Workstream C score session and deterministic cycle adapter.

---

### Task 1: Start the Workstream C climb session and protected-path baseline

**Files:**
- Create: `docs/status/climb/_archive/2026-08-28-workstream-b-package-extraction/*`
- Modify: `docs/status/climb/config.yaml`
- Modify: `docs/status/climb/hypotheses.yaml`
- Modify: `docs/status/climb/runs.csv`
- Modify: `docs/status/climb/calibration.json`
- Modify: `docs/status/climb/pending-lb.json`
- Modify: `docs/status/climb/session-state.json`
- Modify: `docs/status/climb/session-target.md`
- Modify: `docs/status/climb/adjudicator-log.md`
- Modify: `tools/climb/train.sh`
- Modify: `tools/climb/sync-cycle.py`
- Modify: `tools/climb/regen-tree.py`
- Test: `tools/climb/tests/test_workstream_c_adapter.py`

**Interfaces:**
- Consumes: current Workstream B tracked state and `tools/climb/eval-local.sh` gate execution.
- Produces: hypotheses `C-H001` through `C-H005`, a 100-point six-gate score contract, and a protected-path baseline digest.

- [ ] **Step 1: Archive the completed Workstream B state without deleting history**

Copy the ten active state files into
`docs/status/climb/_archive/2026-08-28-workstream-b-package-extraction/` and add
that bucket to `docs/status/INDEX.md`. Preserve the active files for replacement
in later steps.

- [ ] **Step 2: Write failing adapter tests**

Add tests asserting:

```python
assert config["session"] == "2026-08-29-workstream-c-inventory-reference-domain"
assert config["score_weights"] == {
    "reference_authority": 25.0,
    "domain_pack_spi": 20.0,
    "generic_pi_transport": 15.0,
    "authority_lineage": 20.0,
    "distribution_integrity": 10.0,
    "product_compatibility": 10.0,
}
assert [item["id"] for item in hypotheses] == [
    "C-H001", "C-H002", "C-H003", "C-H004", "C-H005"
]
assert config["protected_paths"] == [
    "packages/capability-agent-kernel",
    "packages/pi-capability-tools",
    "packages/trajectory-workbench",
]
```

Also assert `train.sh`, `sync-cycle.py`, and `regen-tree.py` derive labels and
verdict text from config instead of containing `Workstream B` or `B-H005`.

- [ ] **Step 3: Run the adapter tests and verify red**

Run:

```sh
uv run --project packages/grid-agent pytest tools/climb/tests/test_workstream_c_adapter.py -q
```

Expected: failures show the still-active Workstream B session and hard-coded B labels.

- [ ] **Step 4: Materialize the Workstream C state**

Use JSON-compatible YAML with hypotheses:

```json
{
  "hypotheses": [
    {"id":"C-H001","description":"registered inventory service owns deterministic read-only facts and current-run artifacts","parent_paradigm":"inventory-reference-authority","expected_lift":"reference_authority gate","cost_h":0.5,"ranking":1.0,"status":"pending","focused_gate":"reference_authority"},
    {"id":"C-H002","description":"inventory Domain Pack installs and composes through only the public kernel SPI","parent_paradigm":"inventory-domain-pack","expected_lift":"domain_pack_spi gate","cost_h":0.5,"ranking":0.9,"status":"pending","focused_gate":"domain_pack_spi"},
    {"id":"C-H003","description":"unchanged generic Pi tools execute inventory capabilities from the runtime descriptor","parent_paradigm":"generic-pi-transport","expected_lift":"generic_pi_transport gate","cost_h":0.25,"ranking":0.8,"status":"pending","focused_gate":"generic_pi_transport"},
    {"id":"C-H004","description":"inventory authority rejects foreign tampered symlinked and unlinked references","parent_paradigm":"inventory-authority-lineage","expected_lift":"authority_lineage gate","cost_h":0.5,"ranking":0.7,"status":"pending","focused_gate":"authority_lineage"},
    {"id":"C-H005","description":"installed inventory packages preserve protected framework paths and the grid product","parent_paradigm":"cross-domain-release-closure","expected_lift":"distribution and compatibility gates","cost_h":1.0,"ranking":0.6,"status":"pending","focused_gate":"product_compatibility"}
  ],
  "events": []
}
```

Initialize `runs.csv` with the six `local_<gate>` columns, empty calibration
and pending documents, and `session-state.json` with `next_hypothesis` set to
`C-H001`. Set the machine target to local score 100.

- [ ] **Step 5: Generalize the adapter labels**

Add `workstream_label`, `target_description`, and `release_hypothesis_id` to
config. Make `train.sh` write `kind` from `workstream_label`; make `cycle.sh`
and `eval-local.sh` compare against `release_hypothesis_id`; make
`sync-cycle.py` format verdict and next action from config; make
`regen-tree.py` render title and target from config.

- [ ] **Step 6: Capture a protected-path baseline**

Add `protected_path_digests` to config using Git tree object IDs from:

```sh
git rev-parse HEAD:packages/capability-agent-kernel
git rev-parse HEAD:packages/pi-capability-tools
git rev-parse HEAD:packages/trajectory-workbench
```

The product compatibility gate must compare the current Git tree objects to
these values before scoring.

- [ ] **Step 7: Run focused tests and regenerate the tree**

Run:

```sh
uv run --project packages/grid-agent pytest tools/climb/tests/test_workstream_c_adapter.py -q
tools/climb/regen-tree.py
git diff --check
```

Expected: PASS; research tree title is Workstream C and active hypothesis is `C-H001`.

- [ ] **Step 8: Commit and journal**

```sh
git add docs/status/INDEX.md docs/status/climb tools/climb
git commit -m "chore: start Workstream C climb session"
```

Append a project-state journal line with the resulting commit hash.

---

### Task 2: Implement the registered read-only inventory authority service

**Files:**
- Create: `packages/inventory-reference-service/pyproject.toml`
- Create: `packages/inventory-reference-service/src/inventory_reference/{__init__,models,catalog,artifacts,operations,cli}.py`
- Create: `packages/inventory-reference-service/src/inventory_reference/resources/catalogs/warehouse-a.json`
- Create: `packages/inventory-reference-service/tests/{conftest,test_catalog,test_operations,test_cli}.py`

**Interfaces:**
- Produces: `inventoryctl request --workspace PATH`, protocol `inventory-capability/1.0`, and content-addressed revision/context/result/evidence documents.

- [ ] **Step 1: Write failing catalog and operation tests**

Use these public calls:

```python
catalog = load_registered_catalog("warehouse-a")
assert catalog.catalog_id == "warehouse-a"
assert catalog.revision_ref.startswith("inventory-revision:sha256:")

opened = execute("catalog.open", {"catalog_id": "warehouse-a"}, workspace)
listed = execute("asset.list", {"context_ref": opened["context_ref"], "limit": 2}, workspace)
summary = execute("stock.summary", {"context_ref": opened["context_ref"]}, workspace)
assert len(listed["assets"]) == 2
assert summary["reorder_candidate_count"] == 2
```

Add negative tests for unknown catalog/asset, `limit=0`, filter mismatch,
foreign context, mutation capability, and path traversal.

- [ ] **Step 2: Run the service tests and verify red**

```sh
uv run --project packages/inventory-reference-service pytest -q
```

Expected: package/import failures because the service does not exist.

- [ ] **Step 3: Add models and registered catalog**

Define frozen Pydantic models `InventoryAsset`, `InventoryCatalog`,
`CapabilityRequest`, `CapabilitySuccess`, `CapabilityFailure`, and
`CapabilityError`. Package five stable asset records; exactly two records must
have `quantity_on_hand <= reorder_level` so aggregation assertions are fixed.

- [ ] **Step 4: Add canonical artifacts**

Implement:

```python
def canonical_json_bytes(value: Mapping[str, object]) -> bytes: ...
def content_reference(kind: Literal["revision", "context", "result", "evidence"], document: Mapping[str, object]) -> str: ...
def persist_document(workspace: Path, kind: str, document: Mapping[str, object]) -> tuple[str, Path]: ...
```

Use sorted compact UTF-8 JSON plus a newline on disk; derive the reference from
the canonical document without its own reference field. Create directories
with mode `0700` and files with mode `0600`.

- [ ] **Step 5: Add the fixed operation allowlist**

Implement `environment.describe`, `catalog.open`, `asset.list`, `asset.get`,
and `stock.summary` as explicit dispatch branches. Every domain result includes
`capability`, `context_ref`, `revision_ref`, `result_ref`, and `evidence_refs`
where applicable. Do not use callable-name reflection.

- [ ] **Step 6: Add strict CLI envelopes**

Read exactly one JSON object from stdin. Write exactly one compact JSON object
to stdout. Convert validation and domain failures into typed envelopes; write
unexpected diagnostics to stderr and return nonzero without a traceback on
stdout.

- [ ] **Step 7: Run focused tests and the C-H001 cycle**

```sh
uv run --project packages/inventory-reference-service pytest -q
tools/climb/cycle.sh C-H001
```

Expected: service tests pass and `reference_authority` scores 25.

- [ ] **Step 8: Commit and journal**

```sh
git add packages/inventory-reference-service docs/status/climb
git commit -m "feat: add read-only inventory authority"
```

---

### Task 3: Implement the inventory Domain Pack through public SPI

**Files:**
- Create: `packages/inventory-domain-pack/pyproject.toml`
- Create: `packages/inventory-domain-pack/src/inventory_domain/{__init__,resources,capabilities,execution,models,projection,profile}.py`
- Create: `packages/inventory-domain-pack/src/inventory_domain/resources/capabilities/{catalog.open,asset.list,asset.get,stock.summary}.json`
- Create: `packages/inventory-domain-pack/src/inventory_domain/resources/policy/system-policy.md`
- Create: `packages/inventory-domain-pack/src/inventory_domain/resources/guides/SKILL.md`
- Create: `packages/inventory-domain-pack/src/inventory_domain/resources/guides/references/{capability-map,evidence-and-recovery}.md`
- Create: `packages/inventory-domain-pack/tests/{conftest,test_resources,test_execution,test_profile,test_projection}.py`

**Interfaces:**
- Consumes: `DomainManifest`, `DomainRuntimeProfile`, `FilesystemCapabilityContractSource`, `VerifiedInvocation`, and `inventoryctl`.
- Produces: `build_inventory_profile() -> DomainRuntimeProfile` and projectors `inventory-context-v1`, `inventory-asset-v1`, `inventory-stock-summary-v1`.

- [ ] **Step 1: Write failing installed profile/resource tests**

Assert:

```python
profile = build_inventory_profile()
assert profile.manifest.domain_id == "inventory-readonly"
assert profile.manifest.protocol == "inventory-capability"
assert profile.manifest.tool_name_prefix == "inventory_"
assert profile.manifest.authority_id == "inventoryctl"
assert [d["id"] for d in profile.contract_source.load()] == [
    "asset.get", "asset.list", "catalog.open", "stock.summary"
]
```

Prepare a runtime with the installed `inventoryctl` path and assert exact
materialized model tools plus `inventory_record_decision`.

- [ ] **Step 2: Run the domain tests and verify red**

```sh
uv run --project packages/inventory-domain-pack pytest -q
```

- [ ] **Step 3: Add packaged resources and profile**

Build a `DomainManifest` with version `0.1.0`, executable `inventoryctl`,
authority `inventoryctl`, and installed resource paths. Keep resource copying
inside `InventoryResourceSet`; never use repository-relative source paths.

- [ ] **Step 4: Add the fixed executor**

Implement `InventoryctlExecutor.invoke(capability, arguments)` with
`shell=False`, timeout, credential scrubbing, exact protocol correlation, one
stdout line, typed capability errors, and a result-object requirement.

- [ ] **Step 5: Add inventory state projectors**

Define Pydantic state models and make each projector return a delta with
`model_dump`. Require admitted artifact paths for result projections and reject
unknown projector IDs with `InventoryProjectorLookupError`.

- [ ] **Step 6: Run focused tests and C-H002**

```sh
uv run --project packages/inventory-domain-pack pytest -q
tools/climb/cycle.sh C-H002
```

Expected: package tests pass and `domain_pack_spi` scores 20.

- [ ] **Step 7: Commit and journal**

```sh
git add packages/inventory-domain-pack docs/status/climb
git commit -m "feat: add inventory domain pack"
```

---

### Task 4: Implement current-run inventory artifact admission

**Files:**
- Create: `packages/inventory-domain-pack/src/inventory_domain/authority.py`
- Create: `packages/inventory-domain-pack/tests/test_authority.py`
- Modify: `packages/inventory-domain-pack/src/inventory_domain/profile.py`

**Interfaces:**
- Produces: `InventoryArtifactAuthority.admit`, `.verify_result`, and `.audit_answer_references` satisfying the kernel `ArtifactAuthority` protocol.

- [ ] **Step 1: Write failing authority tests**

Cover valid admission plus rejection of wrong reference kind, digest mismatch,
foreign workspace, context/revision mismatch, result/context mismatch,
evidence/result mismatch, symlinked workspace/artifact, traversal-like
references, and post-open replacement.

- [ ] **Step 2: Run authority tests and verify red**

```sh
uv run --project packages/inventory-domain-pack pytest packages/inventory-domain-pack/tests/test_authority.py -q
```

- [ ] **Step 3: Implement no-follow canonical verification**

Open the workspace root with `O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC`, descend fixed
directory names with dirfds, open the digest filename with `O_NOFOLLOW`, and
compare before/after `fstat` plus the named binding. Decode JSON only after the
same descriptor's bytes pass digest verification.

- [ ] **Step 4: Implement lineage and answer audit**

`admit` must return deduplicated verified context/result/evidence artifacts.
`audit_answer_references` must emit deterministic diagnostics for missing,
misclassified, invalid, and unlinked references and return no diagnostics for
a valid result/evidence pair.

- [ ] **Step 5: Run focused tests and C-H004**

```sh
uv run --project packages/inventory-domain-pack pytest packages/inventory-domain-pack/tests/test_authority.py -q
tools/climb/cycle.sh C-H004
```

Expected: authority tests pass and `authority_lineage` scores 20.

- [ ] **Step 6: Commit and journal**

```sh
git add packages/inventory-domain-pack docs/status/climb
git commit -m "feat: verify inventory result lineage"
```

---

### Task 5: Prove unchanged generic Pi transport end to end

**Files:**
- Create: `tools/test_inventory_pi_transport.mjs`
- Modify: `Makefile`
- Test: `packages/inventory-domain-pack/tests/test_generic_pi_transport.py`

**Interfaces:**
- Consumes: `prepare_domain_runtime`, `build_inventory_profile`, the installed `inventoryctl`, and `runCapability`/`createDomainToolsExtension` from unchanged generic Pi tools.
- Produces: `make test-inventory-pi` and C-H003 evidence.

- [ ] **Step 1: Write the failing Python integration wrapper**

Prepare a temporary runtime, write a JSON descriptor with camelCase keys
expected by Node, and invoke:

```sh
node tools/test_inventory_pi_transport.mjs <descriptor.json>
```

Assert the Node process exits zero and prints one JSON summary containing exact
registered names and admitted result/evidence counts.

- [ ] **Step 2: Run and verify red**

```sh
uv run --project packages/inventory-domain-pack pytest tests/test_generic_pi_transport.py -q
```

- [ ] **Step 3: Add the Node proof without editing generic Pi**

Import from `../packages/pi-capability-tools/src/domain-tools.mjs`, register
tools into a recording Pi object, execute `catalog.open`, `asset.list`, and
`stock.summary`, verify correlated `inventory-capability/1.0` responses, and
reject any registered name not beginning with `inventory_`.

- [ ] **Step 4: Add and run the focused gate**

```sh
make test-inventory-pi
tools/climb/cycle.sh C-H003
```

Expected: generic Pi proof passes and `generic_pi_transport` scores 15 while
`git diff -- packages/pi-capability-tools` remains empty.

- [ ] **Step 5: Commit and journal**

```sh
git add tools/test_inventory_pi_transport.mjs Makefile packages/inventory-domain-pack/tests docs/status/climb
git commit -m "test: prove generic Pi inventory transport"
```

---

### Task 6: Enforce package boundaries and clean installed artifacts

**Files:**
- Modify: `tools/check_package_boundaries.py`
- Modify: `tools/tests/test_check_package_boundaries.py`
- Modify: `tools/test_package_artifacts.sh`
- Modify: `packages/grid-agent/tests/contract/installed_smoke.py`
- Modify: `Makefile`

**Interfaces:**
- Produces: `make test-inventory`, updated `make check-package-boundaries`, and a six-Python-wheel clean-install smoke.

- [ ] **Step 1: Write failing negative boundary tests**

Create temporary offenders and assert messages for:

```text
inventory-reference-service imports capability_agent
inventory-domain-pack imports grid_agent
inventory-domain-pack depends on grid-agent
inventory-domain-pack contains packages/.../src
```

- [ ] **Step 2: Run and verify red**

```sh
uv run --project packages/grid-agent pytest tools/tests/test_check_package_boundaries.py -q
```

- [ ] **Step 3: Extend boundary configuration**

Add both source roots, forbidden imports, package roots, and source-literal
roots. Validate exact owning dependencies and reject cross-domain imports.

- [ ] **Step 4: Extend clean artifact installation**

Build both new wheels, require exactly six Python wheels, install all into the
temporary venv, and extend `installed_smoke.py` to build the inventory profile,
run `inventoryctl`, admit its references, and assert no source-tree path appears
in installed resources.

- [ ] **Step 5: Run package and repository-focused tests**

```sh
make check-package-boundaries
make test-inventory
make test-packages
```

Expected: all pass outside repository source layout.

- [ ] **Step 6: Commit and journal**

```sh
git add tools Makefile packages/grid-agent/tests/contract/installed_smoke.py
git commit -m "test: enforce inventory package boundaries"
```

---

### Task 7: Close Workstream C documentation, compatibility, and climb release

**Files:**
- Modify: `README.md`
- Modify: `README.zh-CN.md`
- Modify: `docs/RUNBOOK.md`
- Modify: `docs/architecture/pandapower-capability-composition.md`
- Modify: `docs/superpowers/specs/2026-08-27-general-domain-agent-framework-upgrade-design.md`
- Modify: `docs/status/CURRENT-STATE.md`
- Modify: `docs/status/DECISIONS.md`
- Modify: `docs/status/RESUME-NEXT-SESSION.md`
- Modify: `docs/status/JOURNAL.md`
- Modify: `docs/status/climb/*`

**Interfaces:**
- Consumes: all focused gates and protected-path baseline.
- Produces: bilingual operator documentation, 100/100 climb closure, and a clean `main` recovery point for Workstream D.

- [ ] **Step 1: Update bilingual and architectural documentation**

Document the two inventory distributions, provider-free conformance command,
authority boundary, exact non-goals, and the statement that Workstream C proves
single-domain instantiation but not write governance or multi-domain routing.
Keep README headings, commands, and shared facts aligned.

- [ ] **Step 2: Update structural state and decision ledger**

Record inventory selection, package ownership, authority lineage, protected
kernel paths, and remaining Workstreams D/E. Keep session narration out of
`CURRENT-STATE.md`.

- [ ] **Step 3: Run focused and supported gates**

```sh
make test-inventory
make check-package-boundaries
make test-packages
make doctor
make test
make test-e2e
make validate
```

Expected: all commands exit zero; no provider validation is invoked.

- [ ] **Step 4: Verify protected-path zero diff**

Compare current Git tree objects for every `protected_paths` entry to the
recorded baseline. Any mismatch blocks closure and requires reverting the
Workstream C change under that protected path through a normal corrective
commit, never a destructive reset.

- [ ] **Step 5: Execute C-H005 release closure**

```sh
tools/climb/cycle.sh C-H005
tools/climb/check-target.py
```

Expected: local score 100, `release_ready=true`, no blockers, phase `complete`,
and research tree shows C-H001 through C-H005 confirmed.

- [ ] **Step 6: Run final hygiene checks**

```sh
test -L CLAUDE.md
test "$(readlink CLAUDE.md)" = "AGENTS.md"
git diff --check
git status --short --branch
git worktree list
git branch --list
```

Expected: `main`, no Workstream C temporary branch/worktree, and only the final
task-owned state/docs changes staged for the closure commit.

- [ ] **Step 7: Commit, journal, checkpoint, and push main if the configured origin is unchanged**

```sh
git add README.md README.zh-CN.md docs Makefile packages tools
git commit -m "feat: prove cross-domain inventory instantiation"
```

Append the commit and verification facts to JOURNAL, refresh CURRENT-STATE and
the active-session checkpoint, then push `main` only if `origin/main` has not
advanced and the user has already authorized autonomous repository integration.

---

## Plan self-review

- Spec coverage: every design exit criterion maps to Tasks 1–7.
- Scope: read-only inventory only; Workstreams D/E remain excluded.
- Protected paths: explicit baseline and release blocker prevent accidental kernel or generic Pi edits.
- Type consistency: service references, profile IDs, tool prefix, protocol, and projector IDs are identical across tasks.
- Placeholder scan: no implementation step delegates unspecified error handling, validation, or testing.
