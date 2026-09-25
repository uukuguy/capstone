# PyPSA Network Modeling

Open a registered model with `pypsa_model_open`. Use its returned
`model_ref` unchanged when deriving, inspecting, or validating a revision.
Use `model.derive_series` for a bounded per-snapshot load profile. A derived
revision has a new reference; the parent remains immutable. Cite current-run
result and evidence references for factual claims. This pack does not solve
dispatch, capacity expansion, or sector coupling problems.
