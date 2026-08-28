# Workstream B Physical Package Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Design reference:** [`2026-08-28-workstream-b-physical-package-extraction-design.md`](../specs/2026-08-28-workstream-b-physical-package-extraction-design.md)

**Goal:** Extract an independently buildable capability-agent kernel, pandapower Domain Pack, and generic Pi tools package, then assemble the existing `grid-agent` product from them without changing observable behavior.

**Architecture:** New code uses three distinct ownership namespaces: `capability_agent` for neutral Python contracts and reusable lifecycle primitives, `pandapower_domain` for grid-specific adapters and resources, and `@capability-agent/pi-tools` for descriptor-driven Pi integration. `grid-agent` remains the explicit application composition root and owns implementation-free compatibility shims; extracted packages never import the application.

**Tech Stack:** Python >=3.12, Hatchling, uv, Pydantic >=2.12,<3, pytest >=9,<10, Node.js >=22.19.0, npm, ESM, Pi 0.80.6, JSON Schema, `grid-capability/1.0`.

## Global Constraints

- Distribution names and initial versions are exactly `capability-agent-kernel==0.1.0`, `pandapower-domain-pack==0.1.0`, and `@capability-agent/pi-tools@0.1.0`.
- New Python import namespaces are exactly `capability_agent` and `pandapower_domain`; multiple wheels must not contribute implementation files to `grid_agent`.
- The dependency direction is `grid-agent -> pandapower-domain-pack -> capability-agent-kernel`; `grid-agent -> capability-agent-kernel` is also allowed. Neither extracted package may import or depend on `grid-agent`.
- The generic Node package must not hard-code `grid-capability`, `gridctl`, `grid_`, or `GRID_AGENT_*` in its reusable execution path.
- `grid-agent`, `gridctl`, `grid-capability/1.0`, `grid_*` tools, current CLI arguments, existing `GRID_AGENT_*` variables, run schemas, reports, and evidence admission remain compatible.
- The default CLI writes exactly one JSON object containing only `question_id` and `answer_output` to stdout; diagnostics remain on stderr.
- Numerical and network facts continue to cross the `gridctl` simulator boundary. No model-facing shell, arbitrary subprocess, generic file, Python, pandapower object, or DataFrame capability may be introduced.
- Installed resources use package-resource APIs; production code may not reconstruct `packages/.../src/...` repository paths.
- Existing source imports remain available through implementation-free forwarding modules for this compatibility cycle, but new production code imports only the new namespaces.
- No dynamic plugin discovery, production non-grid domain, multi-domain routing, enterprise write actions, persisted schema migration, external publication, or provider-backed validation belongs in this plan.
- Every behavior task follows red-green-refactor, ends in a focused regression, and lands as an atomic commit containing only task-owned paths.
- Preserve unrelated working-tree changes in `docs/status/CURRENT-STATE.md`, `docs/status/JOURNAL.md`, and `docs/status/RESUME-NEXT-SESSION.md`; state synchronization commits are separate from feature commits.

---

## File and Ownership Map

### Python kernel distribution

- Create `packages/capability-agent-kernel/pyproject.toml` — independently versioned wheel metadata.
- Create `packages/capability-agent-kernel/src/capability_agent/__init__.py` — deliberate public exports.
- Create `packages/capability-agent-kernel/src/capability_agent/domain/` — Workstream A SPI and Profile types.
- Create `packages/capability-agent-kernel/src/capability_agent/tools/catalog.py` — neutral catalog implementation.
- Create `packages/capability-agent-kernel/src/capability_agent/tools/guide.py` — neutral guide allowlist.
- Create `packages/capability-agent-kernel/src/capability_agent/application/composition.py` — Profile-driven runtime preparation.
- Create `packages/capability-agent-kernel/src/capability_agent/trajectory/` — canonical, events, artifacts, answers, reader, recorder, and replay primitives.
- Create `packages/capability-agent-kernel/tests/` — direct public API, boundary, and lifecycle tests.

### Generic and compatibility Pi packages

- Create `packages/pi-capability-tools/package.json` — generic ESM package metadata.
- Create `packages/pi-capability-tools/src/domain-tools.mjs` — descriptor-driven capability and bounded-tool registration.
- Create `packages/pi-capability-tools/src/model-request-capture.mjs` — neutral request capture implementation.
- Create `packages/pi-capability-tools/test/` — generic request, security, runtime, and package tests.
- Modify `packages/pi-grid-tools/package.json` — depend on the generic workspace package.
- Modify `packages/pi-grid-tools/src/domain-tools.mjs` — grid compatibility adapter and exports.
- Modify `packages/pi-grid-tools/src/model-request-capture.mjs` — compatibility re-export.

### Pandapower Domain Pack

- Create `packages/pandapower-domain-pack/pyproject.toml` — domain distribution metadata and resources.
- Create `packages/pandapower-domain-pack/src/pandapower_domain/` — Profile, executor, capability context, projection, and authority.
- Create `packages/pandapower-domain-pack/src/pandapower_domain/resources/` — canonical policy and guide resources.
- Create `packages/pandapower-domain-pack/tests/` — direct package, resource, boundary, projection, and authority tests.
- Modify `packages/grid-simulator/src/grid_simulator/capabilities/__init__.py` — installed capability-resource source.

### Compatibility application and gates

