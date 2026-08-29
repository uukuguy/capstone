# Workstream C Inventory Reference Domain Design

**Date:** 2026-08-29

**Status:** Approved program increment selected from the previously approved general-framework design

**Parent design:** `docs/superpowers/specs/2026-08-27-general-domain-agent-framework-upgrade-design.md`

## 1. Decision

Workstream C will implement a bounded, read-only inventory reference domain.
It will use only the public `capability-agent-kernel` Domain Pack SPI and the
existing generic `@capability-agent/pi-tools` transport. The implementation
must not modify the kernel, generic Pi tools, event schemas, answer commit,
replay, or Workbench core.

Inventory is selected over a ticket domain because the repository already has
a provider-free synthetic inventory conformance fixture. Promoting that seam
into independently installable production-shaped packages gives the strongest
cross-domain proof with the smallest new policy surface. Ticket mutations,
approval flows, and actor/tenant semantics remain Workstream D.

## 2. Goal

Prove that a second business-side interface resource can instantiate a bounded
agent domain without copying or changing the framework kernel:

```text
inventory question / model tool call
  -> generic descriptor-driven Pi tool
  -> inventory-capability/1.0 request
  -> inventoryctl
  -> registered read-only inventory catalog
  -> content-addressed current-run result and evidence
  -> InventoryArtifactAuthority admission
  -> inventory projector state delta
```

The proof is provider-free. It verifies the complete model-facing tool and
authority path without using paid credentials or claiming provider behavior.

## 3. Scope

### 3.1 In scope

- an independently installable `inventory-reference-service` Python package;
- an `inventoryctl` executable with a strict one-request/one-response JSON
  protocol;
- a versioned, packaged, read-only registered inventory catalog;
- an independently installable `inventory-domain-pack` Python package;
- installed capability contracts, policy, and model-facing guides;
- an inventory executor, profile, projector registry, and artifact authority;
- generic Pi transport verification using the existing
  `@capability-agent/pi-tools` package unchanged;
- source and wheel installation conformance tests;
- deterministic climb scoring and release gates for Workstream C.

### 3.2 Out of scope

- inventory creation, updates, reservations, transfers, or deletion;
- ticket workflows or any other write-capable domain;
- tenant, actor, approval, idempotency, compensation, or asynchronous actions;
- dynamic plugin discovery or installed-package scanning;
- selecting or routing multiple domains in one runtime;
- a second provider-backed end-user CLI;
- changes to `grid-agent`, `gridctl`, `grid-capability/1.0`, or `grid_*` tools;
- changes to generic kernel, generic Pi, trajectory, or Workbench behavior.

## 4. Hard invariants

1. Domain facts originate only from `inventoryctl` and are admitted only by
   `InventoryArtifactAuthority` from the current run.
2. The model receives semantic `inventory_*` tools, never shell, arbitrary
   subprocess, generic file, Python, or raw in-memory business objects.
3. The service writes exactly one JSON response to stdout. Diagnostics go to
   stderr.
4. Successful result and evidence references are content-addressed and bound
   to the current workspace and catalog revision.
5. All artifact reads are confined beneath the current workspace, reject
   traversal and symlink substitution, and verify canonical content digests.
6. Capability contracts, runtime publication, tool prefix, protocol, guide
   index, and projector IDs must agree before any model/provider interaction.
7. Existing pandapower behavior and all supported repository gates remain
   unchanged.
8. Workstream C completion requires a recorded zero-diff gate for protected
   kernel and generic-runtime paths.

## 5. Package architecture

### 5.1 `inventory-reference-service`

Namespace: `inventory_reference`

Console script: `inventoryctl = inventory_reference.cli:main`

Responsibilities:

- own the registered reference catalog and its revision identity;
- validate `inventory-capability/1.0` requests;
- execute the bounded read-only capability allowlist;
- persist canonical current-run contexts, results, and evidence;
- return typed error envelopes without tracebacks on stdout.

It depends on Pydantic and the Python standard library. It does not depend on
the kernel, any agent application, pandapower, or grid packages.

### 5.2 `inventory-domain-pack`

Namespace: `inventory_domain`

Responsibilities:

- build `DomainRuntimeProfile(domain_id="inventory-readonly")`;
- own installed capability contracts, policy, guides, descriptions, executor,
  projector registry, and artifact-authority adapter;
- translate the fixed protocol into the public kernel SPI;
- expose no reference-service internals or raw catalog objects to the model.

It depends on `capability-agent-kernel==0.1.0` and
`inventory-reference-service==0.1.0`. It does not depend on `grid-agent`,
`grid-simulator`, `pandapower-domain-pack`, or pandapower.

### 5.3 Existing packages

`capability-agent-kernel`, `@capability-agent/pi-tools`, the trajectory core,
and the Workbench are protected inputs. Workstream C may test them but may not
change them. `grid-agent` and the pandapower packages remain compatibility
products and must continue to pass their existing gates.

## 6. Reference catalog and capabilities

The service ships one immutable registered catalog, `warehouse-a`, containing
stable asset records with these fields:

- `asset_id`: portable identifier;
- `name`: reader-facing name;
- `category`: bounded classification;
- `location`: registered site identifier;
- `quantity_on_hand`: non-negative integer;
- `reorder_level`: non-negative integer;
- `unit`: reader-facing unit;
- `updated_at`: fixed source timestamp.

The catalog revision is the SHA-256 digest of its canonical JSON document.

Published capabilities:

| Capability | Purpose | Required input | Output |
| --- | --- | --- | --- |
| `environment.describe` | Publish protocol and executable capability metadata | none | environment description |
| `catalog.open` | Bind a registered catalog revision into the current run | `catalog_id` | context and revision refs |
| `asset.list` | List bounded summaries from one opened context | `context_ref`, optional category/location/limit | result and evidence refs |
| `asset.get` | Retrieve one asset from one opened context | `context_ref`, `asset_id` | result and evidence refs |
| `stock.summary` | Compute deterministic counts and reorder candidates | `context_ref` | result and evidence refs |

No capability mutates catalog state. `environment.describe` is transport
metadata and is not materialized as a model tool unless the existing catalog
rules already permit it.

## 7. Protocol and error contract

Requests use:

```json
{
  "protocol": "inventory-capability",
  "protocol_version": "1.0",
  "request_id": "caller-generated-id",
  "capability": "asset.list",
  "arguments": {}
}
```

Responses echo protocol, version, and request ID. Success contains an object
`result`; failure contains a typed `error` with `code`, `message`, and
`recovery`. Unknown capabilities, invalid arguments, unopened/foreign contexts,
unknown catalogs/assets, and integrity failures fail closed.

The executor invokes only the configured `inventoryctl` path with
`shell=False`, a fixed `request --workspace <path>` argument vector, a timeout,
and a credential-scrubbed environment. It rejects extra stdout lines,
non-objects, correlation mismatch, and malformed result/error envelopes.

## 8. Current-run artifact authority

Reference forms are domain-specific:

- `inventory-revision:sha256:<digest>`;
- `inventory-context:sha256:<digest>`;
- `inventory-result:sha256:<digest>`;
- `inventory-evidence:sha256:<digest>`.

The service persists canonical JSON under the invocation workspace:

```text
evidence/
  revisions/<digest>.json
  contexts/<digest>.json
  results/<digest>.json
  facts/<digest>.json
```

`InventoryArtifactAuthority` verifies references from same-file-descriptor
reads beneath a no-follow workspace root. Admission checks:

- reference syntax and expected kind;
- canonical document digest;
- context-to-revision binding;
- result-to-context binding;
- evidence-to-result/context binding;
- capability identity for successful tool results;
- membership in the current invocation workspace.

Answer audits reject missing, foreign, misclassified, or unlinked result and
evidence references. They never substitute projected or model-authored facts
for authority output.

## 9. Projection

The domain pack provides three projectors:

- `inventory-context-v1` records the active catalog and revision;
- `inventory-asset-v1` records bounded asset summaries;
- `inventory-stock-summary-v1` records deterministic stock aggregates and
  reorder candidates.

Each projector accepts the kernel's `VerifiedInvocation` and returns an
inventory-owned state delta implementing `model_dump`. Unknown projector IDs
fail closed. Projectors consume only admitted result mappings and paths; they do
not read the catalog directly.

