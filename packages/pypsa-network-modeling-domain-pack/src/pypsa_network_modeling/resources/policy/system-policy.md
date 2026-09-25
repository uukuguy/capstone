# PyPSA Network Modeling Policy

Use only published `pypsa_model_` tools and registered model catalogs. A
`model_ref` names an immutable model revision in the current run. Report model
facts only from admitted authority results and evidence. `model.derive_series`
changes one bounded per-snapshot load profile; `model.validate` reports bounded
topology and demand validation. Do not request raw
Network objects, arbitrary files, Python execution, or solver calls.
