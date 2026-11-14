# Result row selection implementation plan

Goal: exact structured result rows flow through existing task submission, local analysis, source inspection and product adoption.

Owner: capstone-agent/capstone-app. Destination: dev. Accepted via PR113 at dc2aa71a; one approved macOS CI43650887728 passed at acc3bd30. Actual dev rebuild and original table/report recovery passed. Product and design branches closed; recovery worktree remains detached. Final control receipts await documentation integration. Design: [row selection](../specs/2026-11-15-result-row-selection-design.md). Evidence: [verification](../../reviews/2026-11-15-result-row-local.md).

## 1. Versioned row identity and bounded resolver

- [x] Inspect result_projection.py, result_table_store.py and current result-table routes; identify a real registered result table with published pages.
- [x] Write failing tests for version-bound row/column selections, duplicates, nulls/units and cross-page identity.
- [x] Add application-owned result_row_selection.py; preserve strict old ProductRef/paragraph contracts. Define host-published table identity and normalized selection digest.
- [x] Extend immutable table storage with bounded row location where needed; do not scan unbounded manifests/pages for selected rows. Test forged grants and read budgets.
- [x] Run focused projection/store checks and commit.

## 2. Admission, sources and authenticated endpoints

- [x] Extend checked_selections/freeze_product_selection in thread_products.py, thread input validation and selected-material provenance with a distinct typed row selection.
- [x] Freeze selected values before Attempt transaction; verify full selection material identity, professional historical-only context, atomic rejection and exact retry after source disappearance.
- [x] Add host-authenticated table page/selection preparation endpoints; enforce Thread/workspace scope, bounded request bodies, trusted object locations and typed errors.
- [x] Extend product source projections to preserve row selection identity. Test actual PostgreSQL commands and reconnect; do not count skipped database tests as passes.
- [x] Commit verified backend slice with journal/checkpoint.

## 3. Existing table and composer integration

- [x] Extend TypeScript reference parsers, transport and ThreadClient without weakening existing schemas.
- [x] Add row/column selection to existing ResultProjectionCard/result workspace; preserve topology focus, directory and composer.
- [x] Persist cross-page view selection identity; show row/column chips, source version, removal and error recovery. Use unique sibling keys.
- [x] Test sorting/filtering/page changes, same values in distinct rows, keyboard access, draft preservation, forged responses and submitted-reference recovery.
- [x] Run focused App checks/build, inspect actual existing workspace screenshots, commit.

## 4. Real task and integration

- [x] Prepare isolated worktree runtimes; register branch owner/target/acceptance/next step in canonical worklist/control.
- [x] Rebuild via make capstone-local-rebuild; use a real registered result table and real Provider to perform selected-row analysis with actual tools and saved report.
- [x] Check exact row sources, original result unchanged, no implicit Authority elevation, report comparison/adoption, refresh and conversation switch recovery.
- [x] Run source/reference/direct-consumer gates, independent review, project-scoped cache cleanup and control graph browser inspection.
- [x] Prepare exact dev PR and request one focused macOS CI before triggering it. Integrate accepted change, synchronize actual dev, verify real entry and preserve recovery sources. No release-sized gate or cloud/demo promotion.
