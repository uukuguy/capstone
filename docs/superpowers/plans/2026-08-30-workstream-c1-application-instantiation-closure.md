# Workstream C.1 Application Instantiation Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Design reference:** [`2026-08-30-domain-application-instantiation-closure-design.md`](../specs/2026-08-30-domain-application-instantiation-closure-design.md)

**Goal:** Build a domain-neutral application-instantiation path, express pandapower as its first complete Domain Pack, and prove both existing business task files through that path before claiming a second domain or multi-domain runtime.

**Architecture:** `capability-agent-kernel` gains complete application, binding, output, context, runtime, and lifecycle contracts. `pandapower-domain-pack` owns every grid-specific provisioner, state, projection, answer, presentation, and domain-output component. `grid-agent` becomes a thin composition and compatibility entry point; inventory remains an incomplete fixture.

**Tech Stack:** Python >=3.12, Hatchling, uv, Pydantic >=2.12,<3, pytest >=9,<10, Node.js >=22.19.0, npm, ESM, Pi 0.80.6, JSON Schema, `grid-capability/1.0`, pandapower 3.4.0.

## Global Constraints

- Execute on the existing `main` worktree. Do not create or leave a feature branch or temporary worktree.
- Preserve unrelated tracked and untracked changes; stage only task-owned files. Project-state journal/checkpoint edits remain separate bookkeeping.
- The dependency direction remains `grid-agent -> pandapower-domain-pack -> capability-agent-kernel`; Kernel and Domain Pack must not depend on `grid-agent`.
- Generic Kernel/Application sources must not import or recognize `grid_agent`, `grid_simulator`, `pandapower_domain`, `pandapower`, `gridctl`, fixed `grid_*` names, voltage, bus, branch, power-flow, or N-1 semantics.
- A generic result contains a Kernel-owned `core` section and one Domain Pack-owned output per binding. Generic renderers preserve both; only explicit versioned compatibility adapters may project them lossily.
- The existing `grid-agent` compatibility entry continues to write exactly one JSON object containing only `question_id` and `answer_output` to stdout. Diagnostics remain on stderr.
- New generic context, runtime, output, and artifact defaults use domain-neutral schemas and layouts. No generic default is derived from v1.0.1 naming.
- Pandapower facts continue to cross `gridctl` through `grid-capability/1.0`; no shell, arbitrary subprocess, generic file, Python, raw pandapower object, or DataFrame capability is exposed to the model.
- The initial runtime accepts exactly one `DomainBinding`. Tuple-shaped contracts do not constitute multi-domain support.
- Inventory remains a provider-free capability/domain fixture. Do not add inventory business features, CLI, presentation claims, or completion claims.
- Provider-backed execution of `task.md.txt` and `test.md.txt` is a final hard gate and requires explicit credential and billing authorization at execution time.
- Every behavior task uses red-green-refactor, ends with focused regression evidence, and lands as one atomic task-owned commit.

---

## File and Ownership Map

### Kernel application and complete Domain Pack contracts

- Create `packages/capability-agent-kernel/src/capability_agent/application/{errors,manifest,profile,registry,output}.py` for application identity, bindings, registration, and two-part output.
- Create `packages/capability-agent-kernel/src/capability_agent/domain/{provisioning,state,policy,guide,presentation,output,acceptance}.py` for complete Domain Pack ports.
- Create `packages/capability-agent-kernel/src/capability_agent/application/{context_models,context_reducer,context_store,workspace,turns,projector,runner,reporting}.py` for the neutral application engine.
- Create `packages/capability-agent-kernel/src/capability_agent/runtime/` for generic provider/Pi setup, descriptor, launch, RPC, and tracing.

### Generic Pi transport

- Modify `packages/capability-agent-kernel/src/capability_agent/tools/catalog.py` to separate application-core and bound-domain tools.
- Modify `packages/pi-capability-tools/src/domain-tools.mjs` to accept a binding-aware controller descriptor while retaining the legacy descriptor reader.

### Pandapower complete domain

- Create `packages/pandapower-domain-pack/src/pandapower_domain/{provisioning,state,answer_policy,guide,presentation,output,acceptance}.py`.
- Refactor grid semantics from `grid_agent.analysis` and `grid_agent.trajectory` into those components.
- Modify `packages/pandapower-domain-pack/src/pandapower_domain/profile.py` to supply every complete-domain component.

### Application composition and compatibility

- Create `packages/grid-agent/src/grid_agent/application/profile.py` for the explicit pandapower Application Profile.
- Create `packages/grid-agent/src/grid_agent/compat/v1_0_1.py` for legacy CLI, output, aliases, workspace, and readers.
- Modify `packages/grid-agent/src/grid_agent/cli/app.py` to delegate generic and compatibility commands.
- Update validation, packaging, Makefile, runbook, architecture docs, and aligned bilingual READMEs.

---

### Task 0: Lock the C.1 baseline and stronger ownership gate

**Files:**
- Create: `packages/grid-agent/tests/contract/test_application_instantiation_baseline.py`
- Modify: `tools/check_package_boundaries.py`
- Modify: `tools/tests/test_check_package_boundaries.py`
- Modify: `Makefile`

**Interfaces:**
- Consumes: current v1.0.1 CLI, both canonical instruction files, and the existing package-boundary checker.
- Produces: `make check-application-boundaries` plus characterization evidence that remains green during migration.

- [ ] **Step 1: Write baseline and boundary-checker tests**

```python
def test_canonical_business_task_files_are_distinct_and_nonempty(repo_root: Path) -> None:
    task = load_questions(repo_root / "validation/questions/task.md.txt")
    test = load_questions(repo_root / "validation/questions/test.md.txt")
    assert task
    assert test
    assert task != test


def test_grid_compatibility_envelope_has_exact_keys(cli_runner) -> None:
    result = cli_runner.invoke(["run", "--offline", "母线电压正常运行范围是多少?"])
    assert result.exit_code == 0
    assert set(json.loads(result.stdout)) == {"question_id", "answer_output"}
```

Add a checker fixture containing
`packages/capability-agent-kernel/src/capability_agent/application/bad.py` with
`GRID_TOOL = "grid_analysis_powerflow_ac"`; require the sorted diagnostic
`contains grid-owned semantic token grid_`.

- [ ] **Step 2: Run the focused tests and verify RED**

```sh
uv run --project packages/grid-agent pytest \
  packages/grid-agent/tests/contract/test_application_instantiation_baseline.py \
  tools/tests/test_check_package_boundaries.py -q
```

Expected: baseline tests pass; the new semantic-token fixture fails because the
checker currently enforces imports and source paths but not application
semantic literals.

- [ ] **Step 3: Add the application semantic gate**

