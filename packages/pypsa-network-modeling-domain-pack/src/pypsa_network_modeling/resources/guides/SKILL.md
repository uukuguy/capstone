# PyPSA Network Modeling

Open a registered model with `pypsa_model_open`. Use its returned
`model_ref` unchanged when deriving, inspecting, or validating a revision.
Use `model.topology` for a bounded bus/branch view with omitted counts.
Use `model.derive_series` for a bounded per-snapshot load profile. A derived
revision has a new reference; the parent remains immutable. Cite current-run
result and evidence references for factual claims. This pack does not solve
dispatch, capacity expansion, or sector coupling problems.

The registered catalogs used by the current PyPSA application are:

- `regional-six-bus` — regional six-bus dispatch example
- `pypsa-example/scigrid_de` — SciGRID-DE example network
- `pypsa-example/ac_dc_meshed` — meshed AC/DC example network

Use these catalog IDs exactly. Do not guess alternate spellings and do not
open files outside the registered catalog.
