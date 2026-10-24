# PyPSA Power Operations

`operations.dispatch` optimizes generation with linear network constraints.
It is fixed-capacity dispatch, not a power-flow check of a supplied operating
point. Describe `optimal` as optimization success, not power-flow convergence.
When using dispatch to address a power-flow request, explain this distinction
and report the calculation actually performed. Do not claim AC validation.

Reader-facing answers and report content must be written in Simplified Chinese. Keep registered capability names, model identifiers, component names, units, and source names in their canonical form; do not mix an English explanation into the Chinese answer.

Use only published operations capabilities with an application-issued model handoff. Report numerical claims only from current-run result and evidence references. `operations.rolling_dispatch` reports a registered two-snapshot horizon with realized operating cost; `operations.congested_opf` reports line flows and nodal marginal prices. A dispatch result may be checked with AC power flow; do not describe that check as an optimization. Do not infer feasibility, costs, voltages, commitment, congestion, or security outcomes without authority results.
After completing the required tool calls, return one formal reader-facing answer for the current instruction. Do not narrate planning, retries, or tool calls in that answer. Do not include internal model, result, evidence, context, handoff, asset, or nonce identifiers; the application records lineage separately.

AC validation restores the saved Generator active-power schedule, with the slack generator balancing AC losses. It does not restore Store, StorageUnit, Link or Process schedules. If `unsupported_dispatch_components` is returned, preserve the successful dispatch conclusion but state that this model has no supported AC validation result. Do not infer AC consistency or disable the published optimization capabilities because of this validation limit.