```python
FORBIDDEN_GENERIC_PATTERNS = {
    "gridctl": re.compile(r"(?<![a-z0-9_])gridctl(?![a-z0-9_])"),
    "grid_": re.compile(r"\bgrid_[a-z0-9_]*\b"),
    "pandapower": re.compile(r"(?<![a-z0-9_])pandapower(?:_domain)?(?![a-z0-9_])"),
    "power-flow": re.compile(r"\bpower[-_ ]?flow\b"),
    "voltage": re.compile(r"\bvoltage\b"),
    "bus": re.compile(r"\bbus(?:es)?\b"),
    "branch": re.compile(r"\bbranch(?:es)?\b"),
    "n-1": re.compile(r"\bn[-_ ]?1\b"),
}


def check_generic_semantic_literals(root: Path, source_root: Path) -> list[str]:
    violations: list[str] = []
    for path in sorted(source_root.rglob("*.py")):
        text = path.read_text(encoding="utf-8").lower()
        for token, pattern in FORBIDDEN_GENERIC_PATTERNS.items():
            if pattern.search(text):
                relative = path.relative_to(root).as_posix()
                violations.append(f"{relative} contains grid-owned semantic token {token}")
    return violations
```

Expose the checker as `check-application-boundaries` in `Makefile`; do not add a
second scanner script.

- [ ] **Step 4: Run focused and current gates**

```sh
uv run --project packages/grid-agent pytest \
  packages/grid-agent/tests/contract/test_application_instantiation_baseline.py \
  tools/tests/test_check_package_boundaries.py -q
make check-package-boundaries
```

Expected: all pass and `package-boundaries: ok` is printed.

- [ ] **Step 5: Commit the baseline**

```sh
git add Makefile tools/check_package_boundaries.py \
  tools/tests/test_check_package_boundaries.py \
  packages/grid-agent/tests/contract/test_application_instantiation_baseline.py
git commit -m "test: lock application instantiation boundaries"
```

---

### Task 1: Publish application, complete-domain, and two-part output contracts

**Files:**
- Create: `packages/capability-agent-kernel/src/capability_agent/application/{errors,manifest,profile,registry,output}.py`
- Create: `packages/capability-agent-kernel/src/capability_agent/domain/{provisioning,state,policy,guide,presentation,output,acceptance}.py`
- Modify: `packages/capability-agent-kernel/src/capability_agent/domain/profile.py`
- Modify: `packages/capability-agent-kernel/src/capability_agent/{application,domain}/__init__.py`
- Modify: `packages/capability-agent-kernel/src/capability_agent/__init__.py`
- Test: `packages/capability-agent-kernel/tests/application/{test_contracts,test_output,test_registry}.py`

**Interfaces:**
- Consumes: existing `DomainRuntimeProfile`, authority, executor, projector, and manifest contracts.
- Produces: `ApplicationManifest`, `ApplicationProfile`, `DomainBinding`,
  `DomainRegistry`, `FrameworkOutputComposer`, `DomainRuntimeProvisioner`,
  `DomainStateAdapter`, `AnswerEvidencePolicy`, `DomainPolicyProvider`,
  `GuideProvider`, `PresentationProvider`, `DomainOutputContract`,
  `DomainAcceptanceProfile`, `CredentialScope`, `DataSharingPolicy`,
  `ApplicationPolicy`, `ReportShell`, `AcceptanceProfile`, `OutputRenderer`, and
  complete-profile validation.

- [ ] **Step 1: Write failing contract and ownership tests**

```python
def test_application_profile_rejects_incomplete_fixture(fake_domain_profile) -> None:
    with pytest.raises(ApplicationConfigurationError, match="missing application components"):
        build_application_profile(fake_domain_profile)


def test_framework_output_keeps_core_and_domain_ownership() -> None:
    result = FrameworkOutputComposer().compose(
        core=CoreRunResult(
            application_id="app",
            application_version="1.0.0",
            run_id="run-1",
            status="completed",
            answer_refs=(),
            report_ref=None,
            diagnostic_refs=(),
        ),
        bindings=(BindingIdentity(
            binding_id="grid",
            domain_id="pandapower-static-analysis",
            domain_version="1.0.1",
        ),),
        domains={
            "grid": ValidatedDomainOutput(
                schema="pandapower-static-analysis-output/1.0",
                status="completed",
                payload={"completed_count": 2},
            )
        },
    )
    assert result.core.run_id == "run-1"
    assert result.domains["grid"].payload == {"completed_count": 2}
```

Also reject missing/extra binding outputs and any domain payload attempting to
own top-level `core` or `domains`. Verify every domain-neutral error category is
public: configuration, registration, provisioning, routing, transport,
authority integrity, projection, policy conflict, and answer commit.

- [ ] **Step 2: Run tests and verify RED**

```sh
uv run --project packages/capability-agent-kernel pytest \
  packages/capability-agent-kernel/tests/application -q
```

Expected: collection fails because the contracts do not exist.

- [ ] **Step 3: Implement complete profile and public protocols**

```python
@dataclass(frozen=True, slots=True)
class ApplicationManifest:
    application_id: str
    version: str
    display_name: str
    context_schema: str
    result_schema: str
    artifact_schema: str
    core_tool_namespace: str


@dataclass(frozen=True, slots=True)
class DomainBinding:
    binding_id: str
    tool_namespace: str
    profile: DomainRuntimeProfile
    credential_scope: CredentialScope
    sharing_policy: DataSharingPolicy


@dataclass(frozen=True, slots=True)
class ApplicationProfile:
    manifest: ApplicationManifest
    domains: tuple[DomainBinding, ...]
    output_renderer: OutputRenderer
    application_policy: ApplicationPolicy
    report_shell: ReportShell
    acceptance_profile: AcceptanceProfile
```

No default in these types contains grid, pandapower, gridctl, legacy artifact,
or v1.0.1 output identities.

```python
@dataclass(frozen=True, slots=True)
class DomainRuntimeProfile:
    manifest: DomainManifest
    contract_source: CapabilityContractSource
    executor_factory: ExecutorFactory
    projector_registry: DomainProjectorRegistry
    authority_factory: AuthorityFactory
    tool_description_builder: ToolDescriptionBuilder | None = None
    provisioner: DomainRuntimeProvisioner | None = None
    state_adapter: DomainStateAdapter | None = None
    answer_policy: AnswerEvidencePolicy | None = None
    policy_provider: DomainPolicyProvider | None = None
    guide_provider: GuideProvider | None = None
    presentation_provider: PresentationProvider | None = None
    output_contract: DomainOutputContract | None = None
    acceptance_profile: DomainAcceptanceProfile | None = None

    def missing_application_components(self) -> tuple[str, ...]:
        names = (
            "provisioner", "state_adapter", "answer_policy", "policy_provider",
            "guide_provider",
            "presentation_provider", "output_contract", "acceptance_profile",
        )
        return tuple(name for name in names if getattr(self, name) is None)
```

