# Workstream B Physical Package Extraction Design

**Date:** 2026-08-28

**Status:** approved, including written-spec review

**Parent design:** `2026-08-27-general-domain-agent-framework-upgrade-design.md`

**Starting point:** Workstream A is integrated at `f8d0c7e`; its neutral domain
runtime seams still ship inside the `grid-agent` distribution.

## 1. Executive decision

Workstream B will extract the reusable capability-agent runtime and the
pandapower implementation into independently versioned distributions while
keeping `grid-agent` as the compatibility application.

The extraction uses explicit, static composition. It does not introduce
runtime plugin discovery or multi-domain selection. The final dependency graph
is acyclic:

```text
grid-agent application
  |-- capability-agent-kernel (Python)
  |-- pandapower-domain-pack (Python)
  |     `-- capability-agent-kernel
  `-- @grid-static-analysis/pi-grid-tools (compatibility entry)
        `-- @capability-agent/pi-tools

pandapower-domain-pack
  `-- grid-simulator / gridctl authority boundary
```

The new distributions and import namespaces are:

| Distribution | Import/package namespace | Initial version | Purpose |
| --- | --- | --- | --- |
| `capability-agent-kernel` | `capability_agent` | `0.1.0` | Domain-neutral SPI, catalog, guides, composition, and reusable lifecycle primitives |
| `pandapower-domain-pack` | `pandapower_domain` | `0.1.0` | Pandapower profile, transport, projection, authority, and packaged domain resources |
| `@capability-agent/pi-tools` | ESM exports | `0.1.0` | Profile-driven Pi tool materialization and bounded runtime tools |

`grid-agent` remains version `1.0.1` during the extraction unless an externally
observable product change later requires a separate release decision. Local
workspace source mappings do not weaken the requirement that each new package
must build and install from its own artifact.

## 2. Why this boundary is necessary

Workstream A proved dependency injection but did not establish distribution
independence:

- `grid_agent.domain` and `grid_agent.application.composition` are neutral in
  intent but are packaged with the application;
- `grid_agent.domains.pandapower` still imports grid-specific analysis,
  integrity, and simulator modules from the application distribution;
- capability and guide materializers are reusable but live under
  `grid_agent.tools`;
- the Pi extension hard-codes `grid-capability/1.0`, `gridctl`, `grid_*` tool
  names, and `GRID_AGENT_*` runtime paths;
- the pandapower profile resolves contracts, policy, and guides from repository
  paths rather than installed package resources.

Moving only `grid_agent.domain` would create a nominal SDK while leaving both
runtime composition and the model-facing tool layer coupled to the grid
application. Moving the pandapower profile without its adapters would create a
reverse dependency from the domain package to `grid-agent`. Both outcomes fail
the Workstream B exit gate.

## 3. Goals and non-goals

### 3.1 Goals

Workstream B must:

1. produce independently buildable Python kernel and pandapower domain wheels;
2. produce an independently testable generic Pi tools package;
3. make the kernel independent of `grid_agent`, `pandapower_domain`,
   `grid_simulator`, pandapower, and grid-specific resource names;
4. make the pandapower domain package depend only on published kernel contracts
   and its simulator-side implementation, never on `grid-agent`;
5. assemble the existing `grid-agent` CLI explicitly from the extracted
   packages;
6. preserve current commands, stdout, stderr, tools, protocol, run artifacts,
   evidence admission, reports, and deterministic validation behavior;
7. prove artifact-level installation in a clean environment, not only imports
   from the source checkout;
8. retain temporary source-import compatibility shims for repository callers
   while all production implementation imports use the new namespaces.

### 3.2 Non-goals

Workstream B will not:

- load arbitrary domain packages through entry points or filesystem scanning;
- run multiple domains in one process;
- introduce a production non-grid domain;
- add write-side approvals, idempotency, compensation, tenant policy, or
  asynchronous jobs;
- rename `grid-agent`, `gridctl`, `grid-capability/1.0`, `grid_*` tools, CLI
  arguments, environment variables, or persisted schema versions;
- alter pandapower calculations, registered networks, capability coverage, or
  evidence semantics;
- expose shell, generic files, Python execution, pandapower objects, or
  DataFrames to the model;
- delete the compatibility modules in the same workstream;
- publish packages to an external registry.

## 4. Package ownership

### 4.1 `capability-agent-kernel`

The kernel owns contracts and behavior that are meaningful without knowing the
business domain:

