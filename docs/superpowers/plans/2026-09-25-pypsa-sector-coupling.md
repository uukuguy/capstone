# PyPSA Sector Coupling Pack Plan

**Status:** implemented; focused tests, full offline gates, type and boundary checks, and clean-wheel package smoke passed
**Design:** [approved four-pack design](../specs/2026-09-25-pypsa-multibinding-domain-packs-design.md)
**Predecessor:** Network Modeling, Power Operations, and Capacity Planning on `main`.

## First publication

Publish one registered electricity-to-hydrogen conversion and demand-balance solve.
The authority constructs the installed two-carrier model, solves a fixed HiGHS
linear optimization, and reports electricity generation, conversion input,
hydrogen delivery, conversion loss, and objective. The source model reference
crosses from Network Modeling through an application grant for purpose and
family `sector`. Result and evidence belong to the sector binding and identify
the precise source revision, formulation, solver, and optimal condition.

This first release does not publish heat, storage, multi-port processes, or
arbitrary carrier/link construction. Those remain planned capabilities.

Official PyPSA 1.3 references: [single-node sector coupling](https://docs.pypsa.org/v1.3.0/examples/sector-coupling-single-node/),
[Link component](https://docs.pypsa.org/v1.3.0/user-guide/components/links/), and
[optimization overview](https://docs.pypsa.org/v1.3.0/user-guide/optimization/overview/).

## Implementation order

1. Add one registered electricity-hydrogen model to the model authority and a
   fixed `pypsasectorctl` endpoint. Extend revision reconstruction for typed
   carriers and Links. Verify the real solve and one invalid-reference boundary.
2. Add the separately installable `pypsa-sector-coupling-domain-pack` through
   the public Kernel SPI. Verify receipt denial, a granted two-binding solve,
   target evidence admission, and output projection in one focused test.
3. Add coverage, setup/test/build/boundary entries, and clean-wheel smoke.
   Align both READMEs, architecture, runbook, and onboarding docs.
4. Run focused tests followed by the supported repository gates, package
   artifact gate, type/boundary checks, and main-checkout grid CLI verification.
