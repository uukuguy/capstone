# Version-bound local references implementation plan

Status: implemented in the independent branch; local candidate a65b35b6 rebuilt and checked. Not merged into dev; no cloud/demo promotion or CI approval.

## Verified delivery boundary

- Application-owned Markdown paragraph indexes, immutable private objects, PostgreSQL leases and isolated parsing are implemented. Only top-level Markdown paragraphs are supported.
- Exact local selection identity flows through existing admission, composer and preview. Two paragraphs from one parent produce distinct historical materials, with no whole-artifact claim.
- Real model validation in Thread `thr_82eab8cb58cc8741909b` created the original Markdown, continued using two paragraphs, and preserved original bytes. Exact HTTP retry returned the same receipt. PostgreSQL retained two distinct materials and two local provenance records.
- Vivaldi verified preparation, two selections, independent removal, re-add, third-turn submission and refresh restoration. A later capacity correction passed 23 focused tests and was rebuilt; saved indexes and the browser paragraph entry remained available.
- Evidence: research worktree `runs/paragraph-validation-20261114/`. Standard rebuild and project cache cleanup passed. Current App is port 5175; backend source a65b35b6 uses image 0b11a6ff7757. Demo and cloud did not change.
- PostgreSQL admission/retry check at 7ef73be1 passed: deleted source rejects fresh resolution, while exact retry returns its receipt and execution keeps frozen paragraph bytes. The 26 related checks passed.
- Pending: independent review (reviewer startup failed), dev PR/control integration, keyboard-only and unsent-draft restoration coverage, GB-scale chunk processing, hard parser memory isolation, source I/O deadlines and orphan-index cleanup. These are not claimed complete by the small-file slice.

The task checklists below remain the original detailed acceptance checklist. The verified boundary above records measured delivery; unchecked items must not be interpreted as all unimplemented or automatically accepted.

**Goal:** Select a paragraph from an existing text product, continue in the same conversation, and retain exact source identity and historical products.

**Architecture:** The application owns parsing, reference admission and presentation. Existing command, execution and product paths remain the integration points. The Kernel receives admitted context; Authority evidence rules stay in their existing owners.

**Stack:** Python application-owned markdown-it-py 4.2.0 and the existing React/TypeScript App. The browser consumes opaque host-issued block identities and verifies byte digests; it does not derive parser identities.

Source: [research and experiment](../../capstone-app/2026-11-14-code-mapping.md). Owner: enterprise application research; destination: dev after review and focused acceptance. Implementation is active; dev integration remains pending.

## Constraints

- Parent ProductRef stays exact and version-bound. Existing full-product and leading-excerpt semantics remain compatible.
- Start with complete paragraphs in UTF-8 text/Markdown. Other formats need their own contracts.
- Only host-published block identities can be admitted. Current selection grants no additional permission.
- Storage quotas, parsing budgets and model-context budgets are separate. Large products need bounded indexing/read access; an inline-copy shortcut is not the final architecture.
- User-authored text is data. Historical products never automatically become current Authority evidence.
- Run only focused local checks. Each CI run requires separate explicit approval.

## Task 1 — Resolve parser ownership and publish a bounded block contract

Research recommendation resolved: Python application-owned markdown-it-py parser and server-issued manifests. Existing environment is 4.2.0. Declare a direct dependency at implementation time, version configuration, and avoid browser/backend AST equivalence. See the Python experiment in the research record. Nested paragraph semantics and GB-scale background indexing remain explicit scope decisions.

- [ ] Inspect the deployed backend/native runtime dependency boundary before choosing parser packaging.
- [ ] Compare a host-owned parser service with a backend parser plus server-issued manifest. Do not require browser AST paths to match an independently implemented Python parser.
- [ ] Record the selected runtime, parser/config version identity, byte-to-character conversion, resource limits and unsupported-format behavior.
- [ ] Add a small application-owned block index module alongside `thread_products.py`. Store parent identity, parser identity, block identity, source span and digest; return bounded pages.
- [ ] Add meaningful tests for repeated paragraphs, Unicode, code/table exclusion, parser-version mismatch, unavailable parent and bounded access.
- [ ] Verify the same bytes resolve before and after serialization. Record database recovery separately.

Acceptance: a server-published paragraph can be resolved exactly; forged identity and stale parent cannot resolve. Task 2 must not start until parser packaging is decided.

## Task 2 — Admit local selections through existing commands

Affected: `thread_products.py`, `thread_input.py`, existing `thread_service.py` call sites, `general_pi_executor.py`, and `test_thread_products.py`.

- [ ] Introduce a versioned local-selection contract without adding fields to the strict old schema silently.
- [ ] Check ownership, parent version, block identity and digest before the existing Attempt transaction.
- [ ] Include the full selection identity in deduplication and material identity; preserve independent selections from the same product.
- [ ] Preserve idempotent retry, source provenance and historical-only status.
- [ ] Expose actionable selection errors through the existing rejection projection.
- [ ] Run focused reference/command tests, including source disappearance after admission and untouched prior Work.

Acceptance: invalid references do not mutate task state; an admitted selection survives source disappearance for exact retry; no Authority elevation occurs.

## Task 3 — Reuse preview, composer and reference chips

Affected: `ThreadProductsWorkspace.tsx`, `threadProducts.ts`, `ProductReferenceChips.tsx`, `CapstoneAssistantThread.tsx`, `ThreadWorkAdapter.tsx`, and their direct tests.

- [ ] Present selectable server-published paragraphs in the existing product preview.
- [ ] Show parent name/version and a bounded paragraph preview in the existing composer context.
- [ ] Support keyboard selection, removal and multiple blocks without duplicating conversation UI.
- [ ] Freeze submission context; later UI selection changes cannot alter the submitted instruction.
- [ ] Test duplicate text, two blocks from one parent, stale selection feedback and draft restoration.

Acceptance: local continuation stays in the selected conversation and uses the explicit source version.

## Task 4 — Real continuation and recovery

- [ ] Rebuild through `make capstone-local-rebuild` after runtime source changes.
- [ ] Use a real saved Markdown product and real model execution to revise a selected paragraph.
- [ ] Confirm the produced file, old product bytes and source linkage; the old product remains accessible.
- [ ] Refresh and switch sessions; confirm submitted references and products restore from PostgreSQL.
- [ ] Check Vivaldi screenshots against the accepted workspace design, including keyboard and failure states.
- [ ] Run scoped cache maintenance and record exact runtime identities and receipts.

Acceptance: submit, execute, inspect products, continue and restore all work. JSON roundtrip and fixture tests alone do not meet this gate.

## Integration

- [ ] Keep reviewed research commits on the independent branch; implementation uses an explicitly owned package and acceptance boundary.
- [ ] Update canonical worklist, register, journal and graph at each boundary.
- [ ] Prepare a focused dev PR only after local evidence is complete; request approval before any push or PR action that triggers CI.
- [ ] Do not promote the source or change demo deployments as part of this slice.
