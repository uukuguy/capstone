# PyPSA Four-Pack Completion Worklist

**Status:** active after the four first publications
**Scope:** the capability families named in the [approved design](../specs/2026-09-25-pypsa-multibinding-domain-packs-design.md), implemented as bounded workflows over registered authority models.

The existing four Packs and multi-binding handoff are the foundation. A row is
complete only when its installed authority executes a real PyPSA 1.3 model,
the Pack publishes a semantic contract, target-owned result and evidence pass
current-run admission, the coverage catalog is updated, and an installed-wheel
two-binding application can reach it. Distinct authority formulations get one
focused real-solver test; existing receipt and replay tests are reused.

| Pack | Remaining workflow | State |
| --- | --- | --- |
| Network Modeling | bounded typed time-series derivation and model validation | planned |
| Power Operations | rolling horizon and explicit congested grid OPF | planned |
| Capacity Planning | combined capacity plus commitment | planned |
| Capacity Planning | multi-period investment pathway | planned |
| Capacity Planning | two-scenario stochastic investment | planned |
| Capacity Planning | near-optimal alternative (MGA) with distinct objective meaning | planned |
| Sector Coupling | registered heat-pump balance | implemented; installation verification pending |
| Sector Coupling | variable COP, hydrogen and heat storage balance | implemented; installation verification pending |
| Sector Coupling | multi-port conversion and curated electricity-hydrogen-heat balance | implemented; installation verification pending |

## Execution order

1. Complete Sector workflows while the fixed Link formulation is open. Add
   only registered fixture fields needed for time series, Store and multi-port
   components. Avoid general user-defined component APIs.
2. Complete Planning formulations using PyPSA's documented investment,
   stochastic, and MGA accessors. Persist formulation and objective meaning
   separately from the raw model revision.
3. Complete Operations rolling horizon and congested OPF, then add bounded
   time-series derivation and validation to Network Modeling.
4. Keep the two-field grid CLI and existing pandapower evidence contract.
   Verify each Pack from clean wheels and the final integrated `main` checkout.

The package map's names are capability ownership, not a promise to expose every
PyPSA option. Raw Network, DataFrames, caller-supplied Linopy expressions,
arbitrary solver options, and unregistered datasets remain excluded.
