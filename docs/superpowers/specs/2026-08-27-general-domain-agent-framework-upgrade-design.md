# General Domain Agent Framework Upgrade Design

**Date:** 2026-08-27

**Status:** Workstreams A and B implemented for the pandapower static-analysis application; Workstreams C-E remain unimplemented

**Current product:** `grid-agent` 1.0.1 assembled from extracted kernel, simulator, pandapower domain, application, and Pi tool packages

**Completed controlled increments:** domain-runtime seams plus physical package extraction without changing current grid behavior

## 1. Executive decision

The repository will evolve from a capability-first grid application into a
general domain-agent framework by extraction, not by rewriting the working grid
product and not by globally renaming every `grid_*` symbol.

The existing `grid-agent` remains the compatibility application and the first
reference domain. General framework boundaries will be introduced behind its
current CLI, protocol, evidence, and stdout contracts. After those boundaries
are proven, the pandapower implementation will move behind a domain-pack
interface and a second non-grid domain will be added without modifying the
framework kernel.

This design deliberately separates four levels of work:

1. **Kernel seams:** isolate domain metadata, execution transport, capability
   discovery, policy, projection, evidence authority, and presentation hooks.
2. **Pandapower domain pack:** place existing contracts, bindings, state
   projection, evidence rules, guides, and validation behind those seams.
3. **Cross-domain proof:** add a small non-grid reference domain without kernel
   changes.
4. **Enterprise actions:** add approval, tenant, authorization, idempotency,
   compensation, data classification, and asynchronous-operation semantics.

Workstreams A and B implement levels 1 and 2 for the existing pandapower static-analysis application. Levels 3 and 4 are still future work. The repository therefore has extracted package boundaries, but it is not yet a business-agnostic multi-domain framework.

## 2. Product assessment

### 2.1 What the repository already proves

The current product implements a complete controlled path from natural-language
questions to authoritative domain results:

```text
question
  -> grid-agent runtime and Pi/LLM
  -> runtime capability discovery
  -> contract/runtime intersection
  -> deterministic LLM tool catalog
  -> grid-capability/1.0 request
  -> gridctl validation and pandapower execution
  -> content-addressed result and evidence
  -> verified context and trajectory projection
  -> controller-owned answer commit
```

The following assets are already strong candidates for a general framework:

- provider and model runtime configuration;
- canonical pre-provider request capture;
- contract-derived LLM tool materialization;
- turn lifecycle and controller-owned answer submission;
- hash-chained native events with causation and reference lineage;
- immutable artifact registration, replay, and read-only workbench;
- bounded context injection;
- typed errors and recovery guidance;
- content-addressed evidence and current-run reference admission.

Focused verification on 2026-08-27 passed:

- 59 simulator contract, protocol, and analysis-registry tests;
- 45 agent catalog, context, projection, integrity, and projector tests;
- 8 focused Pi tool registration, protocol, correlation, environment, and
  decision tests.

These tests establish the reliability of the current grid product. They do not
establish cross-domain framework conformance because the repository contains no
second domain pack and no test that installs a domain without modifying the
kernel.

### 2.2 Current generalization level

| Target | Current state | Assessment |
| --- | --- | --- |
| Copy the repository and replace grid-specific code | Supported | Practical template reuse |
| Install the pandapower domain package on the shared kernel | Supported | Proven by clean wheel installation smoke tests |
| Add a second domain package without kernel changes | Not implemented | Workstream C |
| Load multiple domains in one runtime | Not implemented | Workstream E |
| Execute enterprise write operations safely | Not implemented | Workstream D |

The current system is therefore an extracted pandapower static-analysis application on a reusable kernel, not yet a plugin-instantiated general framework.

## 3. Existing architecture and concrete coupling

### 3.1 Capability contracts and tool generation

`ToolCatalog.from_environment` already computes the intersection of versioned
documents and runtime-published capabilities. It validates publication and
context-effect agreement before materializing a deterministic catalog.

