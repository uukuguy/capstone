# Product comparison and adoption implementation plan

> Execute task-by-task with focused tests and reviewable commits. Preserve unrelated control drafts and recovery sources.

**Goal:** Close the paragraph continuation loop with source-aware comparison and durable user adoption.

**Architecture:** Application-owned series and adoption contracts compose existing immutable ProductRefs, Thread authorization, event persistence and product previews. Source dependencies remain separate from series membership.

**Stack:** Existing Python/PostgreSQL backend and React/TypeScript App.

Design: [comparison and adoption](../specs/2026-11-14-product-comparison-adoption-design.md).
Owner: capstone-agent and capstone-app; destination dev. Written spec approved; implementation active on feat/product-comparison-adoption-20261114 in .worktrees/product-adoption. Next: integrate exact-source service, API and existing preview UI; acceptance remains the full real task loop. No CI approval exists.

## 1. Durable series and adoption

- [ ] Create application module product_series.py for strict versioned requests, membership and adoption transitions; add test_product_series.py before implementation.
- [ ] Inspect thread_deliveries.py publish transaction and thread_service.py memory/PostgreSQL ownership; add atomic series persistence and receipt storage through their existing transaction boundaries. Keep presentation logic outside thread_service.py.
- [ ] Verify exact ProductRef against existing product ledger without title matching. Test known file lineage and explicit cross-lineage association separately.
- [ ] Test initial unadopted state, adopt/change/clear, stale expected_revision, exact retry, ownership rejection, rollback and real PostgreSQL reconnect recovery.
- [ ] Run focused tests and commit with journal/checkpoint.

## 2. Sources and bounded comparison API

- [ ] Project actual admitted paragraph sources from producer submissions; never infer them from model prose. Cover multiple source files and absent source history.
- [ ] Create product_series_http.py using existing workspace/Thread authorization and bounded request bodies; attach through host_api.py.
- [ ] Provide paged series versions, adoption receipts and bounded text comparison using exact bytes/digests. Apply explicit processing limits independent from storage quotas.
- [ ] Test permission parity, pagination, byte corruption, unsupported format, oversized comparison and absence of partial adopted state on failures.
- [ ] Run direct API/product consumers and commit.

## 3. Existing preview integration

- [ ] Add strict TypeScript series/request parsers and transport methods alongside threadProducts.ts and threadHttpTransport.ts.
- [ ] Add focused ProductComparison panel inside ThreadProductsWorkspace.tsx; reuse its existing preview, session state and reference callback.
- [ ] Show actual source selections, explicit same-series association, original/new text difference and adopt/change/clear actions. Keep source lineage and series history visually distinct.
- [ ] Test duplicate names, conflict refresh, keyboard controls, failed reads, prior draft preservation and two distinct paragraph references.
- [ ] Run focused App tests, type checks and build; inspect screenshots against accepted enterprise workspace; commit.

## 4. Real acceptance and integration

- [ ] Prepare managed runtime in an isolated implementation worktree using setup/install-pi/doctor; preserve auth state without copying it.
- [ ] Rebuild via make capstone-local-rebuild and run a real model task that produces and revises Markdown from two selected paragraphs.
- [ ] Verify immutable original bytes, exact source provenance, explicit membership, comparison, adoption, refresh/session recovery and subsequent explicit adopted-product reference.
- [ ] Check concurrent adoption in two clients and failed adoption preserving input. Save bounded receipts/screenshots under ignored runs/.
- [ ] Run scoped cache maintenance, independent review, local direct-consumer tests and documentation checks. Repair blockers before requesting CI approval.
- [ ] Register the active branch owner/target/acceptance/next step and update actual dev control graph at boundaries. Request one scoped macOS CI only after concrete local review; integrate through dev PR, synchronize actual dev, preserve recovery data and close verified merged branches.

## Measured progress

- 3efef824: pure explicit series transitions, two behavior checks.
- 7260d01c: PostgreSQL state and retry receipts; real database rollback/reconnect checks.
- 9b612758: indexed exclusive membership and paged audit, trusted actor included in retry identity.
- 32dbd31b: literal Markdown comparison with explicit byte/line/output budgets.
- 384f5ec6: private HTTP adapter, not yet host-mounted at this boundary.
- These module tests do not establish full acceptance. Service authorization, in-memory parity, bounded projections, existing UI integration and real model/browser recovery remain required.
