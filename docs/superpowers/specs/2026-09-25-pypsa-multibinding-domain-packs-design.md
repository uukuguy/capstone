# PyPSA Domain Packs and Multi-Binding Application Design

**Status:** approved direction; multi-binding and the registered four-Pack worklist implemented and verified on `main`
**Date:** 2026-09-25

## Decision and scope

An application will be able to select several independently installable Domain Packs. A
Domain Pack names a business capability and its principal implementation library;
the library does not define an exclusive business-domain boundary. The existing
`pandapower-domain-pack` remains the compatible implementation of grid static
analysis. New PyPSA packs use `pypsa-<capability>-domain-pack` distribution names.

This design supersedes the earlier decision to defer multi-binding composition
until after selection of a second production domain. It does not change the
`grid-agent` two-field stdout contract or grant model-side arbitrary Python,
filesystem, shell, or raw authority access. Design approval alone does not
register or publish any Pack capability.

The deliverable is a sequence of independently reviewable changes: a working
multi-binding application path, an authority-owned PyPSA model and reference
protocol, then capability packs activated one at a time. Package shells may be
created early to reserve names and record contracts. A shell has no callable
Profile, published tool, or application binding until its own conformance gate
passes.

## Why this boundary

Three structures were considered:

| Structure | Benefit | Cost | Decision |
| --- | --- | --- | --- |
| One broad PyPSA pack | Simple runtime and model ownership | Business capabilities and independent release scope remain mixed | Do not use as the target |
| One pack for each PyPSA API or example | Small wrappers | Fragments multi-step business work and model/evidence lineage | Do not use |
| Network modeling pack plus business capability packs | Stable model contract and explicit, separately published workflows | Requires real multi-binding routing and reference sharing | Adopt |

