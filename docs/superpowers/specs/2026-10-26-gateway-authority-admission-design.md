# Gateway model admission into the calculation Authority

Status: proposed scope for review. No import capability or gateway calculation acceptance is implemented by this document.

## Current boundary and evidence

Stage B reads frozen electrical structure through the protected application backend.
Stage C additionally needs Authority admission, calculation, saved results and an
exact element mapping. Stage C is currently unsupported for gateway bundles.

The existing pandapower Authority opens only packaged registered factories:
[engine.py](../../../packages/grid-simulator/src/grid_simulator/engine.py),
[model_catalog.py](../../../packages/grid-simulator/src/grid_simulator/model_catalog.py)
and `context.open` in
[operations.py](../../../packages/grid-simulator/src/grid_simulator/operations.py).
There is no published bundle import operation. `OpenedContext.origin` permits
registered, created and derived contexts; it has no imported provenance contract.
Running `pandapower.runpp` in the general native executor would not produce an
admitted Authority result and cannot close Stage C.

Read-only inspection on 2026-10-26 verified this actual gateway validation bundle:

| Field | Verified value |
| --- | --- |
| Artifact reference | `c2feb87c7961b0aab99ab02d94e3c57eff4eb8215b2564ee7393e750d5d3b2f3` |
| ZIP SHA256 | `5946e0754c0497738d9bd2983c2157f25331ae800c47cc6817e88bbb09d58b2f` |
| ZIP bytes | 12,488,511 |
| Map SHA256 | `62ba9cacece0c79de4b1390197bd7fcafee1f4af87852415cc3a3b6bf599c54e` |
| Model | `grid:east`, pandapower 3.4.0 |
| Native element coverage | 998 buses, 893 lines, 563 transformers, 848 loads, 8 external grids |
| Quality | `demo_only=true`, `power_flow_ready=true`, `real_power_flow_ready=false` |

Both hashes matched the actual bytes. Files include `model.pandapower.json`,
`element-map.json`, `calculation-structure.json`, `source-model.json`,
`quality.json` and `demo-assumptions.json`. Package metadata is an external
`.artifact.json`; there is no `manifest.json` member in this ZIP.

Evidence is held in the separate gateway repository at
`runtime/electrical-validation/models/<artifact_ref>.zip` and
`docs/validation/electrical-views-2026-10-26/README.md`. Its report explicitly
records construction, native reload and mapping checks, without a solve for this
large model. This cache is an independent validation service; availability of
this reference on the released 18001 service is not established. Do not treat
the reference as available there without checking that service.

The bundle map has schema `gateway-element-map/1`, typed `element_key`,
`element_table`, `element_ref`, engine version, model revision, selection,
source snapshot and scenario revision. Calculation devices use those element
references. The source capture explicitly lacks verified transaction consistency;
accepted D30 keeps that limitation visible without blocking admission.

## Selected approach

Use a trusted application artifact broker and a narrow public Authority import
capability. This preserves
[Application → Domain Pack → Kernel → Authority ownership](../../architecture/capstone-framework.md).
The Kernel does not gain gateway semantics or model deserialization.

| Alternative | Decision |
| --- | --- |
| General native executor loads and solves a downloaded file | Rejected: bypasses Authority results and evidence. |
| Add the current gateway model to the packaged factory catalog | Rejected: fixes one artifact and loses reusable provenance. |
| Application stages a verified artifact; Authority imports an opaque grant | Proposed: reusable, bounded and compatible with existing solver contracts. |

The first unit supports pandapower 3.4.0 JSON packages and their actual integer
indices. Other engines and unsupported key types fail explicitly; they are not
silently converted. PyPSA import and optimization are separate work.

## Admission contract

The application broker uses only the configured gateway and fixed
`get_network_model_artifact` / `read_network_model_artifact` operations. Those
operations remain unavailable to the general research tool catalog. The broker
accepts an application-selected artifact reference, streams bounded chunks to
private storage, verifies size and archive digest, and issues an opaque
`input_ref`. It does not pass full-file base64 through model context.

The server-owned grant binds the current task/attempt, registered Authority,
artifact reference and digest, engine/version, source model revision, scenario,
map digest, immutable storage object and explicit permission for demo data.
Neither the model nor the browser supplies storage paths, URLs or credentials.
Upload/storage quotas remain separate from import processing budgets.

Proposed public `grid-capability/1.0` operation: `model.artifact.import` with
`{input_ref}` only. The application-selected Domain Pack exposes this semantic
operation only when the task has the corresponding broker grant. Use the existing
private `gridctl --workspace` provisioning path, with a durable grant manifest
and content-addressed input storage; no new service is required. The host installs
an execution binding for the current task/attempt in that protected workspace.
The public capability request carries no attempt identity, so caller arguments
cannot establish this binding. The Authority compares the grant with the installed
binding before resolving stored content. A missing, revoked, foreign or expired
grant fails before input file access. General Pi cannot write grants or bindings.

The Authority validates the archive before loading: reject traversal, absolute
paths, links, duplicate member names, unexpected required-file substitutions,
and decompression beyond the processing budget. Read only the expected files.
Use data-only reconstruction of the supported JSON split tables in the Authority
runtime. Parse with a plain JSON parser, validate table names, columns, integer
indices, scalar values and allowed dtype metadata, then construct tables and a
native network through fixed Authority code. Reject unsupported serialized objects,
controllers and executable metadata. Do not execute bundled scripts, pickle
payloads or caller-selected constructors. There is no `pp.from_json` or
`pp.from_json_string` fallback for untrusted bundle content.