## 10. Generic Pi proof

An integration test will:

1. install or build the two inventory wheels;
2. build the inventory profile and materialize its tool catalog and guide index;
3. construct the existing eight-field runtime descriptor;
4. load `@capability-agent/pi-tools` without the grid compatibility wrapper;
5. assert exact `inventory_*` tool names and schemas;
6. invoke `catalog.open`, `asset.list`, and `stock.summary` through
   `inventoryctl`;
7. admit returned references through `InventoryArtifactAuthority`;
8. project the admitted invocation into inventory state.

The test uses a scripted tool invocation and no provider credentials. It proves
the model-capability boundary and business-authority flow, not model quality.

## 11. Boundary enforcement

The repository boundary checker will add rules that:

- forbid kernel imports from either inventory package;
- forbid `inventory-reference-service` from importing the kernel, agent,
  pandapower, or grid packages;
- forbid `inventory-domain-pack` from importing `grid_agent`, `grid_simulator`,
  `pandapower_domain`, or pandapower;
- reject repository-relative `packages/.../src` literals in both packages;
- validate that the domain pack depends only on the kernel and reference
  service at the approved exact versions.

The climb source gate will hash protected paths before and after Workstream C:

- `packages/capability-agent-kernel/`;
- `packages/pi-capability-tools/`;
- kernel-owned event/replay modules;
- `packages/trajectory-workbench/`.

Any change beneath a protected path is a release blocker, even when tests pass.

## 12. Verification strategy

Focused tests run first:

- reference-service request, validation, filtering, aggregation, and artifact
  tests;
- domain-pack resource, executor, profile, authority, and projector tests;
- generic Pi inventory transport tests;
- cross-domain conformance and protected-path tests;
- clean wheel installation smoke.

Repository gates then run:

```sh
make doctor
make test
make test-e2e
make validate
```

Provider validation remains optional and must not run without explicit billed
credential authorization.

## 13. Climb score contract

Workstream C uses a new tracked climb session with these gates:

| Gate | Weight | Completion evidence |
| --- | ---: | --- |
| `reference_authority` | 25 | service protocol, registered catalog, artifacts, and typed failures pass |
| `domain_pack_spi` | 20 | installed profile/resources/executor/projectors use only public SPI |
| `generic_pi_transport` | 15 | unchanged generic Pi materializes and executes `inventory_*` tools |
| `authority_lineage` | 20 | foreign, tampered, symlinked, and unlinked references fail closed |
| `distribution_integrity` | 10 | both wheels install and smoke outside the source tree |
| `product_compatibility` | 10 | protected paths unchanged and all supported gates pass |

Target: 100/100 with no blockers and session phase `complete`.

## 14. Exit criteria

Workstream C is complete only when:

1. both inventory distributions build and pass focused tests;
2. installed resources work outside the repository source layout;
3. generic Pi transports inventory requests without grid constants or wrappers;
4. only the inventory authority admits inventory facts and current-run evidence;
5. inventory projection uses admitted artifacts and rejects unknown projectors;
6. protected kernel, generic Pi, event/replay, and Workbench paths are unchanged;
7. existing grid product contracts and all deterministic repository gates pass;
8. climb records 100/100 with linked run artifacts and zero blockers;
9. no provider-backed validation is used for the completion claim;
10. the implementation is integrated on `main` with no temporary worktree or
    feature branch left behind.

## 15. Rejected alternatives

### 15.1 Ticket domain first

A useful ticket domain quickly raises write, approval, actor, tenant,
idempotency, and compensation questions. Those are Workstream D concerns and
would weaken the single-domain SPI proof.

### 15.2 In-memory synthetic fixture only

The repository already has this proof. It does not exercise packaging,
subprocess transport, installed resources, or current-run artifact authority,
so it cannot close Workstream C.

### 15.3 Copying `grid-agent` and renaming symbols

This would produce another vertical application while hiding framework
coupling. Workstream C must reuse public SPI and generic Pi transport instead.

### 15.4 Dynamic plugin discovery

Discovery and multi-domain routing enlarge the trust surface before the
single-domain package contract is proven. They remain Workstream E.
