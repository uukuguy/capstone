# Capstone M9 PyPSA Result/Web Projection

## Goal

Make admitted PyPSA power operation results visible through the same public
Thread `capstone-result-projection/1.0` contract already used by pandapower.
The existing assistant Web result card should render the projection without a
PyPSA-specific client protocol.

## Boundary

- `pypsa-power-operations` owns the semantic mapping from its verified
  `pypsa-operation-result/1.0` artifact to bounded summaries and tables.
- `capstone-agent` only supplies the current Thread identity and model revision,
  then validates and persists the public projection.
- The projection may expose solver status, objective, outage identity, bounded
  generator/carrier/storage/line/bus summaries, and the authority's explicit
  omitted-line count.
- The projection never returns raw PyPSA networks, pandas objects, arbitrary
  time-series arrays, or a fabricated topology overlay. PyPSA topology remains
  a separate diagram-provider task.
- Missing or unadmitted evidence is fatal to projection admission; unsupported
  result types become a typed unavailable projection through the existing Kernel
  fallback.

## Implementation

- [x] Add a Domain Pack result projector and expose it from the operations
  projector registry.
- [x] Pass the Thread model revision through the application projector seam.
- [x] Project all published `operations.*` result families with common
  summaries and bounded detail tables.
- [x] Add unit and real artifact integration coverage.
- [ ] Add a PyPSA topology diagram provider and model-specific element focus.
- [ ] Add professional Web copy/formatting specific to long PyPSA result sets
  after the shared result card is observed in the local App.

## Verification

- `pypsa-power-operations` result projector tests and full package tests pass.
- PyPSA two-binding operations profile test passes with a real registered
  dispatch artifact projected through the Domain Pack.
- Capstone Agent result/admission focused tests pass.
- Full App/API rebuild and independent M9 review completed: current-source
  rebuild is healthy and the final independent review is APPROVE.

## Closeout evidence

- PyPSA operations package: 5 passed, including real two-binding dispatch
  projection coverage.
- Capstone Agent: 386 passed, 30 skipped, 1 existing Starlette deprecation
  warning.
- Capstone App: 168 passed and production TypeScript/Vite build passed.
- Repository E2E: 39 grid cases and 3 registered-worker cases passed.
- Scoped Pyright: 0 errors; `git diff --check` passed.
- Current-source `make capstone-local-rebuild` passed; API readiness and App
  HTTP checks returned healthy.
- Independent M9 review: APPROVE, recorded in
  `docs/reviews/2026-10-04-capstone-m9-independent-code-review.md`.