The Pi extension already loops over that catalog and registers tools without
question-specific code. This behavior is general in structure.

The remaining coupling is:

- capability documents are loaded from the fixed
  `packages/grid-simulator/src/grid_simulator/capabilities/definitions` path;
- model-visible tool names must match `grid_*`;
- the Pi extension constructs `grid-capability/1.0` requests;
- every generated tool invokes the `gridctl` executable;
- `CapabilityContract.package` is descriptive only and does not participate in
  runtime discovery, loading, dispatch, or isolation.

### 3.2 Execution kernel

`grid-simulator.operations` owns a static `EXECUTABLE_CAPABILITIES` set and an
explicit capability-to-function dispatch chain. Default services construct a
`Pandapower340Engine`, and environment discovery publishes fixed simulator and
pandapower identities.

This is correct product code but it belongs to the future pandapower domain
pack. A general kernel must depend on a `CapabilityExecutor`, not on
`Pandapower340Engine` or `gridctl`.

### 3.3 Continuous domain context

The durable lifecycle kernel is broadly reusable, but `DomainState` currently
contains grid-oriented model, operating state, constraints, scenarios,
calculations, and artifacts. Projectors are selected from a fixed allowlist and
implemented with branches for model contexts, power flow, constraints, generic
analysis, and N-1 contingency.

The future kernel must retain generic lifecycle and reference state while moving
domain-specific state into namespaced, schema-validated domain projections.

### 3.4 Evidence and authority

The evidence model has the right principle: a claim is admitted only when an
authoritative producer created verifiable current-run artifacts.

The implementation is grid-specific because it fixes:

- reference kinds and prefixes;
- result and evidence directory layouts;
- allowed network-fact capabilities;
- `gridctl` as the authoritative producer;
- context/revision relationships appropriate to immutable grid models.

The general framework must make artifact kinds, authority, reference parsing,
link validation, and freshness/version rules part of a domain evidence adapter.

### 3.5 Policy and enterprise actions

The current capability risk model contains catalog, read-only model,
read-only analysis, and model revision. That is sufficient for a deterministic
analysis product but insufficient for external business systems with real side
effects.

The future enterprise layer must distinguish at least:

- query versus command;
- reversible versus irreversible effects;
- safe versus unsafe retries;
- idempotency requirements;
- approval requirements;
- actor, tenant, and authorization scope;
- data classification and redaction policy;
- synchronous versus asynchronous completion;
- compensating action support;
- observation time, external version, and staleness.

These fields are not added during the first controlled increment. The first
increment creates extension points that can carry them later without changing
the current grid contracts.

## 4. Goals and non-goals

### 4.1 Program goals

The completed upgrade program must allow a new domain agent application to be
created from:

- a domain manifest;
- capability contracts;
- an execution adapter;
- state projectors;
- evidence/authority rules;
- domain policy and guides;
- report presentation hooks;
- conformance and domain validation cases.

Adding that domain must not require edits to the Agent Kernel, generic Pi tool
materializer, native event spine, answer commit, replay service, or workbench
core.

### 4.2 Completed Workstream A/B goals

The completed Workstream A/B increments:

1. define neutral domain-runtime interfaces in `capability-agent-kernel`;
2. express the current pandapower runtime through `pandapower-domain-pack`;
3. route existing CLI composition through those interfaces from `grid-agent`;
4. preserve every current external contract;
5. keep the provider-free conformance fixture proving discovery and tool materialization are not tied to pandapower document paths;
6. split Pi transport into generic `@capability-agent/pi-tools` and grid-compatible `@grid-static-analysis/pi-grid-tools`;
7. prove install-mode compatibility by building four Python wheels and two npm tarballs outside the repository with `make test-packages`.

### 4.3 Remaining non-goals

The completed Workstream A/B increments still do not:

- rename `grid-agent`, `gridctl`, `grid-capability/1.0`, existing tools, schemas,
  environment variables, run artifacts, or CLI commands;
- support multiple simultaneously active domain packs;
- add a second production business domain;
- add business write tools or approval workflows;
- change the stdout answer envelope;
- change current result/evidence identities or paths;
- alter the model-visible system policy or guides;
- change simulator truth, result computation, or evidence admission behavior.

## 5. Target architecture

```text
Application Profile
  - product identity
  - selected Domain Pack
  - system policy and guide selection
  - output contract
          |
          v
Agent Kernel
  - provider/runtime
  - turn lifecycle
  - controller-owned answer commit
  - native event spine
  - artifact CAS and replay
  - bounded core context
          |
          v
Capability SDK / Domain SPI
  - DomainManifest
  - CapabilityContractSource
  - CapabilityExecutor
  - DomainProjectorRegistry
  - ArtifactAuthority
  - DomainPolicy
  - GuideProvider
  - PresentationProvider
          |
          v
Domain Pack
  - pandapower initially
  - non-grid reference domain later
          |
          v
Authoritative Business Resources
```

### 5.1 Agent Kernel ownership

The kernel owns only domain-neutral behavior:

- model/provider invocation;
- questions, turns, steps, and answer lifecycle;
- capability invocation correlation;
- generic consumed/produced/evidence edges;
- native event recording and replay;
- immutable artifact registration;
- domain extension loading and compatibility validation;
- generic policy-decision and approval events;
- final answer envelope and controller commit.

The kernel must not import pandapower, recognize network entity names, interpret
power-flow results, or assume that the authoritative system is a local
subprocess.

### 5.2 Domain Pack ownership

A domain pack owns:

- business capability contracts;
- capability handlers or remote-resource mappings;
- domain-specific state schemas and projectors;
- evidence authority and reference rules;
- business policy metadata;
- semantic titles and report presentation;
- model-facing guides;
- validation matrices and domain acceptance suites.

The pandapower domain pack additionally owns registered networks, immutable
network revisions, result datasets, constraint interpretation, topology,
analysis bindings, and simulator evidence.

## 6. Domain-runtime interfaces

Workstream B moved the proved seams into separately versioned distributions. The module layout is fixed as follows:

```text
packages/capability-agent-kernel/src/capability_agent/domain/
  __init__.py       public domain-runtime interface exports
  manifest.py       DomainManifest and manifest validation
  contracts.py      CapabilityContractSource protocol and filesystem source
  execution.py      CapabilityExecutor protocol
  projection.py     DomainProjector and DomainProjectorRegistry protocols
  authority.py      ArtifactAuthority protocol
  profile.py        DomainRuntimeProfile composition root

packages/capability-agent-kernel/src/capability_agent/application/
  composition.py    shared profile-driven runtime materialization

packages/capability-agent-kernel/src/capability_agent/tools/
  catalog.py        domain-neutral tool catalog and guide index materialization

packages/capability-agent-kernel/src/capability_agent/trajectory/
  *.py              native event spine, artifacts, recorder, replay, and readers

packages/pandapower-domain-pack/src/pandapower_domain/
  profile.py        pandapower static-analysis profile and adapters
  resources/        system policy, guides, and capability contracts

packages/grid-agent/src/grid_agent/
  cli/              compatibility CLI and answer envelope
  runtime/          provider, Pi, auth, process, and workspace setup
  analysis/         continuous analysis orchestration and reporting
  trajectory/api/   read-only workbench service

packages/pi-capability-tools/src/
  domain-tools.mjs          generic descriptor-driven Pi capability transport
  model-request-capture.mjs provider-independent request capture

packages/pi-grid-tools/src/
  domain-tools.mjs          grid-compatible Pi extension wrapper
  model-request-capture.mjs grid-compatible request-capture wrapper
```

