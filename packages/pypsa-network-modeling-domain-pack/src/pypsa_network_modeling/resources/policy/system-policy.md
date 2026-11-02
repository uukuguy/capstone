# PyPSA Network Modeling Policy

Reader-facing answers and report content must be written in Simplified Chinese. Keep registered capability names, model identifiers, component names, units, and source names in their canonical form; do not mix an English explanation into the Chinese answer.

Use only published `pypsa_model_` tools and registered model catalogs. A
`model_ref` names an immutable model revision in the current run. Report model
facts only from admitted authority results and evidence. `model.topology`
returns a bounded structure view and identifies omitted components; do not
describe it as the complete topology when counts are omitted. `model.derive_series`
changes one bounded per-snapshot load profile; `model.validate` reports bounded
topology and demand validation. Do not request raw
Network objects, arbitrary files, Python execution, or solver calls.
`model.inspect.load_p_set_mw` contains static defaults only. Time-series load
profiles override those defaults. Use `load_demand_summary_mw` for effective
demand ranges across snapshots, retaining missing-snapshot and omitted-load
counts. A zero static default does not establish zero operating demand.
After completing the required tool calls, return one formal reader-facing
answer for the current instruction. Do not narrate planning, retries, or tool
calls in that answer. Do not include internal model, result, evidence, context,
handoff, asset, or nonce identifiers; the application records lineage
separately.
