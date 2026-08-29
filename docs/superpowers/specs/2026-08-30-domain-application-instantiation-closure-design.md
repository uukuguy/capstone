# Domain Application Instantiation Closure Design

**Date:** 2026-08-30

**Status:** Approved section by section; written-spec review pending

**Scope:** Close the application-instantiation gap in the general domain-agent
framework, using pandapower static analysis as the first complete domain
application.

**Relationship to prior design:** This specification refines the target
architecture in
`2026-08-27-general-domain-agent-framework-upgrade-design.md`. It does not
replace the completed package and SPI work. Where the earlier design or the
Workstream C inventory specification implies that package-level conformance is
sufficient to prove a complete business agent, this specification is
authoritative.

## 1. Decision

The next controlled increment will not extend the inventory reference fixture
and will not begin dynamic multi-domain routing. It will first make the
application-instantiation boundary concrete and prove it with the existing
pandapower business domain.

The repository already has a useful low-level `DomainRuntimeProfile` seam for
capability contracts, execution, authority, and projection. It does not yet
have a complete application profile capable of assembling provider runtime,
continuous turns, domain state, answer evidence policy, presentation, and
domain acceptance through domain-neutral interfaces.

The approved correction is:

1. define a complete `ApplicationProfile` and `DomainBinding` contract;
2. make the default application path domain-neutral and composite-ready;
3. express the complete pandapower application through that path;
4. treat `grid-agent` 1.0.1 as a behavioral reference and optional
   compatibility adapter, not as the source of new framework defaults;
5. run the two existing pandapower business task files through the new default
   path before selecting a real second domain;
6. retain inventory as a capability/domain conformance fixture only.

## 2. Why the correction is necessary

Workstreams A and B extracted useful neutral interfaces and physical packages.
Workstream C proved that an independently installed inventory package can use
the public Kernel SPI, generic Pi transport, its own subprocess protocol,
current-run artifacts, authority, and projectors.

Those achievements do not prove that a business domain can instantiate a
complete agent application. The current continuous Analysis path still:

- constructs `build_pandapower_profile()` directly in the CLI;
- installs and places `gridctl` on `PATH` from application code;
- locates the grid-specific Pi extension wrapper;
- stores continuous state in pandapower models;
- catches pandapower-specific integrity exceptions in the runner;
- recognizes `grid_*` tools, `gridctl`, baseline network state, power flow,
  constraints, and N-1 in application projection;
- renders pandapower-specific context and reports from application modules;
- contains grid-specific answer-reference and trajectory policies;
- validates inventory only through provider-free scripted tool execution.

The missing layer is not another tool adapter. It is the complete contract that
turns one or more Domain Packs into an end-user agent application.

## 3. Architectural boundary

The target layering is:

```text
domain-specific or compatibility CLI
                  |
                  v
          ApplicationProfile
                  |
                  v
    domain-neutral Agent Application / Kernel
                  |
                  v
          DomainBinding x 1..N
                  |
                  v
     DomainRuntimeProfile / Domain Pack
                  |
                  v
       authoritative business resources
```

### 3.1 Domain-specific or compatibility CLI

An entry point owns command names, argument parsing, and any explicitly
selected legacy output adapter. It selects an Application Profile and delegates
all run and Analysis orchestration.

`grid-agent` remains a supported pandapower entry point. It is not the generic
framework host and its legacy naming does not become the framework default.

### 3.2 Application Profile

An Application Profile declares what application is being assembled:

- application identity and version;
- one or more explicit Domain Bindings;
- application-level policy;
- output contract;
- report shell;
- acceptance profile.

It selects business capabilities but does not interpret business results.

### 3.3 Agent Application / Kernel

The domain-neutral runtime owns:

- provider and Pi lifecycle;
- questions, turns, decisions, and answer lifecycle;
- workspace and immutable core artifacts;
- generic consumed, produced, result, and evidence edges;
- canonical request capture and native events;
- deterministic routing through a selected Domain Binding;
- controller-owned answer commit;
- context persistence and replay;
- generic report structure and failure recovery.

It must not import pandapower, recognize grid entities, interpret simulation
results, or assume that a domain uses a local executable.

### 3.4 Domain Binding

A Domain Binding is one installed Domain Pack bound into one application under
one application-local identity. It owns namespace, credential scope, and data
sharing policy for that instance.

The initial implementation uses exactly one binding. The data model supports a
tuple of bindings so Workstream E can later enable multiple bindings without
redesigning the application contract.

