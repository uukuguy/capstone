# Capstone Agent Framework

Capstone assembles evidence-backed agent applications over authoritative
business-domain systems. It is the composition boundary between a reader-facing
application, a domain's semantic capabilities, and the registered system that
can actually calculate or retrieve the domain facts.

## Purpose and non-goals

The framework lets a model compose a bounded catalog of semantic capabilities
without making the model, the Kernel, or an application the source of truth.
An authority produces source-backed or deterministic results and admits the
evidence that supports them; the application then presents only claims that its
current run can support.

Capstone is not an LLM shell, a generic REST client, a route around a domain's
access controls, or a generic replacement for an authoritative system. It does
not expose shell access, arbitrary subprocesses, arbitrary code execution,
generic filesystem access, raw business objects, credentials, arbitrary network
endpoints, or undeclared capability aliases to the model. The framework also
does not make a domain-specific output envelope a Kernel requirement.

## Four layers and dependency direction

The four layers have distinct ownership:

```text
Application -> Domain Pack -> Kernel -> registered Authority
```

Dependencies only flow rightward. Result and evidence references return through
explicit contracts; they are not reverse imports, raw-object escape hatches, or
an invitation for an outer layer to recreate authority facts.

| Layer | Owns | Must not own |
| --- | --- | --- |
| Application | Application selection, public CLI or UI, provider setup, reader-facing rendering, and compatibility projection | Domain semantics, raw authority objects, credentials in model-visible state, or a mandatory Kernel schema for its public interface |
| Domain Pack | Domain contracts, policy, guides, provisioning, executor, projectors, domain state, output contract, and current-run authority adapter | Kernel internals, another domain's state, or the authority's raw implementation |
| Kernel | Neutral composition, tool and guide materialization, bounded context, turns, trajectories, artifacts, replay, audits, and framework-owned `core` lifecycle output | Domain capability semantics, pandapower objects, domain credential logic, or a product-specific answer schema |
| Registered Authority | Registered domain access, deterministic calculations or source-backed retrieval, revisions, result datasets, and evidence | Model planning, application presentation, or unbounded caller-selected execution |

An application declares an `ApplicationProfile`; `AgentApplication` owns the
run lifecycle; each `DomainBinding` injects a selected Domain Pack's public
contracts. A binding names its domain payload and tool namespace, keeps
credentials scoped, and defaults to no cross-domain data sharing. Domain Packs
communicate with an authority through their declared executor/protocol instead
of importing its implementation into the Kernel.

### Imports, calls, and evidence are different relationships

The layer ordering above constrains ownership and dependencies; it does not
require an import through every adjacent layer. The implemented source imports
are:

```text
Application -> Kernel public application API
Application -> selected Domain Pack public factory
Domain Pack -> Kernel public SPI
Domain Pack -> explicitly allowlisted Authority protocol/resource API
```

The Kernel has no import of a concrete registered authority. In the pandapower
pack, the sole simulator import permitted by the static boundary gate is
`from grid_simulator.capabilities import contract_root` (an alias is allowed).
This public installed-resource function locates the directory containing the
authority-owned capability JSON; it does not admit registry classes, simulator implementation modules,
raw networks, or arbitrary simulator calls. The pack retains an exact simulator
package dependency, declared in its `pyproject.toml`, so resource availability
is checked in clean wheel installation. The schema is not copied into a new
independently maintained contracts package. The AST check enforces declared
source imports; it is not a sandbox for malicious dynamic Python code.

Runtime calls use injected interfaces, not reverse implementation imports:

```text
Application -> Kernel lifecycle -> injected Domain executor -> Authority
```

Evidence returns through validated contracts, in the opposite data direction:

```text
Authority -> Domain admission/projector -> Kernel typed state/commits -> Application
```

Returning a reference does not expose an authority object or let the Kernel
recompute a domain fact. The Domain Pack still owns semantic admission, and
the application still owns its public compatibility projection.

## Runtime and tool protocol

At startup, the selected Domain Pack provisions a trusted endpoint for the
current workspace, materializes its published contracts, policy and guide index,
builds an allowlisted tool catalog, and creates an authority scoped to the
current run. The generic model transport turns an allowed tool invocation into
the Domain Pack's bounded protocol request; the executor sends it only to that
prepared endpoint. Tool input cannot choose a command, endpoint, protocol,
authority, or credential.

The model receives the current question, bounded framework context, the domain
policy and guides, and exact schemas for the registered semantic tools. It may
decide which of those tools to call and return reader-facing prose. It does not
validate itself: the controller validates typed calls, the authority produces
facts, and projectors accept only authority-admitted results into domain state.
The controller then binds the turn's consumed and produced result/evidence
references before committing the answer.

This separation makes tool exposure a two-party publication decision. A
capability must be declared by the Domain Pack and executable by its registered
authority. Documentation alone never registers a model tool, and an
implementation that is not published by the selected profile is not exposed.

## Composite output protocol

The generic application result is composed from independently validated Kernel
and Domain Pack contracts. Its generic shape is exactly:

```json
{"schema":"capability-agent-output/1.0","core":{},"domains":{"<binding_id>":{}}}
```