- `DomainManifest` and compatibility validation;
- `DomainRuntimeProfile` and adapter protocols;
- capability contract sources and validation;
- deterministic capability-to-tool catalog materialization;
- guide allowlist indexing and materialization;
- profile-driven runtime preparation;
- canonical JSON and content-reference primitives;
- generic run events, immutable artifact registration, event recording,
  reading, replay, and answer-reference interfaces that have no grid semantics.

The first extraction will not blindly move every trajectory or analysis module.
Modules containing grid labels, `gridctl` authority assumptions, pandapower
fields, grid-specific projections, or grid analysis state remain outside the
kernel until they are either moved into the domain package or refactored behind
an already-approved neutral protocol.

The kernel public surface is exported deliberately from `capability_agent`.
Internal modules are not made public merely because they were importable from
the monolith.

### 4.2 `pandapower-domain-pack`

The domain package owns the complete adapter side of the Workstream A seam:

- the pandapower `DomainRuntimeProfile` builder;
- the `gridctl` capability executor and executable locator behavior required by
  that profile;
- grid capability context declarations and projector registry;
- grid state deltas and domain result projection;
- current-run content reference verification and `gridctl` authority adapter;
- pandapower-specific semantic reporting helpers required by those adapters;
- packaged model-facing guides and domain policy resources;
- installed-resource discovery for simulator capability contracts.

If an implementation currently needed by the pandapower Profile imports
`grid_agent`, that implementation must either move with the domain package or
be inverted behind a kernel protocol before the Profile moves. A dependency
from `pandapower_domain` to `grid_agent` is forbidden, including imports guarded
by `TYPE_CHECKING`, delayed imports, and test-only shortcuts.

The package may depend on `grid-simulator` as the domain implementation package.
This does not move simulator truth into the agent: network access and numerical
claims continue to cross the `gridctl` process boundary using
`grid-capability/1.0`.

### 4.3 `@capability-agent/pi-tools`

The generic Pi package owns:

- catalog-driven registration of domain capabilities;
- construction and correlation of versioned capability requests;
- sanitized subprocess execution selected by the controller-owned runtime
  profile;
- the allowlisted guide opener;
- bounded context and decision tools;
- canonical model-request capture integration.

It receives a controller-materialized runtime descriptor. The descriptor fixes
the protocol, protocol version, executable basename, executable arguments,
tool-name prefix, guide tool identity, catalog/index paths, workspace, and
trajectory paths before model invocation. Tool parameters cannot select or
modify the executable, arguments, protocol, paths, or environment.

The package must not turn generalization into arbitrary command execution. The
executable remains a validated basename from the selected Domain Manifest, the
argument template is controller-owned, secrets are removed from the child
environment, and request correlation remains fail-closed.

### 4.4 `grid-agent`

The application retains:

- CLI commands and exact answer envelope;
- provider configuration, authentication, Pi installation, and launch;
- product workspace and run directory selection;
- explicit selection of the pandapower Profile;
- continuous grid-analysis orchestration and presentation that has not yet been
  proven domain-neutral;
- compatibility re-exports under existing `grid_agent.*` imports;
- the compatibility Pi extension package and legacy `GRID_AGENT_*` mapping.

The application may depend on both extracted Python packages. Neither extracted
package may depend on the application.

## 5. Resource model

Repository-relative paths are not a valid distribution contract. Installed
resources use `importlib.resources` or the Node package equivalent and are
materialized to explicit paths only when a downstream runtime requires a real
filesystem path.

The ownership rules are:

- capability definitions remain packaged by `grid-simulator`, the authoritative
  implementation-side source; the domain pack exposes them through a
  `CapabilityContractSource` without reconstructing repository paths;
- model-facing pandapower guides and the pandapower system policy become domain
  package resources;
- versioned application/runtime configuration remains under `configs/runtime/`
  when it configures the application rather than defining the domain;
- authoritative documentation links are updated when a canonical resource
  moves; duplicate writable copies are not introduced;
- development checkout and installed-wheel execution use the same public
  resource API.

Missing or incompatible resources fail during runtime preparation before
provider I/O.

## 6. Compatibility strategy

### 6.1 Python imports

Existing repository imports such as `grid_agent.domain`,
`grid_agent.tools.catalog`, and `grid_agent.domains.pandapower` remain available
through thin forwarding modules for one compatibility cycle. These modules:

- contain no business implementation;
- emit no warnings to stdout;
- re-export only the prior public names;
- are covered by import identity and behavior tests;
- are not used by new production implementation code.

Removal of these shims is a future versioned decision, not part of Workstream B.

### 6.2 Pi imports and environment