The `capability_agent` namespace contains neutral interfaces and runtime primitives. The `pandapower_domain` namespace contains product integration and may import grid simulator adapters. Compatibility modules under `grid_agent.domain`, `grid_agent.application.composition`, `grid_agent.trajectory.*`, `grid_agent.tools.*`, and `grid_agent.domains.pandapower` re-export or route to the extracted packages where needed for existing callers.

Neutral kernel modules must not import `grid_agent`, `grid_simulator`, `pandapower_domain`, or `pandapower`. The pandapower domain pack must not depend on `grid-agent`; it owns domain resources and depends only on the kernel plus `grid-simulator`.

### 6.1 DomainManifest

```python
@dataclass(frozen=True, slots=True)
class DomainManifest:
    domain_id: str
    version: str
    display_name: str
    protocol: str
    protocol_version: str
    executable_name: str
    tool_name_prefix: str
    authority_id: str
    capability_contract_root: Path
    system_policy_path: Path
    guide_root: Path
```

For the built-in grid application, values remain compatible with:

- `domain_id="pandapower-static-analysis"`;
- `protocol="grid-capability"`;
- `protocol_version="1.0"`;
- `executable_name="gridctl"`;
- `tool_name_prefix="grid_"`;
- `authority_id="gridctl"`.

### 6.2 CapabilityContractSource

```python
class CapabilityContractSource(Protocol):
    def load(self) -> tuple[dict[str, object], ...]: ...
```

The source owns document discovery. `ToolCatalog` receives documents and must no
longer know the pandapower repository path.

### 6.3 CapabilityExecutor

```python
class CapabilityExecutor(Protocol):
    def invoke(
        self,
        capability: str,
        arguments: dict[str, object],
    ) -> dict[str, object]: ...
```

The existing `GridctlClient` satisfies this behavior through a compatibility
adapter. Later implementations may use another local executable, HTTP, gRPC, or
an asynchronous job adapter without changing orchestration code.

### 6.4 DomainProjectorRegistry

```python
class DomainProjector(Protocol):
    projector_id: str

    def project(self, invocation: VerifiedInvocation) -> DomainStateDelta: ...


class DomainProjectorRegistry(Protocol):
    def require(self, projector_id: str) -> DomainProjector: ...
```

The kernel records and validates the projection event. The domain projector
interprets business output. In the first increment the registry delegates to
the existing projector functions; no durable state schema changes.

### 6.5 ArtifactAuthority

```python
class ArtifactAuthority(Protocol):
    authority_id: str

    def admit(
        self,
        capability: str,
        result: Mapping[str, object],
        evidence_refs: tuple[str, ...],
    ) -> VerifiedReferenceSet: ...
```

The first adapter wraps `ContentReferenceVerifier`. Later domains may validate
signed API receipts, record versions, database snapshots, or service-owned
evidence.

## 7. First-increment data flow

The externally observable flow remains unchanged:

1. CLI selects the built-in pandapower application profile.
2. The profile supplies `DomainManifest`, contract source, executor, guide root,
   policy path, projector registry, and artifact authority.
3. The executor performs `environment.describe` through the existing
   `grid-capability/1.0` wire protocol.
4. `ToolCatalog` intersects runtime capabilities with documents from the
   injected contract source.
5. Pi receives the same materialized tools and invokes the same `gridctl` path.
6. Existing integrity and domain projection logic runs through adapters.
7. Existing answers, events, reports, artifacts, references, and stdout remain
   byte-compatible where they are currently deterministic.

No fallback may silently instantiate the pandapower profile when an explicitly
selected profile is invalid. Configuration or compatibility errors fail before
provider I/O with typed diagnostics on stderr and the existing failure envelope
on stdout.

## 8. Compatibility constraints

The following are hard gates for every first-increment change:

- `grid-agent run`, `analysis`, `report`, `doctor`, authentication, and
  trajectory commands retain their names and arguments;
- stdout remains exactly one JSON object with `question_id` and
  `answer_output`;