The choice follows actual PyPSA combinations: dispatch can be validated by AC
power flow; capacity and commitment can be optimized together; security
constrained dispatch builds on network/contingency results; stochastic and
multi-period planning share investment decisions with dispatch; sector coupling
extends an electricity planning model. Documentation categories are useful for
discovering functions, but they are not package boundaries. See the official
[power-flow](https://docs.pypsa.org/latest/user-guide/power-flow/),
[committable/extendable](https://docs.pypsa.org/latest/examples/committable-extendable/),
[security-constrained](https://docs.pypsa.org/latest/examples/scigrid-sclopf/),
[stochastic](https://docs.pypsa.org/latest/examples/stochastic-optimization/),
and [sector-coupling](https://docs.pypsa.org/latest/examples/sector-coupling-single-node/)
examples.

## Package map

| Distribution / binding ID / tool prefix | Contract ownership | First activation |
| --- | --- | --- |
| `pypsa-network-modeling-domain-pack` / `pypsa-model` / `pypsa_model_` | Registered model catalog, typed component/time-series construction, immutable revision derivation, model inspection and validation | First PyPSA pack |
| `pypsa-power-operations-domain-pack` / `pypsa-operations` / `pypsa_ops_` | Economic dispatch, fixed-capacity unit commitment, rolling horizon, grid-constrained OPF, selected N-1/security-constrained workflows, post-optimization AC power-flow checks | After model handoff |
| `pypsa-capacity-planning-domain-pack` / `pypsa-planning` / `pypsa_plan_` | Capacity expansion, multi-period pathway, stochastic investments, near-optimal alternatives, and explicitly named capacity-plus-commitment optimization | After operations |
| `pypsa-sector-coupling-domain-pack` / `pypsa-sector` / `pypsa_sector_` | Typed cross-carrier technologies and demands, conversion/energy-balance interpretation, curated electricity-hydrogen-heat workflows | After planning |

The package map reserves ownership, not blanket publication of every listed
PyPSA feature. Each release has its own machine-readable coverage catalog with
`planned`, `published`, and `excluded` states. Individual operations become
model-visible only after authority execution, evidence, admission, and clean
wheel conformance pass. A later market-specific pack would require its own
business boundary; redispatch and market clearing initially belong to the
operations capability plan, not an automatic fifth shell.

The installed distribution name `pandapower-domain-pack` and stable `grid_`
tool names remain compatible. Its manifest and product documentation describe
the application as grid static analysis. A future distribution rename requires
an explicit compatibility migration and is outside this work.

## Authority and model handoff

The registered PyPSA authority owns the actual `pypsa.Network`, solver calls,
data revisions, and evidence. PyPSA itself is a toolbox without business data;
the authority must register model sources and datasets explicitly. The
application selects a trusted authority endpoint for its run. Pack-specific
clients use allowlisted capability sets; they do not import another pack's
implementation or read another binding's workspace.

`pypsa-network-modeling-domain-pack` returns an immutable `model_ref`, never a
Python object, DataFrame, arbitrary source path, or serialization controlled by
the model. The authority resolves the reference to a model revision stored in
the run's authority-owned model store. A revision includes its source/catalog
identity, typed edits, time index and weightings, scenarios, component data
digest, PyPSA version, and parent lineage. A solver result identifies the
precise model revision, formulation, solver/version/options, status, and result
and evidence references. Derived revisions and results do not silently mutate
earlier references.

Network export alone cannot be the whole replay contract: a solved Network
can be reloaded without the in-memory Linopy `n.model`. The authority must
record the bounded formulation recipe, custom-constraint identifier and
version, and solver metadata separately when such capabilities are published.
No user-authored Linopy expression or `extra_functionality` callable crosses a
model tool boundary.

Cross-pack sharing uses a typed handoff record:

```text
source binding + target binding + run ID + model/result ref
  + revision digest + purpose + allowed capability family
  + authority admission + application policy decision
```

The target receives only the admitted reference and semantic metadata. The
source authority validates ownership and revision; the application records a
read-only sharing decision before target execution. Default sharing remains
deny. A shared PyPSA authority may serve several PyPSA bindings in one run,
but this does not confer access to unrelated bindings or arbitrary authority
operations. All resources and credentials remain scoped by binding and run.

Typical legal chains include:

```text
model revision -> dispatch result -> AC power-flow validation result
model revision -> capacity plan -> fixed-capacity operating result
model revision -> baseline dispatch -> contingency set -> security-constrained result
sector-coupled model revision -> investment result -> energy-balance result
```

The planning pack may publish a single combined capacity-plus-commitment solve
because PyPSA formulates those decisions together. It uses its own semantic
contract and the common authority; it does not invoke the operations pack's
internal Python code. Each step records parent references so a later answer can
distinguish assumptions, decisions, validation, and derived observations.

## Multi-binding application runtime

`ApplicationProfile.domains` becomes a nonempty ordered tuple of explicit bindings with
unique IDs and tool prefixes. Trusted application assembly selects bindings;
there is no automatic scan of installed packages. Existing single-binding
profiles retain their behavior and output schema. Binding preparation stays
deterministic, with sorted preparation and reverse cleanup on failure.

The Kernel materializes one composite catalog that maps every tool and guide
name to one binding, declared capability, protocol, executor, projector, and
authority. The model cannot choose those routing fields in tool arguments.
The Pi descriptor and extension must validate all selected bindings and route
each registered tool to its own fixed endpoint. Core context and decision tools
remain singular per application; guides are namespaced per binding. The default
Pi path must exercise this composition, not only a scripted provider fixture.

Each binding retains its own workspace, state adapter, credential lease,
policy, output payload, and current-run evidence admission. A composed answer
may cite evidence from several bindings. Each factual claim identifies its
owning binding and admitted references; a conclusion based on multiple packs
records separate supporting claims and the typed handoff lineage. No authority
is asked to certify another authority's facts. Application-level admission
combines per-binding decisions conservatively without letting an advisory
evaluation erase an otherwise valid committed answer. The composite output
keeps `core` and `domains.<binding_id>` ownership.

The current code has independent one-binding guards in
`ApplicationProfile`, `prepare_application`, `CompositeToolCatalog`, the
default Pi transport, the JavaScript descriptor/extension, and answer
admission. Removing one guard alone is not a valid implementation. Existing
multi-binding-shaped data models and binding-scoped workspaces are useful
starting points; their correctness still requires provider-free and real Pi
tests.

## Failure and compatibility rules

- Missing, stale, foreign-run, tampered, or unauthorized `model_ref`/result
  handoffs fail before calculation. A target binding cannot resolve a source
  workspace path or reuse a reference by guessing its text.
- Solver `warning`/`infeasible` and partial outputs return typed failures; they
  do not create admissible successful result claims. Objective meaning is
  recorded per operation: an MGA alternative objective is not system cost.
- Tool-name collisions, policy contradictions, incomplete bindings, endpoint
  failures, and credential-scope conflicts fail before provider startup.
- A failing binding is cleaned up with already prepared endpoints; it cannot
  leave a partially active multi-binding provider session.
- Existing grid compatibility commands continue to emit exactly one JSON
  object containing `question_id` and `answer_output` on stdout. PyPSA tools
  enter only applications that explicitly select them.
- Current-run evidence and replay keep binding identity and model/result
  lineage. Reports and observation remain diagnostic; they do not manufacture
  authority facts.

## Delivery and verification gates

1. **Multi-binding runtime.** Prove an application with the existing
   pandapower and inventory reference packs can call both through the default
   Pi extension and commit a two-source answer. Cover collisions, credential
   isolation, denied sharing, one-binding compatibility, reports, and replay.
2. **Shared model-reference protocol.** Introduce an authority-owned model
   store and explicit, admitted handoff record. Prove stale, foreign-run,
   wrong-target, and altered refs fail; no raw `Network` crosses a contract.
3. **PyPSA network modeling.** Pin an installed PyPSA/solver set, register
   small deterministic model fixtures, build and derive revisions through
   semantic operations, and run clean-install two-turn conformance.
4. **Operations, planning, then sector coupling.** Activate each pack only
   after real authority calls, current-run evidence, cross-pack handoffs, and
   clean-wheel application tests pass. Use small deterministic models first,
   then a registered realistic model for scope and performance validation.

All behavior changes run the repository's focused tests followed by `make
doctor`, `make test`, `make test-e2e`, and `make validate`. Provider-backed
checks remain optional and require separately authorized credentials and cost.
The final integration is verified from the main checkout's real application
entry point. Documentation-only edits run the repository documentation gates.

## Research evidence and limits

An isolated Python 3.12 environment installed PyPSA 1.3.0 and HiGHS 1.15.1.
Small deterministic runs exercised AC/linear power flow, dispatch and
post-optimization AC validation, capacity expansion, fixed-capacity re-solve,
unit commitment with extendable capacity, security-constrained dispatch,
multi-period investment, two-scenario stochastic optimization, MGA, and
electricity-to-hydrogen conversion. `Process` output was read from
`n.components.processes.dynamic`; `n.processes_t` did not exist in that
installation. An infeasible case returned `('warning', 'infeasible')`.

These experiments prove API availability and composition paths, not enterprise
model fitness, solver performance, or complete feature coverage. Larger
registered models and exact release pins are acceptance work for each pack.