`@grid-static-analysis/pi-grid-tools` remains the application-facing extension
and exports the current `buildGridRequest`, `createGridTool`, and default
extension behavior. Internally it delegates to `@capability-agent/pi-tools`
with the pandapower runtime descriptor.

Existing `GRID_AGENT_*` environment variables remain accepted and retain their
meaning. The application may additionally materialize a generic runtime
descriptor, but callers are not required to adopt new variables in this
workstream.

### 6.3 Runtime artifacts

Workstream B does not rewrite historical runs or change current schema versions.
The following remain compatible:

- answer JSON contains exactly `question_id` and `answer_output` on stdout;
- progress, warnings, and diagnostics remain on stderr;
- `runs/<question_id>/` layouts and current-run reference admission;
- event, trace, context, result, evidence, and report formats;
- model-visible `grid_*` tool names and input schemas;
- `gridctl` request/response correlation and typed error envelopes.

Package versions may be exposed through `doctor` diagnostics where an existing
extensible field permits it. They will not force a persisted schema change.

## 7. Runtime flow after extraction

```text
grid-agent CLI
  -> explicitly imports pandapower_domain.build_profile
  -> capability_agent.prepare_domain_runtime(profile, ...)
     -> domain contract source reads installed grid-simulator resources
     -> pandapower executor calls environment.describe via gridctl
     -> kernel intersects contracts with executable capabilities
     -> kernel materializes tool catalog, guide index, runtime descriptor
     -> pandapower authority is scoped to the current workspace
  -> grid compatibility Pi extension delegates to generic Pi tools
  -> generic Pi tools invoke fixed gridctl request transport
  -> pandapower projector and authority interpret admitted results
  -> grid-agent controller commits the same answer and lineage
```

There is no implicit default inside the kernel. If the application does not
select a Profile, or selects incompatible package versions, startup fails before
provider I/O.

## 8. Error handling

The extraction preserves current typed failures and adds packaging-specific
diagnostics:

1. **distribution error:** required package or declared resource is unavailable;
2. **compatibility error:** kernel, domain pack, protocol, or descriptor version
   is outside the supported range;
3. **boundary error:** a forbidden import is detected by the build/test gate;
4. **profile error:** manifest or adapter is incomplete;
5. **transport error:** the fixed domain executable cannot start, times out, or
   returns an uncorrelated response;
6. **integrity error:** result, evidence, authority, or lineage cannot be
   admitted;
7. **projection error:** domain state cannot be derived from a valid result.

Configuration and compatibility failures appear on stderr and use the existing
failure answer envelope when a CLI command requires one. Observation,
projection, or reporting failures still cannot replace simulator truth.

## 9. Controlled migration sequence

The implementation is divided into independently revertible stages:

1. **Characterize distribution behavior.** Add build/install, import-boundary,
   public-import, resource, catalog, and CLI compatibility tests before moving
   implementation.
2. **Extract the Python kernel.** Create `capability-agent-kernel`, move the
   approved neutral slice, and replace old modules with compatibility exports.
3. **Extract generic Pi tools.** Make request construction and bounded tools
   descriptor-driven; retain the grid compatibility entry and exact behavior.
4. **Extract the pandapower domain pack.** Move the Profile and every adapter it
   needs until the new package has no `grid_agent` import.
5. **Switch application assembly.** Make `grid-agent` depend on and explicitly
   compose the extracted packages; remove production use of compatibility
   imports.
6. **Prove installed artifacts.** Build wheels/package archives, install them in
   a clean temporary environment, and run provider-free smoke and compatibility
   tests outside editable source imports.
7. **Close documentation and gates.** Update architecture, runbook, bilingual
   README facts, package manifests, lockfiles, and durable project/climb state;
   run all supported deterministic gates.

Each behavior change begins with a failing focused test and ends with an atomic
commit. A stage may contain several small commits when that keeps moves,
compatibility shims, and behavior changes independently reviewable.

## 10. Verification strategy

### 10.1 Boundary tests

Automated tests must prove:

- `capability_agent` imports with neither `grid_agent` nor pandapower domain
  modules installed;
- kernel source contains no imports or resource literals owned by grid or
  pandapower;
- `pandapower_domain` imports without `grid-agent` installed;
- the domain package has no `grid_agent` dependency in source or metadata;
- `grid-agent` production modules import the new namespaces rather than
  compatibility shims;
- the dependency graph contains no cycle;
- package resources load from built wheels in a non-repository working
  directory.

### 10.2 Compatibility tests

Tests compare the pre-extraction and post-extraction behavior for:

- manifest values and environment compatibility;
- ordered tool names, schemas, descriptions, and catalog fingerprint;
- guide resource IDs and contents;
- `grid-capability/1.0` requests and correlation failures;
- secret sanitization and fixed executable invocation;
- pandapower projector output and current-run evidence admission;
- offline CLI answer envelope, run artifacts, reports, and E2E scenarios;
- existing source import paths through forwarding modules.

### 10.3 Repository gates

After focused tests, the supported gates remain:

```sh
make doctor
make test
make test-e2e
make validate
```

The workstream also adds an artifact-install gate that builds each new package
and exercises their public APIs in a clean temporary environment. Provider-backed
validation is not required and must not run without separate authorization.

## 11. Climb ladder and score

The completed static-analysis climb session will be archived before the new
ladder begins. Workstream B uses a new session whose score is the sum of six
objective subscores:

| Subscore | Weight | Full-credit evidence |
| --- | ---: | --- |
| Kernel independence | 25 | Independent wheel/import succeeds; forbidden-import and neutral-resource gates pass |
| Domain ownership | 20 | Profile and required adapters live in `pandapower-domain-pack` with no `grid_agent` dependency |
| Pi tool generalization | 15 | Generic package is descriptor-driven; grid compatibility snapshots pass |
| Application thinness | 10 | `grid-agent` explicitly composes packages and production code avoids compatibility shims |
| Distribution integrity | 10 | Clean artifact install and non-repository smoke tests pass |
| Product compatibility and repository gates | 20 | Focused compatibility, `doctor`, unit, E2E, and deterministic validation all pass |

The target is `100`. A subscore is binary at its declared gate unless its
adapter defines named, independently verifiable partial checkpoints. A higher
score cannot compensate for a failed stdout, simulator-authority, evidence, or
secret-handling contract; those are release blockers.

The initial hypotheses are:

- **B-H001:** artifact and import characterization can define a safe extraction
  baseline without changing behavior;
- **B-H002:** the approved neutral slice can move into
  `capability-agent-kernel` with compatibility imports preserving callers;
- **B-H003:** Pi registration and request transport can become descriptor-driven
  without exposing arbitrary process execution;
- **B-H004:** all pandapower Profile dependencies can move or invert so the
  domain pack has no application dependency;
- **B-H005:** `grid-agent` can assemble the extracted artifacts and remain
  behavior-compatible under clean installation and all deterministic gates.

Failed hypotheses remain recorded. Alternative implementation branches are
compared by the same scoring adapter; experiments never silently change product
defaults.

## 12. Exit criteria

Workstream B is complete only when all statements are true:

1. the three new distributions build and pass their own focused tests;
2. the kernel contains no grid or pandapower implementation dependency;
3. the pandapower domain package contains no `grid_agent` dependency;
4. the generic Pi package contains no hard-coded grid protocol, executable, or
   tool prefix in its reusable execution path;
5. the compatibility Pi entry produces the same grid requests and tool surface;
6. `grid-agent` explicitly composes the extracted kernel and domain package;
7. clean artifact installation works outside the repository source layout;
8. old public imports remain functional through implementation-free shims;
9. current CLI, tools, simulator boundary, runs, answers, and evidence behavior
   remain compatible;
10. all focused tests and supported deterministic repository gates pass;
11. climb records a score of 100 with linked run artifacts;
12. no provider-backed or billed validation is needed for the completion claim.

Passing Workstream B does not by itself prove a general framework. It establishes
the independently packaged substrate. Workstream C remains the program-level
proof that a production non-grid domain can be added through these public
packages without modifying kernel implementation.

## 13. Rejected approaches

### 13.1 Python SPI-only extraction

Moving only the Workstream A protocol modules is fast but leaves catalog,
guides, runtime preparation, Pi transport, and pandapower adapters owned by the
grid application. A second domain would require another kernel migration, so
this is rejected as a false package boundary.

### 13.2 Dynamic plugin discovery now

Entry-point discovery, arbitrary installed-pack scanning, multi-domain
selection, and capability collision policy belong to Workstream E. Adding them
before single-domain packages are stable increases trust and compatibility
surface without helping the Workstream B exit gate.

### 13.3 Shared `grid_agent` namespace across wheels

Having multiple distributions contribute implementation modules to the same
regular Python package creates ambiguous ownership and installation-order
behavior. New distributions use distinct namespaces; old paths are explicit
forwarding modules owned only by `grid-agent`.

### 13.4 Copying resources into multiple packages

Duplicated capability contracts, guides, or policy files would create competing
sources of truth. The design assigns one canonical owner and accesses installed
resources through published locators.