### 3.5 Domain Pack

A complete Domain Pack owns:

- business capability contracts;
- execution provisioning and transport adaptation;
- evidence authority and reference rules;
- domain state schema and projectors;
- answer evidence policy;
- model-facing policy and guides;
- domain context and report presentation;
- domain acceptance cases.

A package missing any of execution, authority, state, answer policy,
presentation, or acceptance is a capability/domain fixture, not a complete
business-agent domain.

### 3.6 Authoritative business resources

Business resources create facts and evidence. They do not participate in LLM
planning or application orchestration. Pandapower calculations remain behind
`gridctl` and `grid-capability/1.0`.

## 4. Application-instantiation contracts

The following shapes define responsibility. Exact Python module placement is
part of implementation planning, but the fields and ownership are fixed by
this specification.

### 4.1 `ApplicationManifest`

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
```

The default values are new domain-neutral schemas and names. No field defaults
to `grid`, `gridctl`, pandapower, or v1.0.1 artifact identities.

### 4.2 `ApplicationProfile`

```python
@dataclass(frozen=True, slots=True)
class ApplicationProfile:
    manifest: ApplicationManifest
    domains: tuple[DomainBinding, ...]
    output_contract: OutputContract
    application_policy: ApplicationPolicy
    report_shell: ReportShell
    acceptance_profile: AcceptanceProfile
```

The first implementation rejects zero bindings and more than one binding. The
cardinality restriction is a runtime feature gate, not a different type.

### 4.3 `DomainBinding`

```python
@dataclass(frozen=True, slots=True)
class DomainBinding:
    binding_id: str
    tool_namespace: str
    profile: DomainRuntimeProfile
    credential_scope: CredentialScope
    sharing_policy: DataSharingPolicy
```

The initial defaults are an isolated credential scope and denied cross-domain
sharing.

### 4.4 Complete `DomainRuntimeProfile`

The current profile is extended to require or provide:

| Contract | Responsibility |
| --- | --- |
| `DomainManifest` | Domain, protocol, version, tool, and authority identity |
| `CapabilityContractSource` | Published semantic capabilities |
| `DomainRuntimeProvisioner` | Prepare a safe execution endpoint for the current workspace |
| `CapabilityExecutor` | Execute one bounded capability |
| `ArtifactAuthority` | Admit current-run results and evidence |
| `DomainProjectorRegistry` | Select a projector for verified results |
| `DomainStateAdapter` | Validate state schema, merge deltas, and build model-visible state |
| `AnswerEvidencePolicy` | Decide which result/evidence references a claim requires |
| `DomainPolicyProvider` | Provide a deterministic domain policy fragment |
| `GuideProvider` | Provide an allowlisted, digest-bound guide index |
| `PresentationProvider` | Render domain labels, summaries, context, and report sections |
| `DomainAcceptanceProfile` | Declare offline, scripted, and provider-backed acceptance cases |

### 4.5 Runtime provisioning

Application code must not install or locate `gridctl` or any other domain
executable. Provisioning is owned by the Domain Pack:

```python
class DomainRuntimeProvisioner(Protocol):
    def prepare(
        self,
        *,
        binding: DomainBinding,
        workspace: Path,
        credentials: CredentialLease,
    ) -> PreparedDomainEndpoint: ...
```

`PreparedDomainEndpoint` supplies the executor and the controller-owned
transport binding needed by the model tool runtime. For a local process this
includes a verified executable basename, fixed argument vector, bounded search
path, timeout/output limits, and a scrubbed environment. For HTTP, gRPC, or
asynchronous resources it may instead supply a trusted adapter. Tool input can
never select or override endpoint, command, protocol, authority, or credentials.

### 4.6 Application context and domain state

The new default context is `application-context/1.0`:

```text
ApplicationContext
  core
    input and runtime identity
    questions and turns
    decisions and diagnostics
    consumed and produced references
    results and evidence edges
    answer lifecycle
  domains
    <binding_id>
      schema_id
      revision
      state