The optional fields preserve provider-free fixture use. `ApplicationProfile`
rejects a profile when this tuple is non-empty, rejects zero/multiple bindings,
and enforces unique binding/tool namespaces.

- [ ] **Step 4: Implement strict output composition and immutable rendering**

Use strict frozen Pydantic models for `ApplicationResult`, `CoreRunResult`,
`BindingIdentity`, and `ValidatedDomainOutput`. `FrameworkOutputComposer`
creates exactly `schema`, `core`, and `domains`. The JSON renderer canonicalizes
the complete object without transforming either section.

```python
class JsonOutputRenderer:
    def render(self, result: ApplicationResult) -> str:
        return json.dumps(
            result.model_dump(mode="json"), ensure_ascii=False,
            sort_keys=True, separators=(",", ":"),
        ) + "\n"
```

- [ ] **Step 5: Run public API and boundary tests**

```sh
uv run --project packages/capability-agent-kernel pytest \
  packages/capability-agent-kernel/tests/application \
  packages/capability-agent-kernel/tests/test_public_api.py \
  packages/capability-agent-kernel/tests/test_boundaries.py -q
```

Expected: all pass and every public type resolves from `capability_agent.*`.

- [ ] **Step 6: Commit the contracts**

```sh
git add packages/capability-agent-kernel
git commit -m "feat: define complete application contracts"
```

---

### Task 2: Build explicit registration and complete runtime preparation

**Files:**
- Modify: `packages/capability-agent-kernel/src/capability_agent/application/composition.py`
- Modify: `packages/capability-agent-kernel/src/capability_agent/application/registry.py`
- Create: `packages/capability-agent-kernel/tests/application/test_application_composition.py`
- Modify: `packages/capability-agent-kernel/tests/{conftest,test_kernel_composition}.py`

**Interfaces:**
- Consumes: Task 1 contracts.
- Produces: `prepare_application(...) -> PreparedApplication` with deterministic prepared bindings.

- [ ] **Step 1: Write failing preparation tests**

```python
def test_prepare_application_resolves_only_explicit_registration(complete_profile, tmp_path) -> None:
    registry = DomainRegistry()
    registry.register("fixture-domain", "1.0.0", lambda: complete_profile.domains[0].profile)
    prepared = prepare_application(
        complete_profile,
        registry=registry,
        workspace=tmp_path / "run",
        credentials=EmptyCredentialBroker(),
    )
    assert tuple(prepared.bindings) == ("fixture",)
```

Add cases for unregistered domain, version mismatch, wrong factory manifest,
multiple bindings, provisioner failure before a provider-start probe,
credential-scope mismatch, secret-bearing endpoint metadata, and conflicting
Kernel/application/domain policy fragments.

- [ ] **Step 2: Run tests and verify RED**

```sh
uv run --project packages/capability-agent-kernel pytest \
  packages/capability-agent-kernel/tests/application/test_application_composition.py -q
```

Expected: FAIL because `prepare_application` does not exist.

- [ ] **Step 3: Implement deterministic preparation**

```python
@dataclass(frozen=True, slots=True)
class PreparedBinding:
    binding: DomainBinding
    endpoint: PreparedDomainEndpoint
    runtime: PreparedDomainRuntime


@dataclass(frozen=True, slots=True)
class PreparedApplication:
    profile: ApplicationProfile
    bindings: Mapping[str, PreparedBinding]
```

Resolve registered factories, compare exact domain identity/version, prepare
sorted bindings beneath `workspace/domains/<binding_id>/`, and clean endpoints
in reverse order on failure. Composition does not call provider code.

Issue one binding-scoped credential lease at a time, reject credentials in
descriptors/events/results, default cross-domain sharing to denied, and compose
policy fragments in deterministic Kernel/application/domain order. A
`PolicyConflictError` or scope mismatch aborts before provider startup.

- [ ] **Step 4: Preserve the low-level fixture path**

Keep `prepare_domain_runtime()` public. Prove an incomplete inventory-like fake
still materializes a catalog through that function but is rejected by
`prepare_application()`.

- [ ] **Step 5: Run composition regression and commit**

```sh
uv run --project packages/capability-agent-kernel pytest \
  packages/capability-agent-kernel/tests/test_kernel_composition.py \
  packages/capability-agent-kernel/tests/application/test_application_composition.py -q
git add packages/capability-agent-kernel
git commit -m "feat: prepare explicitly registered applications"
```

---

### Task 3: Separate core tools and add binding-aware Pi transport

**Files:**
- Modify: `packages/capability-agent-kernel/src/capability_agent/tools/catalog.py`
- Create: `packages/capability-agent-kernel/tests/tools/test_composite_catalog.py`
- Modify: `packages/pi-capability-tools/src/domain-tools.mjs`
- Modify: `packages/pi-capability-tools/test/domain-tools.test.mjs`
- Modify: `packages/grid-agent/src/grid_agent/runtime/pi_config.py` as a temporary compatibility caller.

**Interfaces:**
- Consumes: `DomainBinding`, `PreparedBinding`, current capability documents, and the legacy descriptor.
- Produces: `CompositeToolCatalog`, `capability-agent-runtime/1.0`, bound routing metadata, and legacy descriptor support.

- [ ] **Step 1: Write failing composite-catalog tests**

```python
def test_composite_catalog_keeps_core_tools_out_of_domain_catalog() -> None:
    catalog = CompositeToolCatalog.build(
        core=CoreToolCatalog.default(namespace="agent_"),
        domains=(BoundDomainCatalog.fixture("grid", "grid_", (grid_contract,)),),
    )
    assert [tool.name for tool in catalog.core_tools] == ["agent_record_decision"]
    assert [tool.name for tool in catalog.domain_tools] == ["grid_context_open"]
    assert catalog.require("grid_context_open").key == CapabilityKey("grid", "context.open")
```

Add collision tests for binding IDs, final names, guide/context names, and
reserved `agent_` names.

- [ ] **Step 2: Write failing Node descriptor and routing tests**

```js
const runtimeV1 = {
  schema: "capability-agent-runtime/1.0",
  application: { applicationId: "fixture-app", runId: "run-1" },
  core: { decisionToolName: "agent_record_decision", contextToolName: "agent_context_get" },
  domains: [{
    bindingId: "inventory",
    protocol: "inventory-capability",
    protocolVersion: "1.0",
    executable: "inventoryctl",
    executableArgs: ["request", "--workspace", "/tmp/run/domains/inventory"],
    toolCatalogPath: "/tmp/run/domains/inventory/tool-catalog.json",
    guideToolName: "inventory_guide_open",
    guideIndexPath: "/tmp/run/domains/inventory/guide-index.json",
    guideRootPath: "/tmp/run/domains/inventory/guides",
    guideIndexSha256: "a".repeat(64),
    workspacePath: "/tmp/run/domains/inventory",
    authorityId: "inventoryctl",
  }],
};
```

