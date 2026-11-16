# Durable workspace session pins

Accepted by the user on 2026-11-16: pins must persist in the backend. The
no-login stage shares pins within one workspace across browser origins and
devices. Different workspaces and deployment databases remain isolated.

## Incident and ownership

The localhost App had an empty local pin list. The 127.0.0.1 origin retained ten
pins; all ten Thread resources still existed. Browser-origin storage isolation,
combined with local-only preferences, caused the apparent loss. The earlier
tab migration did not address this boundary.

Application management owns preferences. No Domain Pack, Kernel execution or
Authority evidence changes are needed. This decision supersedes the browser-only
pin preference in the enterprise UI design; sidebar width remains local.

## Contract

An authenticated or explicitly open workspace API reads all pin identities and
applies individual pin/unpin operations. PostgreSQL stores workspace revision
and per-Thread state. Transactions serialize workspace writes. Explicit unpin
records remain as tombstones. Legacy import only inserts previously unseen
identities, so stale browsers cannot undo an explicit unpin. A workspace revision
survives deletion of its last pin. Every reference is checked against workspace
ownership. Public demo credentials cannot read or mutate these preferences.

The App uses its existing management transport. It imports valid legacy pins
without deleting original browser records. A successful backend response is the
source of truth. Older responses cannot replace a newer revision. Read and write
failures retain the last confirmed state and show a retry action. Tab focus and
bounded periodic refresh reconcile changes from other clients. No failure is
converted into an authoritative empty list. Bulk cleanup rechecks backend pins
and cannot remove a pinned session through its protected deletion operation.

## Acceptance

Restore the ten original pins. Verify persistence across refresh, localhost and
127.0.0.1, independent clients and API restart. Test workspace isolation,
concurrent writes, stale migration after unpin, malformed legacy data and network
failure. Run focused backend/App checks, canonical local rebuild, real PostgreSQL
and existing-browser checks. CI and dev integration remain separate acceptance
steps and require the repository's explicit CI approval.
