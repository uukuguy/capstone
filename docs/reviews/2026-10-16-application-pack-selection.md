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
- Package boundaries, type checks and doctor passed before the adapter correction.
- Development product gates and local rebuild are in progress. This report does
  not yet claim integration or deployment acceptance.

## Remaining scope

Production Claim/Profile persistence, v2, model-free Thread UI and the continuous
native execution loop remain open under Tasks 2 and 3. This slice is preparation
infrastructure, not Demo1/Demo2 business acceptance. No Provider call or cloud
deployment was performed.