Assert an inventory tool routes only through this binding and model parameters
cannot override binding, executable, protocol, authority, or workspace.

- [ ] **Step 3: Run tests and verify RED**

```sh
uv run --project packages/capability-agent-kernel pytest \
  packages/capability-agent-kernel/tests/tools/test_composite_catalog.py -q
npm test --prefix packages/pi-capability-tools
```

Expected: Python import failure and Node rejection of the new descriptor keys.

- [ ] **Step 4: Implement catalog and descriptor composition**

Remove automatic decision-tool creation from each `ToolCatalog`; add it through
`CoreToolCatalog`. A bound domain tool stores `CapabilityKey`, authority,
protocol, and version as controller metadata. JavaScript validates the top-level
key allowlist, requires exactly one domain during C.1, and confines every path
to that binding workspace.

Keep the current descriptor validator and convert it through
`legacyDescriptorToRuntimeV1()`; do not change existing grid request/response
wire behavior.

- [ ] **Step 5: Run transport and boundary regression**

```sh
npm run check --prefix packages/pi-capability-tools
npm test --prefix packages/pi-capability-tools
npm run check --prefix packages/pi-grid-tools
npm test --prefix packages/pi-grid-tools
make check-package-boundaries
```

Expected: all pass; generic source has no product-specific literal; the grid
wrapper remains compatible.

- [ ] **Step 6: Commit transport composition**

```sh
git add packages/capability-agent-kernel packages/pi-capability-tools \
  packages/pi-grid-tools packages/grid-agent/src/grid_agent/runtime/pi_config.py
git commit -m "feat: route bound domain capability tools"
```

---

### Task 4: Implement generic Application Context, workspace, and replay

**Files:**
- Create: `packages/capability-agent-kernel/src/capability_agent/application/{context_models,context_reducer,context_store,workspace}.py`
- Create: `packages/capability-agent-kernel/tests/application/{test_context_reducer,test_context_store,test_workspace}.py`

**Interfaces:**
- Consumes: Task 1 identities and existing trajectory primitives.
- Produces: `ApplicationContext`, `ContextEventDraft`, `ApplicationContextStore`, `ApplicationWorkspace`, and domain-state revision enforcement.

- [ ] **Step 1: Write failing context tests**

```python
def test_domain_delta_can_update_only_its_binding(initial_context) -> None:
    changed = reduce_context(
        initial_context,
        ContextEventDraft(
            event_type="domain.state.projected",
            binding_id="grid",
            payload={
                "schema_id": "pandapower-analysis-state/1.0",
                "previous_revision": 0,
                "state": {"active_context_ref": "context:sha256:" + "a" * 64},
            },
        ),
    )
    assert changed.domains["grid"].revision == 1
```

Reject unknown binding, schema drift, stale revision, foreign reference
ownership, and sibling-binding fields.

- [ ] **Step 2: Write workspace/store tests and verify RED**

Require:

```text
runs/<run_id>/
  core/{context.json,context-events.jsonl,events.jsonl,artifacts.jsonl}
  domains/<binding_id>/{runtime,artifacts,tool-results}
  turns/
  output/
```

Test exclusive creation, portable IDs, no-follow roots, fsync append, atomic
snapshot replace, replay hashes, and snapshot mismatch. Run:

```sh
uv run --project packages/capability-agent-kernel pytest \
  packages/capability-agent-kernel/tests/application/test_context_reducer.py \
  packages/capability-agent-kernel/tests/application/test_context_store.py \
  packages/capability-agent-kernel/tests/application/test_workspace.py -q
```

Expected: collection fails because the modules do not exist.

- [ ] **Step 3: Implement strict context models and reducer**

```python
class DomainStateEnvelope(StrictFrozenModel):
    schema_id: str
    revision: int = 0
    state: dict[str, Any] = Field(default_factory=dict)


class ApplicationContext(StrictFrozenModel):
    schema_version: Literal["application-context/1.0"] = "application-context/1.0"
    run_id: str
    revision: int
    state_hash: str
    status: Literal["initializing", "running", "completed", "failed"]
    core: CoreContext
    domains: dict[str, DomainStateEnvelope]
```

The reducer recognizes a closed event allowlist and recalculates the canonical
state hash after every transition.

- [ ] **Step 4: Implement durable store and workspace**

Port the proven append/fsync/atomic-replace/replay pattern from
`grid_agent.analysis.store` without importing it. Create domain directories
only from declared binding IDs; never guess a domain artifact layout.

- [ ] **Step 5: Run context/trajectory/boundary tests and commit**

```sh
uv run --project packages/capability-agent-kernel pytest \
  packages/capability-agent-kernel/tests/application \
  packages/capability-agent-kernel/tests/trajectory -q
make check-package-boundaries
git add packages/capability-agent-kernel
git commit -m "feat: add generic application context"
```

---

### Task 5: Implement generic turn, answer, and binding-aware projection

**Files:**
- Create: `packages/capability-agent-kernel/src/capability_agent/application/{turns,projector}.py`
- Create: `packages/capability-agent-kernel/tests/application/{test_turns,test_projector}.py`
- Modify: `packages/capability-agent-kernel/src/capability_agent/trajectory/answers.py`

**Interfaces:**
- Consumes: context store, composite catalog, prepared binding, authority, state adapter, and answer policy.
- Produces: `TurnController`, `ApplicationInvocationProjector`, and binding-qualified committed answers.

- [ ] **Step 1: Write failing answer-policy tests**

```python
def test_submit_uses_selected_binding_answer_policy(active_turn, prepared_binding) -> None:
    controller = TurnController(
        store=active_turn.store,
        workspace=active_turn.workspace,
        bindings={"grid": prepared_binding},
        recorder=active_turn.recorder,
    )
    committed = controller.submit(
        active_turn.handle,
        answer_output="verified answer",
        referenced_bindings=("grid",),
        result_refs=("result:sha256:" + "a" * 64,),
        evidence_refs=("evidence:sha256:" + "b" * 64,),
        duration_seconds=1.0,
    )
    assert committed.referenced_bindings == ("grid",)
```

Reject undeclared bindings, foreign-run references, wrong authorities, and
claims missing the selected domain policy's required evidence.

- [ ] **Step 2: Write failing projector tests**