- progress and diagnostics remain on stderr;
- all grid facts still cross `gridctl` through `grid-capability/1.0`;
- all model-visible tools retain existing names and schemas;
- current-run evidence admission remains fail-closed;
- observation and projection remain unable to replace simulator truth;
- existing `runs/` layouts and schema versions remain readable;
- provider credentials remain outside tool arguments, logs, artifacts, and
  simulator environments;
- no generic shell, file, Python, or raw business-object capability is exposed
  to the model.

## 9. Error handling

The kernel/domain boundary distinguishes:

1. **profile errors:** invalid manifest, missing adapter, incompatible protocol;
2. **catalog errors:** missing contract, duplicate capability/tool name,
   contract/runtime disagreement;
3. **transport errors:** process start, timeout, malformed or uncorrelated
   response;
4. **domain errors:** typed resolve, validate, execute, and persist failures;
5. **integrity errors:** untrusted result, evidence, authority, or lineage;
6. **projection errors:** domain state could not be derived from an otherwise
   valid tool result;
7. **provider errors:** LLM transport or adapter failures.

Existing product behavior remains authoritative: projection and reporting
diagnostics do not rewrite valid domain truth, while result/evidence integrity
failures prevent untrusted cross-turn reuse.

## 10. Testing strategy

### 10.1 Existing regression gates

The first increment runs the smallest focused test first, followed by:

```sh
make doctor
make test
make test-e2e
make validate
make test-packages
```

Provider-backed validation remains optional and must not run without explicit
credential and billing authorization.

### 10.2 New kernel conformance tests

Tests must prove:

- an injected contract source is used instead of a repository-relative
  pandapower path;
- an injected executor receives capability and arguments;
- runtime and contract capability intersection remains deterministic;
- manifest protocol and tool-prefix incompatibilities fail before provider I/O;
- the built-in pandapower profile materializes the same tool names and schemas;
- existing `GridctlClient` correlation and stdout protocol behavior is
  unchanged;
- existing projector and evidence adapters preserve current state and reference
  admission;
- a provider-free synthetic domain fixture can discover and materialize a
  catalog without importing pandapower modules;
- the synthetic fixture is a conformance test only and does not become a
  production second domain.

### 10.3 Program-level generality test

Framework generality is not considered complete until a later non-grid domain
passes this invariant:

> Adding the domain changes only its domain package, application profile,
> guides, configuration, and tests. It does not modify Agent Kernel, generic Pi
> tool materialization, event schemas, answer commit, replay, or Workbench core.

## 11. Controlled delivery program

### Workstream A — Kernel seams

Deliver neutral interfaces and pandapower adapters behind the existing CLI.
Route CLI composition through them with zero product behavior change.

**Status:** implemented. The seams now live in `capability-agent-kernel`, with compatibility exports preserving existing callers.

**Exit gate:** all current gates pass, the synthetic conformance fixture avoids pandapower imports, and no current public contract changes.

### Workstream B — Physical package extraction

After Workstream A is stable, move reusable modules into an independently
versioned Agent Kernel/Capability SDK distribution and move grid ownership into
a pandapower domain package.

**Status:** implemented for the pandapower static-analysis application. `grid-agent` is assembled from `capability-agent-kernel`, `grid-simulator`, `pandapower-domain-pack`, `@capability-agent/pi-tools`, and `@grid-static-analysis/pi-grid-tools`.

**Exit gate:** `grid-agent` is assembled from the extracted kernel and domain package while producing compatible tools, runs, and answers; `make test-packages` proves clean install-mode packaging outside the source tree.

### Workstream C — Non-grid reference domain

Implement a bounded read-only inventory or ticket domain using only the public
Domain Pack SPI.

**Status:** not implemented.

**Exit gate:** no kernel modifications, conformance tests pass, and domain facts
are admitted from its own authority adapter.

### Workstream D — Enterprise action governance

