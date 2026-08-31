# Capstone Agent Framework

Capstone assembles evidence-backed agent applications over authoritative
business-domain systems. It is not an LLM shell, a generic REST client, or a
replacement source of truth: models compose bounded semantic capabilities,
while the registered domain authority computes or retrieves facts and admits
the evidence that supports them.

## What is implemented

```text
ApplicationProfile -> AgentApplication -> DomainBinding -> Domain Pack
                                      -> capability-agent-kernel
                                      -> registered authority
```

The Kernel is domain-neutral. It materializes runtime contracts and guides,
provides the tool catalog, bounded context, trajectory/artifact/replay
primitives, and owns the composite `core` lifecycle/audit result. A Domain Pack
uses only the public SPI to own its contracts, policy, guides, executor,
projectors, and current-run authority. The selected authority owns registered
domain access, deterministic or source-backed results, revisions, and evidence.

`analysis-generic` emits `capability-agent-output/1.0` with framework-owned
`core` and Domain-Pack-owned `domains.<binding_id>` payloads. A vertical
application may project that result into a stable public compatibility contract
without making that contract a Kernel requirement.

## Application integration boundary

An application selects an explicit `ApplicationProfile`, binds one Domain Pack,
and supplies its reader-facing output contract. It may own CLI compatibility,
provider setup, reporting, and workbench presentation. It must not make the
Kernel depend on domain semantics, raw authority objects, credentials, or a
particular output schema.

The model receives only allowlisted semantic tools plus bounded framework
context/decision tools. It never receives shell access, arbitrary code,
generic filesystem access, raw business objects, credentials, or arbitrary
network endpoints. Final prose is ordinary model output; the controller binds
current-turn result/evidence lineage before committing an answer.

## First verified application: Grid Static Analysis

`grid-static-analysis` is Capstone's first formal application. Its
`pandapower-domain-pack` binds the grid contracts, policies, `gridctl` executor,
projectors, and current-run authority; `grid-simulator` exclusively owns
registered networks, pandapower calculations, result datasets, model revisions,
and evidence. The versioned `grid-agent` compatibility CLI retains its exact
two-field stdout envelope: `question_id` and `answer_output`.

The generic path and explicit compatibility path have both been exercised:
provider-free application acceptance runs real semantic `gridctl` calls and
checks lineage, replay, reports, and `core` plus `domains.grid`; authorized
provider runs completed both canonical business task suites through the generic
path. This validates the framework/application boundary without claiming that
all future domains or multi-domain routing are already implemented.

## Proven reuse and remaining work

The inventory reference service and Domain Pack prove that an independently
installable, read-only domain can use the public Kernel SPI and generic Pi
transport without modifying protected framework paths. It is conformance
infrastructure, not a production application.

C.2 has a recorded working theory for a GitHub Repository Intelligence domain;
it is not selected or implemented. Governed writes, approvals, tenant/actor
scope, idempotency, compensation, dynamic discovery, and multi-domain routing
remain future work.

## Design rules for every domain

1. Define reusable semantic capabilities and an explicit authority protocol.
2. Keep credentials and raw authority internals outside model-visible tools.
3. Bind reader-facing claims only to current-run admitted evidence.
4. Keep framework core, domain payload, and application compatibility output
   distinct.
5. Prove the domain with provider-free acceptance and separately authorized
   real-authority/provider checks; do not promote fixtures to production proof.