Use events resolved to a structured `CapabilityKey`. Assert only the matching
authority and state adapter run, core references remain opaque, and the delta
targets only that binding. Integrity failure adds no result/evidence/state.

- [ ] **Step 3: Run tests and verify RED**

```sh
uv run --project packages/capability-agent-kernel pytest \
  packages/capability-agent-kernel/tests/application/test_turns.py \
  packages/capability-agent-kernel/tests/application/test_projector.py -q
```

Expected: collection fails because the generic controller/projector do not
exist.

- [ ] **Step 4: Port lifecycle and inject domain decisions**

Move nonce, active-turn, draft, allowed-reference, and commit mechanics from the
grid controller. Replace grid policy/verifier/exception imports with the
binding's public policies and Kernel error types.

`ApplicationInvocationProjector.observe()` resolves the bound tool, admits
references, appends generic observation events, invokes the state adapter, and
appends only a validated namespaced delta.

- [ ] **Step 5: Run lifecycle tests and commit**

```sh
uv run --project packages/capability-agent-kernel pytest \
  packages/capability-agent-kernel/tests/application \
  packages/capability-agent-kernel/tests/trajectory/test_answers.py -q
make check-package-boundaries
git add packages/capability-agent-kernel
git commit -m "feat: add generic turn and projection lifecycle"
```

---

### Task 6: Extract the generic provider/Pi runtime and ordered application runner

**Files:**
- Create: `packages/capability-agent-kernel/src/capability_agent/runtime/{models,catalog,resolver,lock,installer,locator,extension,environment,descriptor,rpc,trace}.py`
- Create: `packages/capability-agent-kernel/src/capability_agent/application/{runner,reporting}.py`
- Create: `packages/capability-agent-kernel/tests/runtime/{test_catalog,test_resolver,test_environment,test_descriptor,test_rpc}.py`
- Create: `packages/capability-agent-kernel/tests/application/{test_runner,test_reporting}.py`
- Modify: `packages/capability-agent-kernel/src/capability_agent/{__init__,application/__init__}.py`
- Modify: `packages/capability-agent-kernel/pyproject.toml`
- Modify: `packages/grid-agent/src/grid_agent/config/{models,catalog,resolver}.py`
- Modify: `packages/grid-agent/src/grid_agent/runtime/{lock,installer,locator,extension,environment,rpc}.py`
- Modify: `packages/grid-agent/src/grid_agent/observability/trace.py`

**Interfaces:**
- Produces: `AgentApplication`, `ApplicationRequest`, `ApplicationOutcome`,
  generic provider selection, generic Pi runtime setup, and a generic report
  shell.
- Consumes: a prepared application, a `ProviderCatalogSource`, ordered
  questions, `TurnController`, `ApplicationInvocationProjector`, and the
  composite output contract.

- [ ] **Step 1: Write a failing domain-neutral runtime launch test**

Build a prepared endpoint whose executable is `domainctl` and whose search
path is `/opt/domain/bin`. Assert that the generated child environment contains
that path, a binding-aware runtime descriptor, and only scrubbed
`CAPABILITY_AGENT_*` controller values. Assert the Kernel source contains no
`gridctl`, `GRID_AGENT_*`, or `pi-grid-tools` literals.

- [ ] **Step 2: Write a failing ordered-runner test**

Use fake provider, transport, binding, and renderer implementations. Submit two
ordered questions and assert:

```python
assert outcome.result.schema == "capability-agent-output/1.0"
assert outcome.result.core.status == "completed"
assert tuple(outcome.result.domains) == ("alpha",)
assert outcome.result.domains["alpha"].payload["completed_count"] == 2
```

Also assert provider startup occurs only after registration, provisioning,
policy composition, guide validation, and catalog validation have succeeded.

- [ ] **Step 3: Run the focused tests and verify RED**

```sh
uv run --project packages/capability-agent-kernel pytest \
  packages/capability-agent-kernel/tests/runtime \
  packages/capability-agent-kernel/tests/application/test_runner.py \
  packages/capability-agent-kernel/tests/application/test_reporting.py -q
```

Expected: collection fails because the generic runtime and runner modules do
not exist.

- [ ] **Step 4: Move reusable runtime mechanics behind neutral interfaces**

Port provider catalog resolution, lock verification, package installation,
executable lookup, extension configuration, scrubbed environment construction,
RPC framing, and tracing from `grid_agent`. Inject `ProviderCatalogSource` and
`PreparedDomainEndpoint` values. Use `CAPABILITY_AGENT_*` for new defaults and
emit `capability-agent-runtime/1.0`; do not infer a domain executable or tool
package in Kernel code.

Keep the existing grid modules as thin compatibility imports until Task 9.
Add `filelock` and `python-dotenv` to the Kernel package when the ported modules
import them directly; retain the existing Pydantic version range.

- [ ] **Step 5: Implement the generic application runner and report shell**

`AgentApplication.run()` must:

1. prepare the application;
2. start the provider transport;
3. process questions in input order;
4. persist core and binding-qualified lifecycle data;
5. build each validated domain output;
6. compose the framework result;
7. render only after both output layers validate;
8. clean up bindings in reverse preparation order.

The generic report shell owns question/answer/trajectory/reference structure;
it delegates all domain labels and business summaries to the selected
`PresentationProvider`.

- [ ] **Step 6: Run focused and compatibility tests**

```sh
uv run --project packages/capability-agent-kernel pytest \
  packages/capability-agent-kernel/tests/runtime \
  packages/capability-agent-kernel/tests/application -q
uv run --project packages/grid-agent pytest \
  packages/grid-agent/tests/config \
  packages/grid-agent/tests/runtime \
  packages/grid-agent/tests/reporting -q
make check-package-boundaries
```

Expected: all selected tests and package-boundary checks pass.

- [ ] **Step 7: Commit the runtime extraction**

```sh
git add packages/capability-agent-kernel packages/grid-agent/src/grid_agent/config \
  packages/grid-agent/src/grid_agent/runtime packages/grid-agent/src/grid_agent/observability/trace.py
git commit -m "feat: extract generic agent application runtime"
```

---

### Task 7: Complete the pandapower Domain Pack

**Files:**
- Create: `packages/pandapower-domain-pack/src/pandapower_domain/{provisioning,state,answer_policy,guide,presentation,output,acceptance}.py`
- Create: `packages/pandapower-domain-pack/tests/{test_provisioning,test_state,test_answer_policy,test_guide,test_presentation,test_output,test_acceptance}.py`
- Modify: `packages/pandapower-domain-pack/src/pandapower_domain/{profile,projection,__init__}.py`
- Modify: `packages/pandapower-domain-pack/pyproject.toml`
- Modify: `packages/grid-agent/src/grid_agent/analysis/{models,reducer,view,domain_projection}.py`
- Modify: `packages/grid-agent/src/grid_agent/trajectory/{answer_policy,business_projection,context_projection}.py`
- Modify: `packages/grid-agent/tests/domain/test_pandapower_profile.py`

