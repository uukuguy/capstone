# Session sidebar stability

Owner capstone-app. Branch fix/session-sidebar-stability-20261117 targets dev.
This restores existing navigation behavior; it introduces no new interaction.

Observed in existing5173: selecting another session temporarily reduces the
pinned section from10 rows to3, then restores10 after history loads. Pin IDs
remain durable in PostgreSQL. Cold navigation remounts SessionNavigation,
discarding its component-local descriptors for older pins outside the recent
page. The list shrinks and the browser clamps its scroll position.

- [x] Reproduce the real transient row loss and add failing cold-navigation and
  late-removal history tests in SessionNavigation.test.tsx.
- [x] Keep resolved pin metadata in the existing access-scoped session catalog.
  Reuse it synchronously on mount/reveal; refresh in the background. Invalidate
  pre-mutation history when archive/delete/restore changes catalog ownership.
  Preserve backend pin persistence, namespace boundaries and scroll behavior.
- [x] Run navigation, management, pin and entry-point consumers plus types.
  Select a focused macOS navigation gate, without solver/release checks.
- [x] Canonical rebuild; inspect existing browser cold/warm switching, stable
  pinned rows/order/position and correct selected conversation. Preserve pins.
- [ ] Review, focused CI and dev PR; actualdev rebuild/5173 acceptance. Update
  canonical worklist/register/graph. Final own closeout receipts stay ignored.

Cache records are read-only presentation metadata, never pin authority or task
data. Archive/delete/restore invalidates in-flight metadata replies so removed
rows cannot reappear from a stale response. No full-file or chat copying.

Candidate399f90f3:125 App checks/types,145 governance and canonical rebuild
passed. Five actual cold/warm switches retained10 pin rows and order; screenshots
and correct selected headings checked. [Evidence](../../reviews/2026-11-17-session-sidebar-stability-local.md).
