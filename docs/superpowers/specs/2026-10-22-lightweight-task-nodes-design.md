# Lightweight cohesive task nodes

The user approved this repair after the 221802 cost audit. Keep independent
contexts, selected read-only inputs, incremental planning and whole-goal review.
The four completed tasks took 221.5/249.6/335.6/245.1 seconds. Their recorded
LLM spans took 214.0/242.2/326.7/232.0 seconds; tool spans took 6.6/8.0/8.7/13.4.
The run failed at 801.209467 seconds when research_summary reached 67557
characters against its 65536 limit. The comparison baseline remains 145.914727.

## Chosen change

Use a compact file return through the existing node finalization path. A new
tool or queue is unnecessary. Prompt-only brevity would leave the mechanical
protocol burden in place. A shared writable context would weaken ownership.

New Application 1.17 / Pack 1.14 / shared policy 1.4 selects lightweightTaskNodes.
Existing publications retain their exact text and old return format. New nodes
write `.capstone-products.json` once using `capstone-task-return/1`: outputs
(slot, summary, scope, observation aliases, files with path/role), numbered
checks (check, status, observations, explanation), and limitations. The host
builds the existing full proposal binding and exact check labels. Aliases are
local to the committed action and map only successful tool observations or
explicitly selected inherited observations. Unknown aliases and unsupported
checks fail before freezing. Only selected products are published; incidental
scripts are not automatically added. File safety, immutable storage, reference
admission, parent assessment and whole-goal closure remain unchanged.

The child gets one concise assignment and selected result summaries/file handles.
Full binding/version metadata stays in the ledger and read-only internal contract.
The parent compact state projects actionable identities and result summaries,
without repeated input source-version arrays in nodes and actions. Full state
remains recoverable through graph_ref. Capacity limits are not increased.

User correction: a model-summary capacity overflow must not terminate the whole
task. The selected adapter converts oversized context into a bounded window with
explicit record counts, omitted text counts, graph/checkpoint identity and paged
overview recovery. The request guard validates the exact prepared window. This
applies in DEBUG mode too; no false completion or ledger truncation is allowed.

Planning declares only outputs needed for the next decision or final delivery.
Discovery may return a concise observation. Intermediate tasks return reusable
data plus findings rather than mandatory long documents. Necessary source and
numerical checks remain task-owned. Repeated calculations need an identified gap.
No domain, fixed branch count, fixed model-call count or artificial time cutoff.

## Verification

Fail first for compact returns, foreign aliases/bindings, checks and selected-file
publication. Exercise the actual dispatcher and existing admission path. Prove
that compact projection preserves refs/goal/recovery while full lineage is intact.
Check old publications and legacy tests. Rebuild through the canonical command,
verify source identity, and run a bounded real node chain before full acceptance.
Reuse prior authorized results for completion where the application supports it.
Full fresh performance acceptance requires a complete report and indicator files;
a resumed run cannot replace the original baseline comparison.