**Interfaces:**
- Produces: the complete public `DomainRuntimeProfile` for pandapower, including
  provisioning, state, answer evidence, presentation, domain output, and
  acceptance.
- Preserves: `grid-capability/1.0`, `gridctl` authority, current-run evidence,
  semantic tool schemas, and the simulator truth boundary.

- [ ] **Step 1: Write the complete-profile failure test**

```python
def test_pandapower_profile_is_application_complete() -> None:
    profile = build_pandapower_profile()
    assert profile.missing_application_components() == ()
    assert profile.output_contract.schema_id == (
        "pandapower-static-analysis-output/1.0"
    )
```

Assert each provider is declared in `pandapower_domain`, not imported from
`grid_agent`.

- [ ] **Step 2: Write focused provider tests**

Cover these exact behaviors:

- the provisioner installs or resolves `gridctl`, pins fixed arguments, limits,
  scrubbed environment, and a binding-owned executable search path;
- the state adapter validates schema/revision and rejects another binding;
- the answer policy rejects unsupported numerical, ranking, topology,
  contingency, and evidence claims;
- the guide provider publishes only digest-bound allowlisted guide documents;
- the presenter renders model/network/scenario/calculation summaries without
  exposing raw DataFrames or pandapower objects;
- the output contract emits only the validated pandapower payload;
- acceptance declares both repository business task files as provider-backed
  cases and the deterministic scripted cases used in Task 10.

- [ ] **Step 3: Run the Domain Pack tests and verify RED**

```sh
uv run --project packages/pandapower-domain-pack pytest \
  packages/pandapower-domain-pack/tests -q
```

Expected: the new tests fail because the profile is still only a low-level
capability fixture.

- [ ] **Step 4: Move pandapower decisions into the Domain Pack**

Port grid state schema, reducer, context presentation, business projections,
answer-reference policy, and runtime provisioning into the new modules.
Keep generic event and reference handling in the Kernel. Keep simulator data
opaque and execute every network-specific capability through `gridctl`.

The grid-agent modules changed in this task become compatibility imports or
adapters; they must not remain alternate owners of the same policy.

- [ ] **Step 5: Implement and validate the pandapower output contract**

Build:

```json
{
  "domain_id": "pandapower-static-analysis",
  "domain_version": "1.0.1",
  "schema": "pandapower-static-analysis-output/1.0",
  "status": "completed",
  "payload": {
    "mode": "continuous-static-analysis",
    "instruction_count": 2,
    "completed_count": 2,
    "failed_count": 0,
    "report_artifact_ref": "artifact:sha256:..."
  }
}
```

Validation rejects framework fields, sibling binding fields, unknown required
payload omissions, and report references not admitted for the current run.

- [ ] **Step 6: Run focused regressions and commit**

```sh
uv run --project packages/pandapower-domain-pack pytest \
  packages/pandapower-domain-pack/tests -q
uv run --project packages/grid-agent pytest \
  packages/grid-agent/tests/analysis \
  packages/grid-agent/tests/trajectory \
  packages/grid-agent/tests/domain/test_pandapower_profile.py -q
make check-package-boundaries
git add packages/pandapower-domain-pack packages/grid-agent/src/grid_agent/analysis \
  packages/grid-agent/src/grid_agent/trajectory \
  packages/grid-agent/tests/domain/test_pandapower_profile.py
git commit -m "feat: complete pandapower domain application"
```

---

### Task 8: Make reports and the trajectory workbench binding-aware

**Files:**
- Modify: `packages/grid-agent/src/grid_agent/trajectory/{service,projection_models,business_projection,context_projection}.py`
- Modify: `packages/grid-agent/src/grid_agent/trajectory/api/{models,catalog,projection_pages}.py`
- Modify: `packages/grid-agent/tests/trajectory/test_service.py`
- Modify: `packages/grid-agent/tests/trajectory/projections/{test_business,test_context}.py`
- Modify: `packages/trajectory-workbench/src/api/{types,business}.ts`
- Modify: `packages/trajectory-workbench/src/views/{BusinessView,ContextView}.tsx`
- Modify: `packages/trajectory-workbench/src/api/{types.test,business.test}.ts`
- Modify: `packages/trajectory-workbench/src/views/{BusinessView.test,ContextView.test}.tsx`

**Interfaces:**
- Reads: application identity and binding/authority metadata recorded by the
  generic runtime.
- Displays: framework lifecycle separately from each domain-owned projection;
  unknown domain payloads remain inspectable without grid interpretation.

- [ ] **Step 1: Write failing binding-aware projection tests**

Record one generic run with binding `grid` and one fixture run with binding
`inventory`. Assert API responses use `binding_id`, `domain_id`, `authority_id`,
and schema metadata rather than a fixed `gridctl` authority. Assert an unknown
domain returns a generic payload view instead of a grid-shaped empty object.

- [ ] **Step 2: Write failing workbench tests**

Assert the UI labels the Kernel `core` timeline separately, selects a domain by
binding ID, renders pandapower through its presentation metadata, and renders
unknown payloads as read-only structured data.

- [ ] **Step 3: Run the focused tests and verify RED**

```sh
uv run --project packages/grid-agent pytest \
  packages/grid-agent/tests/trajectory/test_service.py \
  packages/grid-agent/tests/trajectory/projections/test_business.py \
  packages/grid-agent/tests/trajectory/projections/test_context.py -q
npm --prefix packages/trajectory-workbench test -- --run \
  src/api/types.test.ts src/api/business.test.ts \
  src/views/BusinessView.test.tsx src/views/ContextView.test.tsx
```

Expected: assertions fail on fixed grid authority and non-namespaced response
shapes.

- [ ] **Step 4: Generalize read models without moving truth ownership**

Carry application/binding/domain/authority/schema metadata through service and
API models. Select domain rendering metadata by binding. Preserve raw verified
payloads for inspection; the workbench must not recalculate, validate, or
promote them to evidence.

- [ ] **Step 5: Run focused tests and commit**

```sh
uv run --project packages/grid-agent pytest packages/grid-agent/tests/trajectory -q
npm --prefix packages/trajectory-workbench test -- --run
git add packages/grid-agent/src/grid_agent/trajectory \
  packages/grid-agent/tests/trajectory packages/trajectory-workbench/src
git commit -m "feat: project binding-aware application runs"
```

---

### Task 9: Assemble the generic pandapower application and isolate v1.0.1 compatibility