```

The Kernel reduces only core lifecycle state. A `DomainStateAdapter` validates
and merges its own namespaced state. It cannot change another binding or turn a
projection into authoritative evidence.

### 4.7 Application result, CLI envelope, and compatibility adapters

The new internal and persisted result schema is
`capability-agent-result/1.0`, for example:

```json
{
  "schema": "capability-agent-result/1.0",
  "application_id": "pandapower-static-analysis",
  "run_id": "run-...",
  "status": "completed",
  "output": {
    "type": "report",
    "path": "runs/run-.../report.md"
  }
}
```

The repository CLI contract remains a domain-neutral projection of that result
and writes exactly one object to stdout:

```json
{
  "question_id": "run-...",
  "answer_output": "runs/run-.../report.md"
}
```

No status, schema, diagnostic, event, or domain field is added to CLI stdout.
The richer application result stays in controller state and run artifacts.

Legacy behavior is selected explicitly at an entry point:

```python
AgentApplication(
    profile=build_pandapower_application_profile(),
    adapter=build_grid_v1_0_1_compatibility_adapter(),
)
```

The grid adapter may preserve legacy command names, question-ID conventions,
workspace layout, historical artifact readers, and core-tool aliases. It does
not own the two-field stdout rule, which is already the generic CLI default. It
cannot change simulator truth, evidence admission, or answer-audit decisions.
Without an explicit adapter, the generic defaults apply.

## 5. Registration, naming, and routing

### 5.1 Explicit trusted registration

The first implementation uses a controller-owned registry:

```python
registry.register(
    domain_id="pandapower-static-analysis",
    version="1.0.1",
    factory=build_pandapower_profile,
)
```

Application Profiles may reference only registered factories satisfying an
explicit version constraint. The first implementation does not scan arbitrary
Python entry points, infer plugins from package names, import user-supplied
modules, or download remote code.

Workstream E may add signed and allowlisted installed-package discovery without
changing the profile and binding types.

### 5.2 Separate identities

Each binding has three different identities:

```text
domain_id       package and protocol identity
binding_id      application-local instance identity
tool_namespace model-visible tool prefix
```

For the first domain these can be:

```text
domain_id       pandapower-static-analysis
binding_id      grid
tool_namespace  grid_
```

Kernel indexing uses a structured key:

```python
CapabilityKey(binding_id="grid", capability_id="analysis.powerflow.ac.run")
```

It never uses a domain-local capability ID as a global key.

### 5.3 Core and domain catalogs

The current behavior that adds a decision tool to each domain catalog is a
single-domain assumption. The target catalog is:

```text
Application Core Catalog
  agent_record_decision
  bounded core context tools

Domain Catalog: grid
  grid_context_open
  grid_analysis_powerflow_ac
  grid_guide_open
  ...
```

The new default core namespace is `agent_`. A compatibility adapter may expose
`grid_record_decision`; the Kernel does not default to it.

### 5.4 Composite catalog validation

Before provider I/O, composition verifies:

- unique binding IDs;
- unique tool namespaces and final tool names;
- no collision with reserved Kernel tools;
- capability contract and runtime publication agreement;
- authority identity and protocol agreement;
- unique guide and context tool names;
- compatible state and policy schema versions.

Any disagreement fails startup.

### 5.5 Deterministic routing

Each composite tool entry binds model-visible name to controller-owned routing
metadata:

```json
{
  "tool_name": "grid_analysis_powerflow_ac",
  "binding_id": "grid",
  "capability_id": "analysis.powerflow.ac.run",
  "authority_id": "gridctl",
  "protocol": "grid-capability",
  "protocol_version": "1.0"
}
```

The runtime resolves tool name to `CapabilityKey`, Domain Binding, executor,
authority, and projector. Model parameters never contain those routing fields.

## 6. Isolation and multi-domain conventions

### 6.1 State isolation

A projector can update only its own binding state. The Kernel validates binding
ID, state schema, prior revision, projector registration, and the ownership of
all result and evidence references before applying a delta.

### 6.2 Credential isolation

Provider credentials, domain credentials, and Kernel integrity keys are
separate scopes. A Domain Binding receives only its own credential lease. No
business credential enters model context, tool arguments, generic process
environment, trajectory, reports, or another binding.

Pandapower uses an empty domain credential scope in the first implementation.

### 6.3 Policy composition

Policy is composed deterministically:

```text
Kernel invariants
  + ApplicationPolicy
  + DomainPolicy ordered by binding_id
  + CrossDomainPolicy
