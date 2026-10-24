# Deterministic delegation

Accepted direction: the model owns research questions and changing dependencies;
the runtime owns scheduling, queueing and execution facts. The 182.182-second
review ran two children sequentially while its answer claimed parallel execution.

Reuse the native child executor and its configured concurrency. Add a neutral DAG
scheduler to the delegation adapter. Validate IDs, edges and cycles before any
child starts. Start all ready nodes up to capacity. Queue remaining nodes. A failed
dependency blocks its dependants; unrelated work continues. Cancellation prevents
new starts and waits for active children to settle. Returned dependency results
are observations, never certified evidence or extra filesystem grants.

An accepted research objective may declare subtasks with questions, instructions,
expected outputs and dependencies. After its execute checkpoint commits, the
application invokes the same guarded delegation tool without another model turn.
The parent receives actual results and host references, then records and assesses
them. It can change future work in the existing assessment transition. A child
completion does not mark a research objective met. Existing objectives without
subtasks retain their execution contract. Do not merge questions automatically or
invent independence. Shared report production remains parent-owned.

Execution facts must come from events. No typography changes, new model choice,
permissions, time cutoff, parallel ledger or second thread pool are introduced.
Recovery must not silently repeat a completed automatic dispatch. Integration
must test checkpoint admission, tool receipt delivery and replay before live use.
