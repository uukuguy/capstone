# Contract-driven query efficiency

The user approved the concrete Capstone/data-gateway work split on2026-11-09.
Baseline:thr_5e4b9d3ecf34bd28ab05 / attempt_fabf40376ec5a7b3,213s,
44 model requests/181s,71 tool completions.26 gateway-tool completions include
local validation refusals; upstream requests require request_id correlation.
The other completions are39 composition wrappers,5 discovery searches and1 shell.

## Capstone-owned scope

1. Reproduce and fix neutral helper namespace inconsistency: global python and
   tools.python must be the same granted private-workspace helper; publish its
   exact signature in tools.help. No new execution or host permissions.
2. Preserve bounded corrective JSON-Schema diagnostics. Missing required property
   paths and numeric bounds come from the admitted contract, never argument values
   or arbitrary upstream error text. Keep validation refusal fatal to that call;
   do not retry or rewrite business arguments automatically.
3. Describe the actual composition envelope and helper namespaces. A model can
   inspect/read/repair local paths within one program; known response contracts
   do not mandate a separate discovery/inspection model round. Follow only issued
   version/grant-checked actions and actual dependencies. Never infer tool choice
   or reference conversion from business field names.
4. Keep requested output scope. A bounded display request does not automatically
   require full-dataset statistics, CSV products or a report. Use saved source
   observations for any requested export; do not reconstruct numerical arrays
   from reader-facing prose.

Gateway owns source-supported name/relationship resolution, schema bounds,
typed source references, exact result shapes and next-action publications. Do not
hardcode station/device/metric/table semantics, guessed paging, key_ref conversion
or hidden source limits in Capstone or Kernel. Existing ownership, evidence,
permissions and asynchronous waits remain enforced.

## Independent attribution and acceptance

Keep exact-reference, zero-seed and named-object/time instructions separate.
The named-object case is the new performance baseline; the other two bypass its
identity-disambiguation problem. Hold model/source/instruction constant and record
Capstone-only, gateway-only and joint versions separately where compatible.
Do not attribute joint improvements to one component.

For the named case, initial engineering targets are at most10 model responses,
8 remote calls and zero invalid arguments/reference/helper errors. These are
case acceptance goals, not a universal runtime budget or a promise of latency.
Count source requests separately from local callbacks, wrappers and metadata.
Record first valid fetch, elapsed time, per-phase time and full call/request IDs.
All10 final time/value pairs must match current-run source observations, with
device identity, unit basis and source coverage limits. Record unsupported names
or gateway contract gaps explicitly; do not privately seed the named task.

No CI, push or remote deployment. Local real checks follow canonical rebuild.
Gateway-dependent acceptance remains pending until the candidate publication and
its exact revision are available. No package closure follows from this patch.