- Modify `packages/grid-agent/pyproject.toml` and `packages/grid-agent/uv.lock` — local extracted-package dependencies.
- Replace selected `packages/grid-agent/src/grid_agent/{domain,tools,application,trajectory,domains,simulator,analysis}/` implementation modules with forwarding imports where ownership moved.
- Modify `packages/grid-agent/src/grid_agent/cli/app.py` — explicit new-package composition.
- Modify `packages/grid-agent/src/grid_agent/runtime/pi_config.py` and `runtime/environment.py` — materialize and pass the validated runtime descriptor while keeping legacy environment variables.
- Create `tools/check_package_boundaries.py` — AST and metadata dependency gate.
- Create `tools/test_package_artifacts.sh` — clean wheel/package installation gate.
- Modify `Makefile` — package setup, test, and artifact verification targets.
- Update architecture, runbook, bilingual READMEs, repository contract references, and durable climb/project state.

---

### Task 1: Lock distribution and compatibility baselines

**Files:**

- Create: `packages/grid-agent/tests/contract/test_package_extraction_baseline.py`
- Modify: `packages/grid-agent/tests/domain/test_pandapower_profile.py`
- Modify: `packages/pi-grid-tools/test/domain-tools.test.mjs`
- Create: `tools/check_package_boundaries.py`
- Modify: `Makefile`

**Interfaces:**

- Consumes: current Workstream A imports, catalog/guide output, pandapower Profile, and Pi request helpers.
- Produces: `python3 tools/check_package_boundaries.py` and compatibility assertions that remain green throughout extraction.

- [ ] **Step 1: Write failing package-layout and import-boundary tests**

Add tests that require the approved distributions and public namespaces:

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def test_approved_distribution_layout_exists() -> None:
    expected = (
        ROOT / "packages/capability-agent-kernel/pyproject.toml",
        ROOT / "packages/pandapower-domain-pack/pyproject.toml",
        ROOT / "packages/pi-capability-tools/package.json",
    )
    assert [str(path.relative_to(ROOT)) for path in expected if not path.is_file()] == []


def test_legacy_public_imports_are_preserved() -> None:
    from grid_agent.application.composition import prepare_domain_runtime
    from grid_agent.domain import DomainManifest
    from grid_agent.domains import build_pandapower_profile
    from grid_agent.tools.catalog import ToolCatalog

    assert prepare_domain_runtime.__name__ == "prepare_domain_runtime"
    assert DomainManifest.__name__ == "DomainManifest"
    assert build_pandapower_profile.__name__ == "build_pandapower_profile"
    assert ToolCatalog.__name__ == "ToolCatalog"
```

- [ ] **Step 2: Add a boundary checker with exact dependency rules**

Create `tools/check_package_boundaries.py` using `ast.parse`. It must scan Python sources and fail with sorted `path imports module` lines when:

```python
RULES = {
    "packages/capability-agent-kernel/src": (
        "grid_agent",
        "grid_simulator",
        "pandapower_domain",
        "pandapower",
    ),
    "packages/pandapower-domain-pack/src": ("grid_agent",),
}
```

It must also parse both new `pyproject.toml` files with `tomllib`, reject a `grid-agent` dependency in either, and reject repository-source literals matching `packages/.+/src` inside either package. Exit `0` with `package-boundaries: ok`; otherwise print each violation to stderr and exit `1`.

- [ ] **Step 3: Extend Node characterization before the generic extraction**

Add an exact request assertion to `packages/pi-grid-tools/test/domain-tools.test.mjs`:

```javascript
test("grid request compatibility remains exact", () => {
  assert.deepEqual(buildGridRequest("model.list", {}, "request-1"), {
    protocol: "grid-capability",
    protocol_version: "1.0",
    request_id: "request-1",
    capability: "model.list",
    arguments: {},
  });
});
```

Keep the existing catalog-driven tool, response-correlation, path containment,
context, decision, and secret-sanitization tests as the compatibility baseline.

- [ ] **Step 4: Run the red baseline**

Run:

```sh
uv run --project packages/grid-agent pytest \
  packages/grid-agent/tests/contract/test_package_extraction_baseline.py \
  packages/grid-agent/tests/domain/test_pandapower_profile.py -q
npm test --prefix packages/pi-grid-tools
python3 tools/check_package_boundaries.py
```

Expected: Python layout test fails because the three packages do not exist;
existing pandapower and Node behavior remains green; the boundary checker passes
the current rules because the new roots are absent.

- [ ] **Step 5: Add the boundary command without satisfying the layout test**

Add to `Makefile`:

```make
.PHONY: check-package-boundaries

check-package-boundaries:
	python3 tools/check_package_boundaries.py
```

Run `make check-package-boundaries`; expected: `package-boundaries: ok`.

- [ ] **Step 6: Commit the characterization gate**

```sh
git add packages/grid-agent/tests/contract/test_package_extraction_baseline.py \
  packages/grid-agent/tests/domain/test_pandapower_profile.py \
  packages/pi-grid-tools/test/domain-tools.test.mjs \
  tools/check_package_boundaries.py Makefile