```

The result is digest-bound to the run descriptor. Domain policy may tighten but
cannot relax Kernel invariants. Contradictory permissions, prohibited generic
tools, unmet approval requirements, or incompatible data-classification rules
fail before provider I/O.

### 6.4 Cross-domain sharing

The default is `DataSharingPolicy(mode="deny")`. Future sharing requires a
typed record naming source binding, target binding, verified reference,
purpose, classification, and policy decision. The source authority must admit
the reference before the Kernel re-registers a read-only shared reference for
the target.

Direct access to another binding's workspace, state objects, process, or
credentials is forbidden.

### 6.5 Lifecycle

Bindings prepare in sorted binding-ID order and clean up in reverse order. A
registration, provisioning, collision, policy, authority, state-schema, or
credential failure in any binding prevents provider startup.

The initial feature gate rejects more than one active binding. Workstream E
removes that gate only after collision, credential, policy, authority, and
sharing tests exist.

## 7. Pandapower as the first complete instance

The default first-domain profile is:

```python
def build_pandapower_application_profile() -> ApplicationProfile:
    return ApplicationProfile(
        manifest=ApplicationManifest(
            application_id="pandapower-static-analysis",
            version="1.0.1",
            display_name="Pandapower Static Analysis",
            context_schema="application-context/1.0",
            result_schema="capability-agent-result/1.0",
            artifact_schema="capability-agent-run/1.0",
            core_tool_namespace="agent_",
        ),
        domains=(
            DomainBinding(
                binding_id="grid",
                tool_namespace="grid_",
                profile=build_pandapower_profile(),
                credential_scope=isolated_empty_credentials(),
                sharing_policy=deny_sharing(),
            ),
        ),
        output_contract=default_result_contract(),
        application_policy=default_read_only_application_policy(),
        report_shell=default_continuous_analysis_report(),
        acceptance_profile=pandapower_acceptance_profile(),
    )
```

### 7.1 Ownership migration

| Current responsibility | Target owner |
| --- | --- |
| Generic workspace, provider, Pi, turn, and answer orchestration in `grid_agent.cli` | `capability_agent.application` |
| Pandapower selection | Pandapower application composition root |
| `_install_gridctl`, locator, and PATH injection | Pandapower runtime provisioner |
| Fixed grid Pi extension locator | Generic Pi transport locator; grid wrapper retained only for compatibility |
| `AnalysisRunner` lifecycle | Kernel application runner |
| Context ledger, hashes, and replay | Kernel application context store |
| Grid model, constraints, scenarios, calculations | Pandapower state adapter |
| Generic invocation and reference recording | Kernel invocation projector |
| `grid_*`, baseline, solver, power-flow, and N-1 interpretation | Pandapower projectors |
| Grid answer-reference rules | Pandapower answer policy |
| Generic bounded context view | Kernel context-view builder |
| Model, voltage, constraint, scenario, and calculation summaries | Pandapower context presenter |
| Generic question, answer, trajectory, evidence report skeleton | Kernel report shell |
| Grid report title, environment, and semantic sections | Pandapower presentation provider |
| Fixed `gridctl` checks in trajectory/workbench | Binding and authority metadata |
| Offline grid diagnostics | Optional pandapower application hook |

### 7.2 First-domain flow

```text
explicit pandapower ApplicationProfile
  -> validate the one grid DomainBinding
  -> pandapower provisioner prepares gridctl
  -> materialize domain contracts, guides, policy, and tool catalog
  -> generic Pi transport registers grid tools
  -> Kernel executes ordered questions and turns
  -> gridctl creates current-run results and evidence
  -> pandapower authority admits references
  -> Kernel records generic edges and events
  -> pandapower projectors update domains.grid.state
  -> pandapower presenter builds model-visible domain context
  -> Kernel commits the answer
  -> pandapower answer policy audits business references
  -> generic report shell and pandapower presenter produce the report
  -> default generic result or explicit legacy adapter emits output
