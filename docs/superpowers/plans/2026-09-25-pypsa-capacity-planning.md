# PyPSA Capacity Planning Pack Plan

**Status:** active implementation plan
**Design:** [approved four-pack design](../specs/2026-09-25-pypsa-multibinding-domain-packs-design.md)
**Predecessor:** Network Modeling and Power Operations on `main`.

## First publication

Publish one bounded capacity-expansion solve over a registered model revision.
The authority owns the installed model, fixed HiGHS invocation, and immutable
target result/evidence; the Pack owns `planning.capacity_expand` contract,
guide, policy, state, output, and answer admission. The result identifies the
source revision, optimized generator capacity, investment and operating cost,
formulation, solver/version, and solve condition. The target requires a
replayable application grant for purpose and family `planning` before solving.

The initial catalog contains one small extendable-generator network. Multi-period
pathways, stochastic optimization, MGA alternatives, and combined capacity plus
commitment remain `planned`, not callable. This keeps the first publication
limited to an independently verified formulation rather than implying that
the entire package map is implemented.

Official PyPSA 1.3 references: [optimization overview](https://docs.pypsa.org/v1.3.0/user-guide/optimization/overview/),
[optimization accessor](https://docs.pypsa.org/v1.3.0/api/networks/optimize/), and
[extendable generator example](https://docs.pypsa.org/v1.3.0/examples/committable-extendable/).

## Implementation order

1. Add an installed registered expansion model and fixed `pypsaplanctl` endpoint
   to `pypsa-model-authority`; write one real-solver test and one invalid-ref or
   infeasible boundary test.
2. Add the separately installable `pypsa-capacity-planning-domain-pack` through
   the public Kernel SPI. The executor checks the ledger receipt and source
   revision; no sibling Pack import or raw Network is published. One real
   two-binding test checks admission, target evidence, and projection.
3. Add machine-readable coverage, build/setup/test/package-boundary entries,
   and clean-wheel two-binding smoke. Align English/Chinese README and
   architecture/onboarding facts.
4. Run focused tests, then repository gates: `make doctor`, `make test`,
   `make test-e2e`, `make validate`, `make test-packages`, type and boundary
   checks. Integrate to `main` and verify its grid CLI envelope.