`core` is Kernel-owned and records the framework run lifecycle, references,
audits, and diagnostic metadata. Each `domains.<binding_id>` object is built
and validated by that binding's Domain Pack; it contains the domain-specific
status and business payload. A domain may add only its own namespaced payload;
it cannot redefine `core` or make its payload appear to be a framework result.

An application may render or project this composite result into a versioned
public interface. That is a vertical compatibility adapter owned by the
application, not by the Kernel. In particular, the grid compatibility adapter
owns the historical two-field `question_id` / `answer_output` projection. The
Kernel neither owns nor requires that grid envelope for another application.

## Current-run evidence protocol

Offline informational answers create no simulator or authority evidence.
Simulator- or authority-backed answers persist result and evidence artifacts
under the current run, conventionally `runs/<run_id>/`, and only references
admitted for that run may support final factual claims. A result reference
identifies a returned authority result; evidence references identify the
supporting current-run artifacts. The answer commit, report, and replay record
their lineage rather than trusting prose alone.

The current-run authority verifies the applicable result/evidence relationship
and rejects references outside the run or references it cannot admit. A
projected state, a cached display, a fixture, or an evidence-inspection tool is
not a substitute for the primary result contract. Replay and reporting can
diagnose a run, but do not create facts or make an otherwise invalid evidence
chain valid.

## Integrating a new application

An application integration is an explicit assembly, not dynamic discovery:

1. Define the authoritative system boundary and a reusable, versioned semantic
   capability protocol. Decide which facts, revisions, result references, and
   evidence the authority can return.
2. Implement a Domain Pack using the public Kernel SPI: published contracts,
   policy, guides, trusted endpoint provisioner, executor, current-run
   authority adapter, projectors, state adapter, output contract, and
   acceptance profile.
3. Define an `ApplicationProfile` and `DomainBinding` that select the pack,
   namespace its tools and output, scope credentials, and declare its public
   output renderer or compatibility adapter.
4. Materialize the runtime from that profile. Verify that only published,
   executable semantic tools and digest-bound guides reach the model.
5. Prove provider-free acceptance with real authority calls, current-run
   evidence lineage, answer audits, report creation, and replay. Run separate
   authorized authority/provider checks where credentials and billing permit.

The application must keep provider credentials outside arguments and artifacts,
keep diagnostics on its diagnostic channel, and preserve its stated public
output contract. It must not alter the Kernel merely to introduce a domain
term, raw object, or legacy answer shape.

## Verified grid application

`grid-static-analysis` is the first formal Capstone application. Its
`pandapower-domain-pack` supplies grid contracts, policy, guides, a `gridctl`
executor, projectors, and the current-run authority adapter. `grid-simulator`
owns the registered networks, pandapower calculations, result datasets, model
revisions, and evidence. Numerical and network-specific claims cross the
`gridctl` `grid-capability/1.0` boundary.

The `analysis-generic` path emits the composite result with Kernel-owned `core`
and pandapower-owned `domains.grid`. Provider-free application acceptance has
executed real semantic `gridctl` calls and checked current-run lineage, context
reuse, answer audit, report creation, replay, and the composite output.
Authorized provider runs have exercised the canonical business task suites
through that generic path. These results verify the first application's
assembly and compatibility boundary, not a claim that every prospective domain
has been accepted.

The stable `grid-agent` compatibility commands remain a vertical adapter. They
write exactly one JSON object to stdout with `question_id` and `answer_output`;
progress, diagnostics, tool events, and warnings belong on stderr. This is a
grid application contract, not the generic Capstone output protocol.

## Conformance proof and deferred scope

The read-only `inventory-reference-service` and `inventory-domain-pack` prove
that an independently installable domain can use the public Kernel SPI and
unchanged generic Pi transport without modifying protected framework paths.
Inventory is conformance infrastructure, not a production application and not
a runtime-selectable `grid-agent` mode.

Capstone does not yet provide dynamic plugin discovery, runtime domain
selection, multi-domain routing, cross-domain conflict resolution, or a chosen
second production domain. Governed writes, approval flows, tenant/actor scope,
idempotency, compensation, and write-capability governance are likewise
deferred. The C.2 GitHub Repository Intelligence record is a working theory,
not an implemented or selected domain.

## Domain design rules

1. Define reusable semantic capabilities and an explicit, versioned authority
   protocol before exposing model tools.
2. Keep authority internals, credentials, and raw domain objects out of
   model-visible tools and Kernel contracts.
3. Make a Domain Pack own contracts, policy, guides, executor, projections,
   current-run admission, state validation, and its namespaced output payload.
4. Let the Kernel own neutral lifecycle, trajectory, artifact, replay, audit,
   and composite `core` concerns; do not couple it to a domain vocabulary.
5. Bind reader-facing factual claims only to current-run, authority-admitted
   result and evidence references.
6. Treat an application's public compatibility output as an application adapter,
   never as a framework-wide domain or Kernel rule.
7. Demonstrate provider-free acceptance first, then conduct authorized
   real-authority and provider checks separately. Fixtures prove conformance;
   they do not prove a production domain.

For grid-specific capability composition and operational details, see
[`pandapower-capability-composition.md`](pandapower-capability-composition.md)
and [`PANDAPOWER-APPLICATION.md`](../PANDAPOWER-APPLICATION.md).