```

No module on the generic path may import pandapower code or recognize grid
vocabulary.

## 8. Generic defaults and v1.0.1 compatibility

Version 1.0.1 is the business and safety reference. It is not the source of new
framework defaults.

### 8.1 New defaults

| Concern | Default |
| --- | --- |
| Core tools | `agent_*` |
| Domain tools | Binding-selected namespace |
| Context | `application-context/1.0` |
| Runtime descriptor | `capability-agent-runtime/1.0` |
| Internal/persisted result | `capability-agent-result/1.0` |
| CLI stdout | Exact `question_id`/`answer_output` AnswerEnvelope |
| Artifacts | `runs/<run_id>/core/` and `runs/<run_id>/domains/<binding_id>/` |
| Events | Application identity from ApplicationManifest |
| Model tool transport | `@capability-agent/pi-tools` |
| Reporting | Generic shell plus domain presentation |

### 8.2 Explicit compatibility support

The grid compatibility adapter supports, where required:

- `grid-agent run`, `analysis`, `report`, and current arguments;
- current question-ID conventions within the generic two-field stdout envelope;
- existing `grid_*` core-tool aliases;
- existing run artifact readers and layouts;
- current reports and workbench readers;
- `grid-capability/1.0`, grid tool schemas, reference identities, and simulator
  truth boundaries.

Compatibility tests do not substitute for tests of the new default path.

## 9. Error contract

The Kernel recognizes domain-neutral categories:

| Error | Meaning and handling |
| --- | --- |
| `ApplicationConfigurationError` | Incomplete or inconsistent profile; fail before provider I/O |
| `DomainRegistrationError` | Missing, incompatible, or conflicting domain registration |
| `DomainProvisioningError` | Safe endpoint or credential lease could not be prepared |
| `CapabilityRoutingError` | Tool, binding, capability, protocol, or authority mismatch |
| `CapabilityTransportError` | Timeout, malformed response, or correlation failure |
| `AuthorityIntegrityError` | Result, evidence, digest, lineage, or current-run admission failure |
| `DomainProjectionError` | Verified result could not be converted into reusable domain state |
| `PolicyConflictError` | Kernel, application, domain, or sharing policy conflict |
| `AnswerCommitError` | Required current-run result or evidence references are invalid or absent |
| `PresentationError` | Context view or report presentation failed |

Expected business failures return bounded tool errors with recovery guidance.
Routing, credential, transport-integrity, and authority failures fail the
current turn and admit no result. Projection failure preserves the verified
artifact but prevents it from entering reusable state. Presentation failure
cannot rewrite domain truth; the application emits diagnostics and a minimal
fallback presentation. Answer-audit failure preserves the model draft and
evidence but does not publish a committed answer.

## 10. Delivery program correction

### 10.1 Workstream C status

Workstream C remains a completed inventory capability/domain fixture proof. It
proved independent packaging, generic Pi transport, subprocess protocol,
current-run authority, and projection conformance.

It did not prove a second complete business agent, a complete Application
Profile, provider-backed end-user execution, first-domain migration to the new
default path, or multi-domain composition.

### 10.2 Workstream C.1 — Application Instantiation Closure

C.1 will:

1. implement the contracts in this specification;
2. establish the new domain-neutral default application path;
3. migrate the complete pandapower application behind that path;
4. isolate v1.0.1 behavior in an optional compatibility adapter;
5. pass both existing pandapower business task files through the new path.

C.1 excludes inventory expansion, a second production domain, arbitrary plugin
scanning, multiple active domains, cross-domain sharing, write operations,
approvals, and compensation.

### 10.3 Workstream C.2 — Real Second Domain

C.2 begins only after C.1. Before implementation, it must select a domain with
real business value and define its authoritative interface, user workflows,
read/write scope, evidence and permission model, and at least two acceptance
task sets. Inventory remains a fixture unless a later approved design replaces
it with a real governed resource and business case.

### 10.4 Workstream E — Multi-domain Composition

Workstream E removes the one-binding feature gate and implements trusted
discovery, composite catalogs, credential isolation, policy conflicts,
cross-domain references, data sharing, and multi-domain end-to-end acceptance.

## 11. Migration sequence

### Phase 1 — Boundaries and generic contracts

- freeze inventory as a fixture;
- add forbidden-import and forbidden-symbol gates for generic paths;
- implement Application Manifest/Profile, Domain Binding/Registry, generic
  context, provisioning, answer policy, presentation, acceptance, and common
  errors;
- retain a one-binding runtime gate.

### Phase 2 — Generic application engine

- move reusable workspace, provider/Pi, runner, turn, answer, context, replay,
  and report-shell behavior behind the new interfaces;
- produce only new generic defaults unless an explicit adapter is provided;
- extend the generic runtime descriptor and Pi transport for binding-aware
  routing while preserving the existing single-domain descriptor reader.

### Phase 3 — Pandapower first-domain migration

- add pandapower provisioning, state, projection, answer-policy, presentation,
  and acceptance providers;
- remove pandapower imports and identifiers from generic paths;
- assemble the pandapower Application Profile explicitly.

### Phase 4 — New-path business validation

Run both existing business task files through the new default entry point:

```sh
make analysis-generic \
  APPLICATION=pandapower-static-analysis \
  INSTRUCTIONS=validation/questions/task.md.txt

make analysis-generic \
  APPLICATION=pandapower-static-analysis \
  INSTRUCTIONS=validation/questions/test.md.txt
