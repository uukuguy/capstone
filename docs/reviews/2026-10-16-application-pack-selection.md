# Application Profile / Pack selection

Implementation: `32f08c31`, with structural adapter correction `20226bf0`.

The same ApplicationProfile, DomainBinding and DomainRegistry can declare authority
and native Packs. Native declarations do not require a model or Authority. Explicit
binding selection prepares only the requested resources and retains the complete
profile and ReferenceGrants. Empty selection has no resource side effects.

The Kernel accepts native preparation through a neutral SPI. The Capstone adapter
checks the registered Pi host's published resource profile and load receipt. It
returns immutable resource and executor identity, not simulator evidence. Missing
optional resources do not block preparation. Required resources must be available.

Professional execution retains its policy and Authority contracts. The legacy
runner rejects selected native bindings before starting resources. Registry
resolution cannot silently change a binding's execution kind. A failed preparation
closes previously prepared endpoints.

## Verification

- 18 focused selection/resource tests passed, including mixed configuration,
  grants, immutable receipts, missing resources, policy isolation and cleanup.
- 28 application/preparation regression tests passed. The two warmup adapter
  regressions were corrected and passed separately.
- Independent review found a mutable-receipt gap. Type and immutable-field
  checks now reject it; the reviewer confirmed the fix.
- Final focused gates passed: 642 Kernel tests, 1349 Capstone tests, 3 registered
  worker tests and type checks. 65 Capstone tests retain their conditional skips.
  Package boundaries and doctor passed. Earlier local full runs stopped after
  adapter regressions were identified; they are not recorded as passing full gates.
- Candidate graph: 23 nodes and 30 edges, checked at 1280 and 1920 pixels without
  overlap, through-card edges, crossings or page overflow. Existing professional
  Thread and electrical topology remain readable in the real App.
- Canonical local rebuild passed. API, worker and PyPSA worker use image
  `sha256:d5eb7fb8e69f18a9160028a6350e7fa8edbe16f7578e39fcd2a77e83c595f519`.
  All 1150 source files/link targets per role match `20226bf0`.
  Receipt: `runs/application-pack-selection/local-identity.json`.
- The worker read the actual private Pi host publication and obtained a native
  preparation receipt without a model call. Receipt:
  `runs/application-pack-selection/native-publication.json`. The API has no direct
  route to that private host; validation used the registered worker network.
- The first product CI run was cancelled after it exceeded the desired early
  development duration. A comparable earlier product gate took 39 minutes.
  `cb08ef92` adds the reviewed foundation allowlist and a 15-minute step limit.
  Authority/solver/native-bridge/dependency changes and unknown paths still
  select product; main still selects release. Governance tests: 51 passed.
- Added dependency checks passed locally: inventory conformance/multi-binding
  12, real hosted/Thread assembly 10, professional adapters 34, pandapower Pack
  143 and PyPSA application 55. Additional existing PyPSA suites also passed.
- PR46 CI `38916542829` passed: Linux 8m49s and macOS 10m22s, including setup.
  The normal merge `9eb84a34` has the exact tested `cb08ef92` tree. The dev
  checkout was fast-forwarded and the implementation branch closed. Product
  runtime stays at the verified `20226bf0`; later changes are CI/control only.

## Remaining scope

Production Claim/Profile persistence, v2, model-free Thread UI and the continuous
native execution loop remain open under Tasks 2 and 3. This slice is preparation
infrastructure, not Demo1/Demo2 business acceptance. No Provider call or cloud
deployment was performed.
