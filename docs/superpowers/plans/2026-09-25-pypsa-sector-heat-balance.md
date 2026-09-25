# PyPSA Sector Heat Balance Implementation Plan

**Status:** active implementation plan
**Design:** [approved four-pack design](../specs/2026-09-25-pypsa-multibinding-domain-packs-design.md)

## Goal and boundary

Publish `sector.heat_balance` in the existing Sector Coupling Pack. The source
is one registered single-snapshot electricity-to-heat model: a fixed-capacity
electricity generator, a heat demand, and a heat-pump Link with fixed COP 3.0.
The authority solves a fixed HiGHS formulation and returns electricity input,
heat delivery, COP, operating-cost objective, source revision, solver and
optimal condition. A target-owned result and evidence pair is admitted only
after an application grant with purpose and family `sector`. No temperature
data, user-authored COP, heat storage, or arbitrary Link constructor is exposed.

PyPSA 1.3's [sector-coupling example](https://docs.pypsa.org/v1.3.0/examples/sector-coupling-single-node/)
models heat pumps as Links with COP in `efficiency`; the
[Link contract](https://docs.pypsa.org/v1.3.0/user-guide/components/links/)
defines positive input `p0` and negative supplied output `p1`.

## Tasks

1. Add a failing authority test in
   `packages/pypsa-model-authority/tests/test_sector_coupling.py` for the
   registered heat model's 10 MWh electricity input, 30 MWh heat delivery,
   COP 3.0, cost 200, target evidence, and wrong-model rejection.
2. Add `electricity-heat-pump` to the installed catalog, extend the fixed
   authority workflow and `pypsasectorctl` publication, and retain the same
   result/evidence schemas and source/target verifiers.
3. Publish one new Sector Pack contract. Update the executor allowlist, policy,
   guide, and the existing clean-wheel smoke to run both hydrogen and heat in
   one granted two-binding application. Do not add a duplicate receipt-denial
   test; the existing Sector test already owns that assertion boundary.
4. Update the coverage catalog and English/Chinese product docs. Run the
   focused authority test first, then `make doctor`, `make test`,
   `make test-e2e`, `make validate`, `make test-packages`, type and boundary
   checks. Integrate to `main` and verify the real grid CLI envelope.