```

The command name is a required supported gate; implementation planning may
choose the underlying Python entry point but may not route this gate through
the v1.0.1 output/workspace adapter.

Provider-backed execution is a final C.1 gate. It requires explicit credential
and billing authorization at execution time.

### Phase 5 — Compatibility and repository regression

- run the same pandapower profile through the grid v1.0.1 compatibility entry;
- verify old output and readable artifacts;
- pass supported repository and packaging gates;
- integrate on `main` without leaving a worktree or feature branch.

## 12. Verification strategy

### 12.1 Static architecture gates

Tests fail if generic modules import or contain product-specific dependencies,
including `grid_agent`, `grid_simulator`, `pandapower_domain`, `pandapower`,
`gridctl`, fixed `grid_*` names, power-flow, voltage, bus, branch, or N-1
semantics.

Domain Pack tests fail if they import a concrete application CLI or mutate
another binding's state.

### 12.2 Contract and failure tests

Tests cover:

- invalid profiles and binding cardinality;
- unregistered or incompatible domains;
- capability, namespace, guide, and core-tool collisions;
- contract/runtime/protocol/authority disagreement;
- deterministic policy composition and conflict rejection;
- credential isolation and secret redaction;
- state-schema and revision enforcement;
- cross-binding state and reference rejection;
- transport correlation and timeout failures;
- current-run authority and answer-audit failures;
- projection and presentation fallback behavior;
- legacy adapter isolation from generic defaults.

Inventory may be used in these tests as a fixture. Such tests do not count as a
second business-agent acceptance result.

### 12.3 Pandapower business acceptance

Each provider-backed task-file run must record Application Profile and Domain
Pack versions/digests, provider/model, model requests, tool calls, turn status,
result/evidence lineage, context reuse, answer audit, report, and final generic
result.

Each run passes only if:

- every instruction completes;
- the model uses only published project and domain tools;
- numerical, ranking, topology, contingency, and evidence claims come from
  current-run `gridctl` results;
- authority and answer-reference audits pass;
- later turns can reuse only admitted state and references;
- context replay matches the materialized snapshot;
- reports and artifacts are traceable;
- stdout contains exactly one object with `question_id` and `answer_output`.

### 12.4 Compatibility and repository gates

After new-path acceptance, run:

```sh
make doctor
make test
make test-e2e
make validate
make test-packages
```

Compatibility tests additionally verify current grid question-ID conventions,
supported command aliases, existing tool schemas, readable historical run
formats, and unchanged simulator evidence rules. The exact two-field stdout
envelope is a generic application gate as well as a compatibility gate.

## 13. Completion claims

Workstream C.1 is complete only when:

1. the complete Application Profile and Domain Binding contracts are public and
   documented;
2. generic application modules contain no pandapower/grid strong dependency;
3. pandapower enters solely through its Domain Pack and explicit application
   composition root;
4. new generic defaults do not depend on v1.0.1 names or layouts;
5. both `task.md.txt` and `test.md.txt` pass through the new default path;
6. both runs have auditable result, evidence, context, answer, and report
   lineage;
7. the optional v1.0.1 compatibility entry remains supported;
8. repository, package, and boundary gates pass;
9. the result is integrated on `main` with no temporary worktree or feature
   branch left behind.

Completion terminology is fixed:

- before C.1: reusable Kernel/SPI plus conformance fixtures;
- after C.1: one real domain instantiated as a complete application;
- after C.2: another real domain independently instantiated;
- after E: multiple domains safely composed in one runtime.

No lower-level package, transport, or fixture gate may be reported as a higher
level of completion.

## 14. Rejected directions

### 14.1 Continue expanding inventory

The current fixture has little product value and does not exercise the complete
application path. More fixture capabilities would not close the first-domain
gap.

### 14.2 Make v1.0.1 the framework default

This would preserve grid-specific names and layouts in every future domain.
Version 1.0.1 remains a reference and explicit adapter only.

### 14.3 Copy `grid-agent` for every domain

Copying creates multiple vertical products with divergent fixes and hides
remaining application coupling. A domain-specific CLI may be thin, but it must
delegate to the shared application engine.

### 14.4 Implement dynamic plugin discovery now

Arbitrary discovery enlarges the trust surface before the complete
single-domain application contract is proven. Explicit trusted registration is
sufficient for C.1.

### 14.5 Claim multi-domain support from composite-ready types

A tuple-shaped profile does not prove safe composition. Multi-domain support is
claimed only after Workstream E removes the cardinality gate and passes
credential, policy, authority, collision, sharing, and end-to-end tests.
