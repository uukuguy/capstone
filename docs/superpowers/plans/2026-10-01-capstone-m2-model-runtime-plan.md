# Capstone M2 — Real Model Catalog and Runtime Dispatch

## Goal

Make the Capstone application consume real Authority model identities and
select the matching Profile/runtime by implementation family. The Kernel and
Thread remain domain neutral; pandapower and PyPSA stay behind application
registration adapters.

## Scope

1. Introduce one neutral model identity validator. It accepts registered
   hierarchical IDs such as `pypsa-example/scigrid_de`, while keeping run,
   thread, profile, and family identifiers strict. Model page IDs are derived
   through one stable, path-safe function.
2. Extend the Authority catalog boundary with immutable public metadata:
   authority reference, display name, and diagram provider identity. The
   Thread snapshot continues to persist only the identity needed for replay;
   raw Authority records never cross the boundary.
3. Add a composite model catalog that registers disjoint Authority adapters,
   rejects duplicate IDs/defaults, resolves exact revisions, and exposes
   bounded listing metadata for Web/TUI/CLI projections.
4. Add a family runtime dispatcher to the Capstone application assembly. It
   routes a leased Attempt to the factory selected by the immutable model
   context and fails closed for an unregistered family.
5. Register the real PyPSA catalog IDs through the existing PyPSA Authority
   adapter. `pypsa39` remains only as a legacy test fixture and is removed from
   production model labels; no fake model is added to the Authority.
6. Add focused tests, boundary checks, and documentation. Do not co-install
   incompatible pandapower/PyPSA simulator environments; the composite catalog
   is an application registration seam and actual cross-environment hosting
   remains an explicit adapter/process concern.

## Verification

- Focused Capstone model/catalog/protocol/dispatch tests.
- PyPSA catalog tests for `pypsa-example/scigrid_de` and exact revision shape.
- `python tools/check_package_boundaries.py`.
- `make doctor` and the package-scoped Capstone and PyPSA suites.
- A formal code review report for M2 with severity-classified findings.

## Non-goals

- No automatic semantic conflict detection between Domain Packs.
- No per-tool toggles or multi-Run Thread behavior.
- No raw pandapowerNet/PyPSA Network in Thread state.
- No direct Web/TUI connection to Pi or DSH.