Extend contracts and runtime policy for side effects, approvals, actor/tenant
scope, idempotency, compensation, asynchronous completion, and data
classification.

**Status:** not implemented.

**Exit gate:** a write-capable reference domain proves safe retry, approval,
audit, authorization, and compensation behavior.

### Workstream E — Multi-domain composition

Add namespaced capability resolution, cross-domain policy, credential isolation,
and explicit data-sharing rules only after single-domain packs are stable.

**Status:** not implemented.

**Exit gate:** capability collisions, tenant isolation, evidence authority, and
cross-domain reference flow have deterministic tests.

## 12. Implemented Workstream A/B boundary

Workstream A introduced the seams behind the existing `grid-agent` distribution. Workstream B then moved the proved seams and resources into separately installable distributions. The implemented boundary is:

1. `capability-agent-kernel` owns neutral domain-runtime contracts, composition, tools, guides, and trajectory primitives.
2. `pandapower-domain-pack` owns the pandapower static-analysis Profile, resources, policy, guides, capability contracts, and compatibility adapters.
3. `grid-simulator` continues to own `gridctl`, registered network access, deterministic pandapower calculations, result datasets, and simulator evidence.
4. `grid-agent` owns the compatibility CLI, Pi/runtime setup, authentication, analysis runner, reporting, workbench service, and answer envelope.
5. `@capability-agent/pi-tools` owns generic descriptor-driven Pi capability transport and request capture.
6. `@grid-static-analysis/pi-grid-tools` owns the grid-compatible Pi extension entrypoint and keeps existing tool names stable.

The implemented package relocation does not rename `grid-agent`, `gridctl`, `grid_*` tools, `grid-capability/1.0`, environment variables, run artifacts, or the stdout answer envelope. Second-domain production code, enterprise write semantics, and multi-domain composition remain deferred to Workstreams C-E.

## 13. Remaining Program Success Criteria

The overall framework program is complete only when all statements below are true:

1. A non-grid reference domain can be added without modifying Agent Kernel, generic Pi tool materialization, event schemas, answer commit, replay, or Workbench core.
2. Domain facts are admitted through that domain's own authority adapter and evidence rules.
3. Enterprise write operations have approval, actor/tenant scope, authorization, idempotency, compensation, asynchronous completion, and data classification semantics.
4. Multiple domains can be composed with deterministic namespace, credential, policy, evidence, and cross-domain sharing rules.
5. Existing grid CLI, protocol, tool names, schemas, artifacts, evidence, and answer envelope remain compatible throughout those later workstreams.

## 14. Rejected approaches

### 14.1 Global rename first

Renaming every `grid_*`, protocol, schema, path, and package before introducing
interfaces creates large diffs without proving a reusable boundary. It also
risks breaking validated artifacts and external scripts. The design rejects this
approach.

### 14.2 Copy-and-specialize as the framework model

Repository cloning can create another vertical product quickly, but fixes and
governance improvements will diverge across copies. This remains a prototyping
option, not the target framework architecture.

### 14.3 Big-bang domain-pack extraction

Moving simulator, agent, schemas, guides, tests, and reports into new packages
in one change makes compatibility failures difficult to isolate. The design
requires seam-first extraction followed by physical movement.

### 14.4 Multi-domain runtime before single-domain SPI proof

Namespacing, credential isolation, cross-domain policy, and authority conflicts
are premature until one non-grid package can use the same kernel without core
edits. Multi-domain composition is intentionally last.

## 15. Final architectural position

The repository should preserve its strongest invariant:

> The model plans and composes bounded semantic capabilities; authoritative
> business systems create facts; the controller verifies lineage and commits the
> reader-facing answer.

The upgrade changes the nouns around that invariant, not the invariant itself.
`gridctl` becomes the first `ArtifactAuthority` and `CapabilityExecutor`;
pandapower becomes the first Domain Pack; `grid-agent` becomes the first
application profile built on a reusable Agent Kernel.