git commit -m "test: characterize package extraction boundary"
```

---

### Task 2: Extract the neutral Python SDK and runtime preparation

**Files:**

- Create: `packages/capability-agent-kernel/pyproject.toml`
- Create: `packages/capability-agent-kernel/src/capability_agent/__init__.py`
- Create: `packages/capability-agent-kernel/src/capability_agent/domain/*.py`
- Create: `packages/capability-agent-kernel/src/capability_agent/tools/{__init__,catalog,guide}.py`
- Create: `packages/capability-agent-kernel/src/capability_agent/application/{__init__,composition}.py`
- Create: `packages/capability-agent-kernel/tests/{conftest,test_public_api,test_composition,test_boundaries}.py`
- Modify: `packages/grid-agent/src/grid_agent/domain/*.py`
- Modify: `packages/grid-agent/src/grid_agent/tools/{catalog,guide}.py`
- Modify: `packages/grid-agent/src/grid_agent/application/composition.py`
- Modify: `packages/grid-agent/pyproject.toml`

**Interfaces:**

- Consumes: the exact Workstream A public types and behavior.
- Produces: `capability_agent.DomainManifest`, `DomainRuntimeProfile`, `ToolCatalog`, `GuideIndex`, and `prepare_domain_runtime(...)`; old imports resolve to the same class/function objects.

- [ ] **Step 1: Add direct-package tests that fail before extraction**

The new tests import only `capability_agent` and assert identity through the old paths:

```python
from capability_agent import DomainManifest, DomainRuntimeProfile
from capability_agent.application import prepare_domain_runtime
from capability_agent.tools import GuideIndex, ToolCatalog


def test_kernel_public_api_is_deliberate() -> None:
    assert DomainManifest.__module__.startswith("capability_agent.")
    assert DomainRuntimeProfile.__module__.startswith("capability_agent.")
    assert prepare_domain_runtime.__module__ == "capability_agent.application.composition"
    assert ToolCatalog.__module__ == "capability_agent.tools.catalog"
    assert GuideIndex.__module__ == "capability_agent.tools.guide"
```

Add one provider-free inventory Profile test by moving the current fixture logic
from `packages/grid-agent/tests/application/test_composition.py`; expected output
contains exactly `inventory_asset_list` and `inventory_record_decision`.

- [ ] **Step 2: Run the direct tests and verify import failure**

```sh
uv run --project packages/grid-agent pytest packages/capability-agent-kernel/tests -q
```

Expected: FAIL with `ModuleNotFoundError: capability_agent`.

- [ ] **Step 3: Create the kernel package and move the neutral implementation**

Use these package settings:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "capability-agent-kernel"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["pydantic>=2.12,<3"]

[dependency-groups]
dev = ["pytest>=9,<10"]

[tool.hatch.build.targets.wheel]
packages = ["src/capability_agent"]
```

Move the bodies of `grid_agent/domain/*.py`, `tools/catalog.py`, `tools/guide.py`,
and `application/composition.py` into equivalent `capability_agent` modules.
Change only internal import roots. Delete `load_packaged_capability_documents`
from the neutral catalog because it reconstructs a grid repository path.

- [ ] **Step 4: Add implementation-free compatibility modules**

Each old module re-exports the exact prior public names. For example:

```python
# packages/grid-agent/src/grid_agent/domain/manifest.py
from capability_agent.domain.manifest import DomainManifest, DomainManifestError

__all__ = ["DomainManifest", "DomainManifestError"]
```

`grid_agent.tools.catalog`, `grid_agent.tools.guide`, and
`grid_agent.application.composition` follow the same pattern. No wrapper writes
warnings or contains fallback behavior.

- [ ] **Step 5: Add the local package dependency**

Append to `packages/grid-agent/pyproject.toml`:

```toml
[tool.uv.sources]
capability-agent-kernel = { path = "../capability-agent-kernel", editable = true }
```

Add `"capability-agent-kernel==0.1.0"` to `[project].dependencies`, then run:

```sh
uv lock --project packages/grid-agent
uv sync --project packages/grid-agent
```

- [ ] **Step 6: Run focused and boundary tests**

```sh
uv run --project packages/grid-agent pytest \
  packages/capability-agent-kernel/tests \
  packages/grid-agent/tests/domain \
  packages/grid-agent/tests/application/test_composition.py \
  packages/grid-agent/tests/tools -q
make check-package-boundaries
```

Expected: PASS, and old/new imports refer to the same implementations.

- [ ] **Step 7: Commit the neutral package**

```sh
git add packages/capability-agent-kernel packages/grid-agent/pyproject.toml \
  packages/grid-agent/uv.lock packages/grid-agent/src/grid_agent/domain \
  packages/grid-agent/src/grid_agent/tools \
  packages/grid-agent/src/grid_agent/application/composition.py
git commit -m "feat: extract capability agent kernel sdk"
```

---

### Task 3: Extract the proven neutral trajectory lifecycle slice

**Files:**

- Create: `packages/capability-agent-kernel/src/capability_agent/trajectory/*.py`
- Create: `packages/capability-agent-kernel/tests/trajectory/*.py`
- Modify: `packages/grid-agent/src/grid_agent/trajectory/{canonical,events,artifacts,answers,reader,recorder,replay}.py`

**Interfaces:**

- Consumes: existing canonical serialization, event models, artifact registry, answer validation, reader, recorder, and replay behavior.
- Produces: the same APIs under `capability_agent.trajectory`, with old modules as identity-preserving exports.

- [ ] **Step 1: Add direct kernel lifecycle tests**

Copy the behavioral tests for canonical hashing, event building, immutable
artifact registration, answer validation, hash-chain reading, recording, and
replay into the kernel test tree. Change only imports to `capability_agent`.
Add this isolation assertion:

```python
def test_trajectory_public_modules_import_without_application() -> None:
    modules = (
        "capability_agent.trajectory.canonical",
        "capability_agent.trajectory.events",
        "capability_agent.trajectory.artifacts",
        "capability_agent.trajectory.answers",
        "capability_agent.trajectory.reader",
        "capability_agent.trajectory.recorder",
        "capability_agent.trajectory.replay",
    )
    for module in modules:
        assert importlib.import_module(module).__name__ == module
```

- [ ] **Step 2: Run the direct lifecycle tests and verify import failure**

```sh
uv run --project packages/grid-agent pytest packages/capability-agent-kernel/tests/trajectory -q
```

Expected: FAIL because `capability_agent.trajectory` is absent.

- [ ] **Step 3: Move the exact neutral module bodies**

Move these seven implementations without schema, validation, path-layout, or
error-message changes:

```sh
canonical.py events.py artifacts.py answers.py reader.py recorder.py replay.py
```

Replace internal imports with `capability_agent.trajectory.*`. Do not move
`capture.py`, `context_bridge.py`, projections, API, service, or materialization;
they still contain application or grid assumptions.

- [ ] **Step 4: Replace old modules with explicit exports**

For modules with many public names, use star re-export only when the new owning
module defines a deliberate `__all__`; otherwise list the symbols used by source
and tests. Verify object identity, not merely equivalent output:

```python
from capability_agent.trajectory.events import RunEvent as KernelRunEvent
from grid_agent.trajectory.events import RunEvent as LegacyRunEvent

assert LegacyRunEvent is KernelRunEvent
```

- [ ] **Step 5: Run lifecycle and all trajectory tests**

```sh
uv run --project packages/grid-agent pytest \
  packages/capability-agent-kernel/tests/trajectory \
  packages/grid-agent/tests/trajectory -q
make check-package-boundaries
```

Expected: PASS with unchanged persisted event and artifact contracts.

- [ ] **Step 6: Commit the lifecycle extraction**

```sh
git add packages/capability-agent-kernel/src/capability_agent/trajectory \
  packages/capability-agent-kernel/tests/trajectory \
  packages/grid-agent/src/grid_agent/trajectory
git commit -m "refactor: extract neutral trajectory lifecycle"
```

---

### Task 4: Extract descriptor-driven generic Pi tools

**Files:**

- Create: `packages/pi-capability-tools/package.json`
- Create: `packages/pi-capability-tools/src/{domain-tools,model-request-capture}.mjs`
- Create: `packages/pi-capability-tools/test/*.test.mjs`
- Modify: `packages/pi-grid-tools/package.json`
- Modify: `packages/pi-grid-tools/package-lock.json`
- Modify: `packages/pi-grid-tools/src/{domain-tools,model-request-capture}.mjs`

**Interfaces:**

- Consumes: a validated controller-owned `RuntimeDescriptor` and current Pi APIs.
- Produces: `buildCapabilityRequest(descriptor, capability, params, requestId)`, `createCapabilityTool(descriptor, contract, runner)`, `createDomainToolsExtension(descriptor)`, and exact grid compatibility exports.

- [ ] **Step 1: Write failing generic request and security tests**

Define a test descriptor:

```javascript
const inventory = Object.freeze({
  protocol: "inventory-capability",
  protocolVersion: "1.0",
  executable: "inventoryctl",
  executableArgs: ["request", "--workspace", "/tmp/inventory-run"],
  toolNamePrefix: "inventory_",
  guideToolName: "inventory_guide_open",
  contextToolName: "inventory_analysis_context_get",
  decisionToolName: "inventory_record_decision",
});
```

Assert that `buildCapabilityRequest(inventory, "asset.list", {}, "r-1")`
returns the inventory protocol document, correlation mismatch is fail-closed,
and tool input cannot override `executable` or `executableArgs`. Assert the
generic source tree contains none of the four forbidden grid literals.

- [ ] **Step 2: Run the generic tests and verify package absence**

```sh
npm test --prefix packages/pi-capability-tools
```

Expected: FAIL because the package does not exist.

- [ ] **Step 3: Create the generic package metadata**

```json
{
  "name": "@capability-agent/pi-tools",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "check": "node --check src/domain-tools.mjs && node --check src/model-request-capture.mjs",
    "test": "node --test"
  },
  "dependencies": {
    "@earendil-works/pi-ai": "^0.80.6",
    "@earendil-works/pi-coding-agent": "0.80.6"
  },
  "engines": { "node": ">=22.19.0" }
}
```

- [ ] **Step 4: Implement validated descriptor-driven request execution**

Use an exact descriptor validator that rejects unknown fields, non-basename
executables, non-string argument entries, invalid tool prefixes, and mismatched
bounded-tool prefixes. `createCapabilityTool` closes over the descriptor; it
passes only `{protocol, protocol_version, request_id, capability, arguments}` to
the runner. The child process is spawned from `descriptor.executable` and the
frozen `descriptor.executableArgs`; tool parameters are never concatenated into
the command line.

Move model-request capture unchanged except for module/package names. Preserve
canonical request persistence and acknowledgement behavior byte-for-byte.

- [ ] **Step 5: Convert the grid package to a compatibility adapter**

Add the workspace dependency:

```json
"@capability-agent/pi-tools": "file:../pi-capability-tools"
```

The grid module exports wrappers with the prior names:

```javascript
export function buildGridRequest(capability, params, requestId) {
  return buildCapabilityRequest(gridDescriptor(), capability, params, requestId);
}

export function createGridTool(contract, runner) {
  return createCapabilityTool(gridDescriptor(), contract, runner);
}
```

The default extension maps the current validated `GRID_AGENT_*` paths into the
descriptor and delegates registration. It must continue skipping the catalog's
decision tool before registering the bounded controller-owned replacement.

- [ ] **Step 6: Install and run both Node suites**

```sh
npm install --prefix packages/pi-capability-tools
npm install --prefix packages/pi-grid-tools
npm run check --prefix packages/pi-capability-tools
npm test --prefix packages/pi-capability-tools
npm run check --prefix packages/pi-grid-tools
npm test --prefix packages/pi-grid-tools
```

Expected: both suites pass; the grid request snapshot is unchanged.

- [ ] **Step 7: Commit the Pi extraction**

```sh
git add packages/pi-capability-tools packages/pi-grid-tools/package.json \
  packages/pi-grid-tools/package-lock.json packages/pi-grid-tools/src \
  packages/pi-grid-tools/test
git commit -m "feat: extract descriptor driven pi tools"
```

---

### Task 5: Establish installed simulator resources and pandapower transport

**Files:**

- Modify: `packages/grid-simulator/src/grid_simulator/capabilities/__init__.py`
- Modify: `packages/grid-simulator/tests/test_capability_contracts.py`
- Create: `packages/pandapower-domain-pack/pyproject.toml`
- Create: `packages/pandapower-domain-pack/src/pandapower_domain/{__init__,resources,execution}.py`
- Create: `packages/pandapower-domain-pack/tests/{conftest,test_resources,test_execution,test_boundaries}.py`
- Modify: `packages/grid-agent/src/grid_agent/simulator/{client,locator}.py`

**Interfaces:**

- Consumes: packaged simulator capability definitions and the exact `GridctlClient` request behavior.
- Produces: `grid_simulator.capabilities.contract_root()`, `PandapowerResourceSet`, `GridctlExecutor`, and application compatibility exports.

- [ ] **Step 1: Write failing installed-resource and transport tests**

Simulator test:

```python
def test_contract_root_exposes_packaged_definitions() -> None:
    root = contract_root()
    documents = sorted(root.glob("*.json"))
    assert len(documents) == 30
    assert all(path.is_file() for path in documents)
```

Domain test asserts `PandapowerResourceSet.load().capability_contract_root`
contains the same files and does not contain `packages/grid-simulator/src`.
Transport tests copy the existing fake-`gridctl` assertions and import
`GridctlExecutor` from `pandapower_domain.execution`.

- [ ] **Step 2: Run and verify missing APIs**

```sh
uv run --project packages/grid-simulator pytest \
  packages/grid-simulator/tests/test_capability_contracts.py -q
uv run --project packages/grid-agent pytest packages/pandapower-domain-pack/tests -q
```

Expected: FAIL on missing `contract_root` and missing domain package.

- [ ] **Step 3: Expose simulator package resources**

Implement `contract_root()` with `importlib.resources.files`. Return a traversable
filesystem path for the installed wheel and keep the existing Hatch
`force-include` configuration. If the loader cannot provide a stable path,
materialize the immutable JSON files through `as_file` inside a resource-owner
context held by the Domain Profile; do not copy them into the repository.

- [ ] **Step 4: Create the domain package and move transport code**

Use Python metadata:

```toml
[project]
name = "pandapower-domain-pack"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "capability-agent-kernel==0.1.0",
  "grid-simulator==1.0.1",
]

[dependency-groups]
dev = ["pytest>=9,<10"]

[tool.uv.sources]
capability-agent-kernel = { path = "../capability-agent-kernel", editable = true }
grid-simulator = { path = "../grid-simulator", editable = true }

[tool.hatch.build.targets.wheel]
packages = ["src/pandapower_domain"]
```

Move the implementation of `GridctlClient` to
`pandapower_domain.execution.GridctlExecutor`, retaining `invoke(capability,
arguments) -> dict[str, object]`, correlation, timeout, sanitized environment,
and typed errors. Export `GridctlClient = GridctlExecutor` only from the old
compatibility module.

- [ ] **Step 5: Run domain transport and old simulator-client tests**

```sh
uv lock --project packages/pandapower-domain-pack
uv sync --project packages/pandapower-domain-pack
uv run --project packages/pandapower-domain-pack pytest \
  packages/pandapower-domain-pack/tests/test_resources.py \
  packages/pandapower-domain-pack/tests/test_execution.py -q
uv run --project packages/grid-agent pytest \
  packages/grid-agent/tests/simulator/test_client.py -q
make check-package-boundaries
```

Expected: PASS; exact request documents remain unchanged.

- [ ] **Step 6: Commit transport and resource ownership**

```sh
git add packages/grid-simulator/src/grid_simulator/capabilities/__init__.py \
  packages/grid-simulator/tests/test_capability_contracts.py \
  packages/pandapower-domain-pack \
  packages/grid-agent/src/grid_agent/simulator
git commit -m "feat: package pandapower resources and transport"
```

---

### Task 6: Move pandapower projection, authority, policy, and guides

**Files:**

- Create: `packages/pandapower-domain-pack/src/pandapower_domain/{capabilities,models,projection,authority,profile}.py`
- Create: `packages/pandapower-domain-pack/src/pandapower_domain/resources/policy/system-policy.md`
- Create: `packages/pandapower-domain-pack/src/pandapower_domain/resources/guides/`
- Create: `packages/pandapower-domain-pack/tests/{test_profile,test_projection,test_authority}.py`
- Modify: `packages/grid-agent/src/grid_agent/analysis/{capabilities,models,domain_projection,integrity}.py`
- Modify: `packages/grid-agent/src/grid_agent/domains/pandapower.py`
- Modify: `packages/grid-agent/pyproject.toml`
- Modify: `packages/grid-agent/uv.lock`
- Modify: `AGENTS.md`

**Interfaces:**

- Consumes: kernel Profile protocols, installed simulator contracts, existing grid state-delta and evidence behavior.
- Produces: `pandapower_domain.build_pandapower_profile()` with no repository-root parameter and no `grid_agent` import.

- [ ] **Step 1: Write direct Profile, projection, and authority parity tests**

Port the current `test_pandapower_profile.py` scenarios to direct domain imports.
Change the construction assertion to:

```python
profile = build_pandapower_profile()
resources = PandapowerResourceSet.load()

assert profile.manifest.capability_contract_root == resources.capability_contract_root
assert profile.manifest.system_policy_path == resources.system_policy_path
assert profile.manifest.guide_root == resources.guide_root
assert profile.manifest.protocol == "grid-capability"
assert profile.manifest.tool_name_prefix == "grid_"
```

Keep the existing real artifact fixtures and assert authority admission equals
the pre-move verifier output. Keep the model-open projection dump assertion.

- [ ] **Step 2: Run the tests and verify the new Profile is absent**

```sh
uv run --project packages/grid-agent pytest \
  packages/pandapower-domain-pack/tests/test_profile.py \
  packages/pandapower-domain-pack/tests/test_projection.py \
  packages/pandapower-domain-pack/tests/test_authority.py -q
```

Expected: FAIL on missing domain modules.

- [ ] **Step 3: Move the minimal grid implementation closure**

Move the implementations required by the Profile from these current modules:

```text
grid_agent.analysis.capabilities
grid_agent.analysis.models
grid_agent.analysis.domain_projection
grid_agent.analysis.integrity
grid_agent.domains.pandapower
```

Update imports to `capability_agent` and `pandapower_domain`. If an entire
`analysis.models` type is consumed broadly by the grid application, keep its
implementation in the Domain Pack and make the old module an explicit export;
do not duplicate model classes because Pydantic identity affects validation.

The compatibility `grid_agent.domains.pandapower.build_pandapower_profile`
accepts its former optional repository-root argument and deliberately ignores
it before delegating to the installed-resource Profile. This keeps the current
CLI executable between Tasks 6 and 7 without reintroducing path ownership.

- [ ] **Step 4: Move canonical domain resources**

Move the current policy and grid guide files into the package resource tree with
history-preserving `git mv`. Update the package wheel include and change
`PandapowerResourceSet.load()` to resolve them through `importlib.resources`.
Update `AGENTS.md` authoritative references to their single new canonical
locations. If a repository-level path must remain for an operator command,
materialize it from the package during setup; do not keep two editable sources.

- [ ] **Step 5: Add the Domain Pack to the compatibility application environment**

Add `pandapower-domain-pack==0.1.0` to `grid-agent` dependencies and:

```toml
pandapower-domain-pack = { path = "../pandapower-domain-pack", editable = true }
```

to its existing `[tool.uv.sources]`, then run `uv lock --project
packages/grid-agent` and `uv sync --project packages/grid-agent`. This dependency
supports the compatibility exports; Task 7 separately switches production
assembly imports.

- [ ] **Step 6: Enforce domain independence**

Run:

```sh
python3 tools/check_package_boundaries.py
rg -n "from grid_agent|import grid_agent" packages/pandapower-domain-pack/src
```

Expected: boundary checker passes and `rg` prints no matches.

- [ ] **Step 7: Run domain and compatibility slices**

```sh
uv run --project packages/pandapower-domain-pack pytest \
  packages/pandapower-domain-pack/tests -q
uv run --project packages/grid-agent pytest \
  packages/grid-agent/tests/domain \
  packages/grid-agent/tests/analysis/test_capabilities.py \
  packages/grid-agent/tests/analysis/test_domain_projection.py \
  packages/grid-agent/tests/analysis/test_integrity.py -q
```

Expected: PASS with class identity and artifact admission preserved.

- [ ] **Step 8: Commit the Domain Pack**

```sh
git add AGENTS.md packages/pandapower-domain-pack \
  packages/grid-agent/pyproject.toml packages/grid-agent/uv.lock \
  packages/grid-agent/src/grid_agent/analysis \
  packages/grid-agent/src/grid_agent/domains \
  configs/agent skills/grid-static-analysis
git commit -m "feat: extract pandapower domain pack"
```

Stage only paths that actually moved or became compatibility exports; do not
stage unrelated analysis modules.

---

### Task 7: Switch `grid-agent` to explicit extracted-package assembly

**Files:**

- Modify: `packages/grid-agent/pyproject.toml`
- Modify: `packages/grid-agent/uv.lock`
- Modify: `packages/grid-agent/src/grid_agent/cli/app.py`
- Modify: `packages/grid-agent/src/grid_agent/runtime/{environment,pi_config}.py`
- Modify: `packages/grid-agent/tests/cli/test_app.py`
- Modify: `packages/grid-agent/tests/runtime/{test_pi_config,test_provider_adapters}.py`
- Modify: `packages/grid-agent/tests/contract/test_package_extraction_baseline.py`

**Interfaces:**

- Consumes: `capability_agent.prepare_domain_runtime`, `pandapower_domain.build_pandapower_profile`, and generic Pi runtime descriptor fields.
- Produces: the unchanged `grid-agent` CLI assembled from extracted packages without production compatibility imports.

- [ ] **Step 1: Write failing assembly import and descriptor tests**

Parse `cli/app.py` and assert it imports the new owning namespaces. Add a runtime
test that materializes this immutable descriptor for the current product:

```json
{
  "protocol": "grid-capability",
  "protocol_version": "1.0",
  "executable": "gridctl",
  "executable_args": ["request", "--workspace", "<current run path>"],
  "tool_name_prefix": "grid_",
  "guide_tool_name": "grid_guide_open",
  "context_tool_name": "grid_analysis_context_get",
  "decision_tool_name": "grid_record_decision"
}
```

Assert that the descriptor path is controller-created and read-only to the Pi
child, while all current `GRID_AGENT_*` entries remain present.

- [ ] **Step 2: Run the focused red tests**

```sh
uv run --project packages/grid-agent pytest \
  packages/grid-agent/tests/cli/test_app.py \
  packages/grid-agent/tests/runtime/test_pi_config.py \
  packages/grid-agent/tests/contract/test_package_extraction_baseline.py -q
```

Expected: FAIL because CLI still imports compatibility paths and no descriptor is materialized.

- [ ] **Step 3: Switch production assembly to the owning imports**

Use the Domain Pack dependency added in Task 6. Import `prepare_domain_runtime`
from `capability_agent.application` and
`build_pandapower_profile` from `pandapower_domain`. Remove the repository-root
argument. Keep explicit selection in each CLI composition path; do not add a
kernel default.

- [ ] **Step 4: Materialize the Pi runtime descriptor**

Extend `PiConfigMaterializer` with one method:

```python
def materialize_domain_runtime(
    self,
    manifest: DomainManifest,
    *,
    workspace: Path,
) -> Path:
    """Atomically materialize the fixed model-runtime transport descriptor."""
```

Use canonical JSON, mode `0o600`, manifest-validated basename/protocol/prefix,
and fixed `("request", "--workspace", str(workspace))` arguments. Add only the
descriptor path to the child environment; retain legacy variables.

- [ ] **Step 5: Prove production code avoids compatibility imports**

Extend the boundary checker with application ownership rules for modules changed
in this task. Run:

```sh
make check-package-boundaries
uv run --project packages/grid-agent pytest \
  packages/grid-agent/tests/cli \
  packages/grid-agent/tests/runtime \
  packages/grid-agent/tests/domain \
  packages/grid-agent/tests/application -q
```

Expected: PASS.

- [ ] **Step 6: Run offline E2E before committing**

```sh
uv run --project packages/grid-agent pytest \
  packages/grid-agent/tests/e2e/test_offline_walking_skeleton.py \
  packages/grid-agent/tests/e2e/test_semantic_pi_path.py -q
```

Expected: PASS with the two-key stdout envelope and current grid request surface.

- [ ] **Step 7: Commit application assembly**

```sh
git add packages/grid-agent/pyproject.toml packages/grid-agent/uv.lock \
  packages/grid-agent/src/grid_agent/cli/app.py \
  packages/grid-agent/src/grid_agent/runtime \
  packages/grid-agent/tests/cli packages/grid-agent/tests/runtime \
  packages/grid-agent/tests/contract/test_package_extraction_baseline.py \
  tools/check_package_boundaries.py
git commit -m "refactor: assemble grid agent from extracted packages"
```

---

### Task 8: Prove clean artifact installation

**Files:**

- Create: `tools/test_package_artifacts.sh`
- Create: `packages/grid-agent/tests/contract/installed_smoke.py`
- Modify: `Makefile`
- Modify: `.gitignore` if build directories are not already ignored

**Interfaces:**

- Consumes: all three package manifests and public APIs.
- Produces: `make test-packages`, a hermetic provider-free build/install/import/composition gate.

- [ ] **Step 1: Write the installed smoke program**

The program must run from a non-repository temporary directory and verify:

```python
from capability_agent import DomainManifest
from pandapower_domain import build_pandapower_profile

profile = build_pandapower_profile()
profile.manifest.assert_resources_present()
assert isinstance(profile.manifest, DomainManifest)
assert profile.manifest.protocol == "grid-capability"
assert profile.manifest.executable_name == "gridctl"
print("installed-smoke: ok")
```

It must also materialize the catalog and guide index using a fake executor so no
provider or real simulation is required.

- [ ] **Step 2: Implement the clean artifact gate**

`tools/test_package_artifacts.sh` must use `set -euo pipefail`, create its root
with `mktemp -d`, register a trap that removes only that exact temporary root,
and perform:

```sh
uv build --project packages/capability-agent-kernel --out-dir "$artifact_dir"
uv build --project packages/grid-simulator --out-dir "$artifact_dir"
uv build --project packages/pandapower-domain-pack --out-dir "$artifact_dir"
uv build --project packages/grid-agent --out-dir "$artifact_dir"
npm pack --prefix packages/pi-capability-tools --pack-destination "$artifact_dir"
npm pack --prefix packages/pi-grid-tools --pack-destination "$artifact_dir"
```

Create a clean venv and install the four local wheels in one `uv pip install`
invocation so locked external runtime dependencies are resolved normally while
the four project distributions come only from `$artifact_dir`. Change directory
outside the repository and run `installed_smoke.py`. Inspect both npm tarball
file lists and reject source-map, secret, `.env`, cache, test fixture, or
repository-root leakage.

- [ ] **Step 3: Add the Make target and run the red gate**

```make
.PHONY: test-packages

test-packages:
	bash tools/test_package_artifacts.sh
```

Run `make test-packages`. Expected initially: FAIL on missing wheel metadata,
resource inclusion, or local dependency resolution discovered by the clean
install.

- [ ] **Step 4: Fix only artifact defects and rerun**

Adjust Hatch includes, package exports, and npm `files` fields until:

```text
package-boundaries: ok
installed-smoke: ok
package-artifacts: ok
```

Do not add repository-path fallbacks to make the test pass.

- [ ] **Step 5: Commit the artifact gate and packaging fixes**

```sh
git add tools/test_package_artifacts.sh \
  packages/grid-agent/tests/contract/installed_smoke.py \
  packages/capability-agent-kernel/pyproject.toml \
  packages/grid-simulator/pyproject.toml \
  packages/pandapower-domain-pack/pyproject.toml \
  packages/grid-agent/pyproject.toml \
  packages/pi-capability-tools/package.json \
  packages/pi-grid-tools/package.json \
  packages/pi-capability-tools/package-lock.json \
  packages/pi-grid-tools/package-lock.json Makefile .gitignore
git commit -m "test: prove extracted package installation"
```

Stage only manifests changed by the artifact fixes.

---

### Task 9: Close documentation, climb score, and repository gates

**Files:**

- Modify: `README.md`
- Modify: `README.zh-CN.md`
- Modify: `docs/RUNBOOK.md`
- Modify: `docs/architecture/pandapower-capability-composition.md`
- Modify: `docs/superpowers/specs/2026-08-27-general-domain-agent-framework-upgrade-design.md`
- Modify: `docs/status/CURRENT-STATE.md`
- Modify: `docs/status/JOURNAL.md`
- Modify: `docs/status/RESUME-NEXT-SESSION.md`
- Modify: `docs/status/INDEX.md`
- Modify: `docs/status/climb/*`
- Modify: `tools/climb/*`

**Interfaces:**

- Consumes: final extracted architecture and deterministic verification output.
- Produces: accurate operator documentation, a 100-point Workstream B climb record, and a recoverable clean integration state.

- [ ] **Step 1: Update shared product documentation in lockstep**

Document the four-distribution assembly, source/install setup, resource
ownership, compatibility paths, `make test-packages`, and unchanged external
contracts. Keep English and Chinese README headings, commands, facts, and links
aligned. Mark Workstream B complete only after all gates pass; keep Workstreams
C-E explicitly unimplemented.

- [ ] **Step 2: Reconfigure the climb adapter for Workstream B**

Archive the completed static-analysis session under
`docs/status/climb/_archive/2026-08-18-full-capability/`, add one roll-up row to
`docs/status/INDEX.md`, and initialize session
`2026-08-28-workstream-b-package-extraction` with hypotheses `B-H001` through
`B-H005` from the specification. Update the adapter to calculate exactly:

```text
kernel_independence=25
domain_ownership=20
pi_tool_generalization=15
application_thinness=10
distribution_integrity=10
product_compatibility=20
```

Each nonzero score must be backed by the named command and artifact path in the
cycle manifest. The target checker returns success only at `100` with no release
blocker.

- [ ] **Step 3: Run the smallest final package gates**

```sh
make check-package-boundaries
make test-packages
```

Expected: PASS.

- [ ] **Step 4: Run all supported repository gates**

```sh
make doctor
make test
make test-e2e
make validate
```

Expected: doctor resolves `gridctl`; all Python and Node suites pass; E2E passes;
offline/scripted validation passes; capability matrix remains `24/24` and
release-ready.

- [ ] **Step 5: Run and synchronize the final climb cycle**

Run the project adapter for `B-H005`. Confirm the cycle manifest links the exact
gate outputs, `session-state.json` is complete, `research-tree.md` is regenerated
from structured state, and the score is `100`. Do not edit generated climb views
by hand.

- [ ] **Step 6: Run documentation and worktree hygiene checks**

```sh
test -L CLAUDE.md
test "$(readlink CLAUDE.md)" = "AGENTS.md"
git diff --check
git status --short --branch
git worktree list
```

Expected: the symlink contract holds, no whitespace errors exist, only intended
project-state changes remain uncommitted before their dedicated state commit,
and no temporary feature worktree remains after integration.

- [ ] **Step 7: Commit documentation and durable state separately**

```sh
git add README.md README.zh-CN.md docs/RUNBOOK.md \
  docs/architecture/pandapower-capability-composition.md \
  docs/superpowers/specs/2026-08-27-general-domain-agent-framework-upgrade-design.md
git commit -m "docs: document extracted domain framework packages"
```

Then journal that commit, refresh the structural snapshot and live checkpoint,
stage only `docs/status/` and `tools/climb/` paths owned by the climb/state
transition, verify the staged diff, and commit:

```sh
git commit -m "chore: close workstream b climb ladder"
```

- [ ] **Step 8: Perform final review before claiming completion**

Review the whole Workstream B commit range for correctness, security boundaries,
package isolation, compatibility, test adequacy, and documentation truth. Resolve
all findings, rerun affected focused tests plus the complete gates, and record the
final evidence in the project journal and active checkpoint.

---

## Execution Order and Checkpoints

Execute Tasks 1-9 in order. Tasks 2 and 3 establish the Python kernel before the
Node and domain packages consume it. Task 4 may be reviewed independently after
Task 2, but it must land before Task 7. Tasks 5 and 6 establish a domain package
with no application dependency before Task 7 switches application imports.
Task 8 is the artifact-level truth gate; Task 9 cannot award a 100 score without
it.

After every commit:

1. append one `project-state journal` line with the commit hash;
2. synchronize structured climb state for the active hypothesis;
3. run the focused tests owned by the task;
4. refresh the live checkpoint at recovery thresholds;
5. preserve all unrelated working-tree changes.

No task may be marked complete solely because files moved or imports resolve.
The relevant behavior and boundary tests must pass from the owning distribution.