**Files:**
- Create: `packages/grid-agent/src/grid_agent/application/{profile,registry}.py`
- Create: `packages/grid-agent/src/grid_agent/compat/{__init__,v1_0_1}.py`
- Create: `packages/grid-agent/tests/application/{test_profile,test_registry,test_generic_entrypoint}.py`
- Create: `packages/grid-agent/tests/compat/test_v1_0_1.py`
- Modify: `packages/grid-agent/src/grid_agent/application/{composition,__init__}.py`
- Modify: `packages/grid-agent/src/grid_agent/cli/app.py`
- Modify: `packages/grid-agent/tests/cli/test_app.py`
- Create: `packages/grid-agent/tests/cli/test_run_command.py`
- Modify: `Makefile`

**Interfaces:**
- Produces: `build_pandapower_application_profile()` and an explicit trusted
  application registry.
- Adds: `make analysis-generic APPLICATION=pandapower-static-analysis
  INSTRUCTIONS=...`.
- Retains: the existing `grid-agent` CLI through an explicit v1.0.1 adapter.

- [ ] **Step 1: Write a failing composition-root test**

Assert the application manifest uses domain-neutral context/result/artifact
schemas, has one explicit `grid` binding, uses the complete pandapower profile,
and defaults to the validating two-part JSON renderer.

- [ ] **Step 2: Write failing generic output tests**

Invoke the generic entry point with fake provider transport and assert stdout
contains exactly one JSON object shaped as:

```json
{
  "schema": "capability-agent-output/1.0",
  "core": {
    "application_id": "pandapower-static-analysis",
    "application_version": "1.0.1",
    "run_id": "run-1",
    "status": "completed",
    "answer_refs": ["artifact:sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"],
    "report_ref": "artifact:sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "diagnostic_refs": []
  },
  "domains": {
    "grid": {
      "domain_id": "pandapower-static-analysis",
      "domain_version": "1.0.1",
      "schema": "pandapower-static-analysis-output/1.0",
      "status": "completed",
      "payload": {
        "mode": "continuous-static-analysis",
        "instruction_count": 2,
        "completed_count": 2,
        "failed_count": 0,
        "report_artifact_ref": "artifact:sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
      }
    }
  }
}
```

Validate the complete object against both schemas. Diagnostics and progress
must be on stderr.

- [ ] **Step 3: Write failing compatibility isolation tests**

Run the explicit v1.0.1 entry point and assert stdout has exactly
`question_id` and `answer_output`. Assert the adapter can read supported legacy
artifacts and aliases but cannot change evidence admission, answer audit, or
the internal validated `ApplicationResult`.

- [ ] **Step 4: Run the focused tests and verify RED**

```sh
uv run --project packages/grid-agent pytest \
  packages/grid-agent/tests/application \
  packages/grid-agent/tests/compat \
  packages/grid-agent/tests/cli -q
```

Expected: the generic composition root and explicit compatibility adapter do
not exist.

- [ ] **Step 5: Implement explicit assembly and adapters**

Register `pandapower-static-analysis` in source code. The generic entry point
selects only registered applications, calls `AgentApplication` without a legacy
adapter, and renders the validated two-part result. Move legacy command names,
question-ID conventions, two-field stdout, historical workspace/artifact
readers, and supported `grid_*` core aliases into `compat.v1_0_1`.

- [ ] **Step 6: Add the supported Make target**

`analysis-generic` requires `APPLICATION` and `INSTRUCTIONS`, forwards optional
`PROVIDER` and `MODEL`, and never dispatches through the compatibility adapter.
Its stdout remains the single composite result object.

- [ ] **Step 7: Run CLI regressions and commit**

```sh
uv run --project packages/grid-agent pytest \
  packages/grid-agent/tests/application \
  packages/grid-agent/tests/compat \
  packages/grid-agent/tests/cli \
  packages/grid-agent/tests/contract -q
make doctor
git add packages/grid-agent Makefile
git commit -m "feat: assemble generic pandapower application"
```

---

### Task 10: Add deterministic application acceptance and package/documentation gates

**Files:**
- Create: `validation/application/pandapower-scripted-task.json`
- Create: `validation/application/pandapower-scripted-test.json`
- Create: `packages/grid-agent/tests/e2e/test_generic_pandapower_application.py`
- Modify: `validation/manifest.json`
- Modify: `validation/run.py`
- Modify: `Makefile`
- Modify: `tools/check_package_boundaries.py`
- Modify: `tools/tests/test_check_package_boundaries.py`
- Modify: `packages/capability-agent-kernel/tests/test_boundaries.py`
- Modify: `packages/pandapower-domain-pack/tests/test_boundaries.py`
- Modify: `README.md`
- Modify: `README.zh-CN.md`
- Modify: `docs/RUNBOOK.md`
- Modify: `docs/architecture/pandapower-capability-composition.md`
- Modify: `docs/status/CURRENT-STATE.md`

**Interfaces:**
- Adds: provider-free scripted acceptance for the complete application wiring.
- Strengthens: generic-path forbidden imports/symbols and package ownership.
- Documents: generic default output versus explicit v1.0.1 compatibility.

- [ ] **Step 1: Write the failing scripted acceptance test**

Use a deterministic scripted model transport that performs real semantic tool
calls through the prepared pandapower endpoint. For each scripted input, assert
current-run result/evidence lineage, context reuse, answer audit, report
creation, replay equality, and a validated `core` plus `domains.grid` result.
Do not bypass `gridctl`, inject expected numerical answers, or call pandapower
directly.

- [ ] **Step 2: Add the boundary failure cases**

Assert generic packages reject imports and literals for `grid_agent`,
`grid_simulator`, `pandapower_domain`, `pandapower`, `gridctl`, `grid_*`, power
flow, voltage, bus, branch, and N-1 semantics. Assert the pandapower Domain Pack
cannot import the concrete CLI or write another binding's state.

- [ ] **Step 3: Run the focused tests and verify RED**

```sh
uv run --project packages/grid-agent pytest \
  packages/grid-agent/tests/e2e/test_generic_pandapower_application.py -q
make check-package-boundaries
```

Expected: acceptance or the strengthened static boundary gate fails until the
new path is fully wired and product-specific literals are removed.

- [ ] **Step 4: Add deterministic validation cases and target**

Register both scripted cases under a new `application-instantiation` suite.
Teach the validation harness to invoke the generic application entry point and
validate both output contracts. Add `make validate-application` as a
provider-free gate. This suite proves wiring and safety but does not satisfy the
provider-backed business completion gate in Task 11.

- [ ] **Step 5: Update operator and architecture documentation**

Keep both READMEs aligned. Document:

- `ApplicationProfile -> AgentApplication -> DomainBinding -> Domain Pack`;
- framework-owned `core` and Domain Pack-owned `domains.<binding_id>`;
- `analysis-generic` and evidence inspection;
- explicit v1.0.1 compatibility and its exact two-field stdout;
- inventory's fixture-only status;
- C.1 as in progress until both real business task files pass Task 11.

- [ ] **Step 6: Run deterministic gates and commit**

```sh
make doctor
make test
make test-e2e
make validate-application
make check-package-boundaries
git diff --check
test -L CLAUDE.md
test "$(readlink CLAUDE.md)" = "AGENTS.md"
git add validation Makefile tools/check_package_boundaries.py \
  tools/tests/test_check_package_boundaries.py \
  packages/capability-agent-kernel/tests/test_boundaries.py \
  packages/pandapower-domain-pack/tests/test_boundaries.py \
  packages/grid-agent/tests/e2e/test_generic_pandapower_application.py \
  README.md README.zh-CN.md docs/RUNBOOK.md \
  docs/architecture/pandapower-capability-composition.md \
  docs/status/CURRENT-STATE.md
git commit -m "test: add application instantiation gates"
```

---

### Task 11: Reproduce both v1.0.1 business tasks on the new path and close C.1

**Files:**
- Modify after successful evidence review: `docs/status/CURRENT-STATE.md`
- Modify after successful evidence review: `docs/status/JOURNAL.md`
- Modify after successful evidence review: `docs/status/RESUME-NEXT-SESSION.md`
- Generated and ignored: `runs/<run_id>/core/**`
- Generated and ignored: `runs/<run_id>/domains/grid/**`

**Authorization gate:**
- This task requires explicit user authorization for provider credentials and
  possible billing at execution time.
- If authorization is absent, stop before provider I/O and report C.1 as
  implemented but not acceptance-complete.

- [ ] **Step 1: Record the authorized provider/model without exposing secrets**

Set `AUTHORIZED_PROVIDER` to the provider ID explicitly authorized by the user.
Set `AUTHORIZED_MODEL` only when the authorization names a model. Credentials
remain in environment variables or project-owned ignored authentication state;
never print, log, or pass them as command-line secret values.

- [ ] **Step 2: Run `task.md.txt` through the generic default path**

When both provider and model are authorized:

```sh
make analysis-generic \
  APPLICATION=pandapower-static-analysis \
  INSTRUCTIONS=validation/questions/task.md.txt \
  PROVIDER="$AUTHORIZED_PROVIDER" \
  MODEL="$AUTHORIZED_MODEL"
```

When the provider's configured default model is authorized, omit the `MODEL`
assignment. Save the emitted run ID from the `core` result for inspection.

- [ ] **Step 3: Inspect task evidence before running the second file**

Verify every instruction completed and inspect the run manifest, model
requests, tool calls, result/evidence lineage, context snapshots, answer audits,
report artifact, and final composite result. Confirm every numerical, ranking,
topology, contingency, and evidence claim traces to current-run `gridctl`
results.

- [ ] **Step 4: Run and inspect `test.md.txt` independently**

```sh
make analysis-generic \
  APPLICATION=pandapower-static-analysis \
  INSTRUCTIONS=validation/questions/test.md.txt \
  PROVIDER="$AUTHORIZED_PROVIDER" \
  MODEL="$AUTHORIZED_MODEL"
```

Use a fresh run ID. Apply the same inspection checklist as Step 3 and verify
context replay equals the materialized snapshot.

- [ ] **Step 5: Re-run one file through explicit v1.0.1 compatibility**

```sh
make analysis \
  INSTRUCTIONS=validation/questions/test.md.txt \
  PROVIDER="$AUTHORIZED_PROVIDER" \
  MODEL="$AUTHORIZED_MODEL"
```

Assert stdout is exactly one JSON object with `question_id` and
`answer_output`; inspect the referenced report and confirm the internal run
retains the richer validated result and identical simulator/evidence rules.

- [ ] **Step 6: Run all repository gates on main**

```sh
make doctor
make test
make test-e2e
make validate
make test-packages
git diff --check
test "$(git branch --show-current)" = "main"
test "$(git worktree list --porcelain | rg '^worktree ' | wc -l | tr -d ' ')" = "1"
```

Expected: every command passes, the repository is on `main`, and only the main
worktree remains.

- [ ] **Step 7: Record the completion claim only after all evidence passes**

Update project status to say exactly:

- C fixture: complete as conformance infrastructure;
- C.1: complete with one real pandapower application and two provider-backed
  business acceptance runs;
- C.2: not started; no real second domain selected;
- E: not started; multiple bindings remain feature-gated.

Record the two run IDs, provider/model identifiers, commands, gate results, and
commit hash without credentials. If either business run or any gate fails,
record the failing condition and leave C.1 incomplete.

- [ ] **Step 8: Commit the verified closure state**

```sh
git add docs/status/CURRENT-STATE.md docs/status/JOURNAL.md \
  docs/status/RESUME-NEXT-SESSION.md
git commit -m "test: close first domain application instantiation"
```

## Dependency order

Execute Tasks 0-11 in order. Tasks 1-5 define the public contracts and
lifecycle that Task 6 extracts into a complete runner. Task 7 supplies the
first real Domain Pack. Tasks 8-9 wire operator projections and application
entry points. Task 10 establishes deterministic regression coverage. Task 11
is the only provider-backed completion gate and must run last.

Do not expand inventory or remove the one-binding gate during C.1. C.2 may
select and instantiate a second useful business domain only after Task 11.
Workstream E may remove the one-binding gate only after separate multi-domain
sharing, authority, credential, collision, and end-to-end acceptance design.

## Completion rule

Tasks 0-10 can establish that the architecture is implemented and
deterministically testable. They cannot establish that Workstream C.1 has
reproduced the v1.0.1 business capability. C.1 is complete only when Task 11
has passed both `validation/questions/task.md.txt` and
`validation/questions/test.md.txt` through `analysis-generic`, the resulting
evidence has been audited, compatibility remains intact, every repository gate
passes, and the result is integrated directly on `main` with no temporary
worktree or feature branch.

## Plan coverage review

- [x] Every contract in the approved design has an owning task and exact file.
- [x] The plan enforces a Kernel free of pandapower/grid product vocabulary and imports.
- [x] Framework output and Domain Pack output receive independent validation tasks.
- [x] The generic renderer is required to preserve both output sections.
- [x] Only the explicit v1.0.1 adapter may emit `question_id`/`answer_output`.
- [x] Inventory remains a fixture and is not described as a second agent.
- [x] Both real pandapower business task files are mandatory C.1 gates.
- [x] Provider execution requires explicit authorization and secret-safe handling.
- [x] Full verification ends on `main` with one worktree and no half-finished branch.