This requirement follows inspection of the pinned pandapower 3.4.0
`pandapower/io_utils.py`: `FromSerializableRegistry.rest` at line 658 imports the
payload-selected module, resolves its class and calls its constructor or
`from_dict`. Its DataFrame handler at lines 544–557 passes absolute `.json` strings
to `pd.read_json` as paths. Therefore, even a valid bundle hash does not make the
generic decoder safe. Regression tests must reject both object construction and
file-path payloads without importing their modules or opening their paths.

Validate the native model and map together. Engine version and bundle/map
identities must match. Every supported native element key must have one exact
map entry, and every mapped key must exist after native reload. Preserve integer
keys as integers; never join by display name or row position. Validate endpoint
references against the same native model. Missing source-port roles remain gaps.
`demo_only` and declared assumptions remain attached to the admitted model.

Persist atomically before returning: normalized native bytes, the Authority
revision, imported-origin lineage, original bundle/map identities and an import
receipt. Write content-addressed model, mapping and evidence objects first, then
commit the context record last. Only that final record makes the import usable;
interrupted preparation can leave unreferenced objects, never a partial context.
The Authority revision is a content identity of the admitted native
model, distinct from the gateway `model_revision`; record their explicit link.
Import failure exposes no usable context. Repeated admission of the same granted
content is idempotent. Import receipts describe provenance and validation, not
calculation success or source operating truth.

Return bounded typed references: `context_ref`, `revision_ref`, `model_id`,
`import_receipt_ref`, `mapping_ref`, engine/version and demo/readiness flags.
Application model selection uses this admitted binding. Existing registered
models and their factory path remain unchanged.

## Calculation and result projection

Run existing `analysis.powerflow.ac.run` on the admitted context. Require its
saved convergence status, `result_ref` and evidence references. Then call
`result.branches.rank` with `metric=loading_percent`, `direction=descending`,
`element_kind=line`, `limit=3`. Rank persisted results, not model-written values.

Join each verified result's `pandapower_index` and element table to the admitted
map, then to the calculation view's `element_ref`. Save an application layer
binding Authority/context/revision/result, gateway model/revision/artifact,
scenario, map digest and calculation `view_ref`. Preserve metric units and
`demo_only`. Reject changed revisions, wrong maps, duplicate keys or unadmitted
results before overlay. No source-view overlay is inferred without explicit
mapping. Nonconvergence is a saved failure state; it must not produce a success
ranking or zero-valued substitute results.

## Runtime dependency paths

| Owner | Required changes |
| --- | --- |
| Application | Protected artifact broker, durable input grants and host-installed task/attempt binding through existing private workspace provisioning; `kernel_capability_preparation.py` and `model_capability_context.py` bind imported models through existing Authority selection. |
| Domain Pack | `pandapower-domain-pack` semantic import schema, tool publication, execution routing and provenance policy. |
| Authority | `grid-simulator` capability definitions/registry, `operations.py`, `models.py`, `workspace.py` and a focused import module; imported-origin integrity and mapping storage. |
| Projection | `grid-agent/thread_network_view.py` and application electrical-view layer adapter consume verified imported identity and typed element keys. |
| Packaging | Include new capability/schema resources in package manifests; rebuild API/worker with the same source identity and provide the Authority's private input-store binding. General Pi receives no model input mount. |

Do not expose the broker as arbitrary file access through the Domain Pack. Do not
change global simulator registries at runtime or couple another Domain Pack's
state to this admission.

## Acceptance and next unit

First run the existing registered IEEE-39 Authority test chain to verify the
solver/ranking/projection baseline. The direct public request sequence is
`context.open {model_id:ieee39}` → `analysis.powerflow.ac.run {context_ref}` →
`result.branches.rank {result_ref,metric:loading_percent,direction:descending,element_kind:line,limit:3}`.
Use `uv run --project packages/grid-simulator gridctl request --workspace <private-test-workspace>`
with one JSON `grid-capability/1.0` request on stdin per operation. This baseline
does not prove gateway import or gateway mapping.

After review, implement admission as one coherent unit with these gates:

1. Deterministic rejection tests for foreign grants, corrupt archives/maps,
   unsafe members, decoder payloads, engine mismatch and integer/string key mismatch.
2. Imported-origin context and map integrity survive process restart; failures
   and interrupted writes cannot leave a usable partial context.
3. Import the actual verified East demo bundle through the broker grant, run the
   registered Authority, and retain the real solve outcome. No claim of convergence
   is made in advance. Never adjust source data merely to force acceptance.
4. On convergence, save top-three line results and verify every highlighted
   calculation element through the exact map and baseline; reload the saved layer.
   If it does not converge, preserve that evidence and select a separately declared
   small supported demo artifact for the success-path test.
5. Test wrong-revision rejection, source/calculation separation and visible demo
   status. Check the real App result display after the canonical local rebuild.

The user has authorized Capstone Stage C implementation. This document defines
the next implementation scope for review; it does not add an authorization gate.
Sibling gateway edits remain prohibited. Research-adapter model-build permissions
remain unchanged, and calculation acceptance still requires the evidence above.
