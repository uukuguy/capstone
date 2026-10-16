# Capability Status And Intentional Exclusions

## Use This For

Use `environment.describe` as the runtime authority for what is executable now. The full static-analysis matrix is current product scope; missing rows are implementation defects, not a permanent product boundary.

## Do Not Use This For

Do not use this as permission to simulate unsupported studies, import arbitrary model files, mutate existing revisions, run raw pandapower, or infer unavailable results. Published typed revision operations remain available.

## Concepts and Terminology

An unavailable dedicated workflow can still contain steps supported by published capabilities. Check those capabilities before declaring the study impossible. Their composition proves only the cases, conditions, and objectives actually evaluated; it does not create an unpublished coupled solver.

## Available Capabilities

Published model/data discovery includes `model.dataset.list`, schema-described access to all public static element tables, and multiple registered pandapower networks. Other rows are published only when they appear in `environment.describe`; never invent an unpublished capability ID.

Unavailable in the current matrix:

- Security-constrained OPF as a distinct coupled optimizer (ordinary AC/DC OPF is published).
- Time series.
- Arbitrary model file import or in-place mutation; declarative creation and immutable typed revisions are published.
- Automatic import or interpretation of user-supplied or named-standard constraint catalogs. Explicit supplied limits on supported model fields can be applied to a child revision and checked; retain their supplied provenance rather than calling them original model limits.
- Dynamic stability, dynamic protection relay simulation, and remedial action optimization.

## Parameters and Defaults

Use `analysis.operation.list` and `environment.describe` as runtime authority. Do not invent capability IDs or schemas for missing rows.

## Result Fields and Units

No result fields or units exist for unavailable capabilities. Any value would be unsupported unless produced by an available WP-A capability.

## Single-step Examples

- "Run DC power flow" -> describe `powerflow.dc`, call `analysis.run`, then inspect the required result datasets.
- "Which registered models exist?" -> call `model.list`; do not assume only IEEE-39.

## Multi-step Examples

- "Rank sourced violations" -> run a compatible analysis, call `analysis.result.violations.evaluate`, then call `analysis.result.risk.rank`; report unavailable constraint quantities instead of inventing limits.

## Failures and Legal Recovery

If the user asks for unavailable scope, do not emulate it with a different calculation without saying so. Ask for permission only when a nearby available workflow would materially change the requested analysis.

## Evidence Requirements

Unavailable workflows produce no evidence. Do not claim evidence for future capabilities.

## Common Mistakes

- Presenting AC power flow as DC flow instead of selecting `powerflow.dc`.
- Treating N-1 as OPF or dynamic stability.
- Confusing current implementation gaps with intentional exclusions from static analysis.
