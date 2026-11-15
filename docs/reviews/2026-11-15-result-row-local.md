# Structured row references and local analysis verification

Status: implementation accepted into dev dc2aa71a through PR113; closeout accepted through PR114 at51fc1cc1 after approved docs CI43678586237 passed130seconds. Approved macOS CI43650887728 passed in 212 seconds at acc3bd30: 185 backend, 255 frontend and 271 governance checks passed, three governance checks skipped. Owner: capstone-agent/capstone-app. Product source: 419b07b8. Design: [row selection](../superpowers/specs/2026-11-15-result-row-selection-design.md). Package complete; post-merge snapshots remain local metadata.

## Delivery boundary

Exact row references bind a domain_result ProductRef, table version, row IDs, canonical column IDs and a content digest. Column labels, units, original values and nulls are frozen as historical input. Separate subsets of one parent keep separate material identities. The host validates the original result grant and immutable retained source; the browser cannot provide a replacement manifest or row contents.

Inline paging publishes only the requested immutable page. Existing paged sources use a source-bound row locator and reject missing locators or oversized publication. Selection budgets are 128 rows, 64 columns, eight source pages and 24 KiB frozen context; page reads/writes are bounded at 256 KiB. These are processing budgets, not storage quotas. Large locator sharding remains unimplemented; this slice does not establish GB-scale table processing.

Professional Work saves retain references only. Explicit Start validates and freezes selected data privately into the producer Attempt. Saved scope remains visible through refresh. A missing source before Start rejects atomically; an accepted Start retry returns its original receipt after source loss. Public Work snapshots never contain private material bytes.

The existing workspace hosts row/column controls, current-page sorting/filtering, cross-page selection, composer chips and exact report sources. Typed professional sessions can explicitly resume editing the existing Work; default legacy recovery guards and backend authorization remain. Resume does not execute a command or grant tools.

Reports include the saved model answer under a separate model-analysis heading and retain admitted Authority projections separately. Failed or missing answers are not presented as accepted model analysis. Input provenance comes from actual saved Attempt references, not model assertions.

## Verification and repairs

The final focused gate at 419b07b8 passed 185 backend/database checks, 59 frontend product/selection checks, 196 frontend composer/Work/route checks, TypeScript and build. Backend checks took 7.57 seconds. Counts from earlier checks overlap. Independent review found no remaining blocker after repairs.

Repairs included full-parent size incorrectly gating tiny selections, all-page publication amplification, loose client cursors, Unicode code-point ordering, dropped professional composer metadata, missing Work save/start freezing, invisible saved scope and invalid-reference HTTP 500 responses. Tests reproduced these cases before repair. Actual workspace-route tests cover explicit professional resume and retained legacy guards.

## Real model and browser evidence

Dedicated Thread thr_92ff32fabb0e777de6a5 and Work work_9e710eaca9e59f84db45 used a real registered IEEE39 AC powerflow. Authority-backed line_loading contains 35 rows. The original result was saved before the feature rebuild; no fixture numerical values were injected into this run.

Host pages of ten rows were read at offsets zero and ten. Exact references selected line:0 and line:10, with line, loading_percent and active_loss_mw. Page-size changes did not alter the saved table version. The same professional Work saved and started with this input; precise retries returned the original receipt.

The real model queried registered results/evidence and element identities and produced the two-row historical analysis. Its first answer had an inaccurate loss wording. A real source-backed follow-up corrected that wording and retained sample limitations; the application did not patch business conclusions. Original answers remain in the ledger.

Four report revisions remain saved: earlier table-only reports and later complete original/corrected analysis reports. The repaired report path saved the model interpretation and exact two-row references. Revision 3 versus revision 4 has 15 changed literal-text ranges. Revision 4 was explicitly adopted.

In the existing Vivaldi tab, the user flow passed: resume the typed professional Work, inspect saved input scope, open its source, select line:0 and line:10 across two pages, add/remove a draft reference while keeping typed draft text, Start the saved task, open the saved report, compare versions 3/4, clear and re-adopt version 4. Refresh and conversation switching restored adopted version 4, the exact row/column/version source and the unsent draft. The default recovery guard returned after refresh and did not cause automatic execution.

Root ignored receipts: runs/result-row-validation-20261115/. Key files: baseline.json, baseline-result.json, prepared-selection.json, saved-work.json, analysis-events.json, correction-events.json, corrected-answer.md, corrected-report.md, final-report-sources.json, report-comparison.json and adopted-report.json. Screenshots are retained with those receipts. Credentials are not included.

## Runtime and remaining integration

Product source 419b07b8 adds the final historical-source navigation repair. Opening a report source clears the presentation instruction scope and preserves the exact source through scope reset. The actual browser opened the original line table at version e23e20be; keyboard Space deselected and reselected line:0. Independent review found no blocker; 35 focused workspace tests passed.

Final canonical rebuild at product source 419b07b8 completed readiness. API and three workers run image sha256:dcc22264cdf4dcde773d4d8cbb270006422bf6736b133a993b7abb1e845f2f7e. Candidate App uses 5177. Scoped cache maintenance completed with receipt cache-maintenance-20261115-031710-31830.log. No cloud/demo deployment or release promotion occurred.

Original projection readback after the final candidate rebuild is byte-contract-equivalent to the saved baseline; adopted report v4 restored at series revision5 with the exact original row digest. The actual dev checkout control graph was regenerated and checked in Vivaldi at readable and full overview sizes. Focused local governance checks passed 123 tests in 3.68 seconds. Doctor, changed documentation links, relative CLAUDE symlink and diff whitespace checks passed.

After PR113 merged, root dev fast-forwarded to dc2aa71a; its product code is identical to acc3bd30. Canonical actual-dev rebuild passed readiness with API/three workers image sha256:636f0cb736dc97a3c957dc98d3600cfb4c8d20611b50da007f808ae0c103c358. Default App5173 restored the same professional Work after explicit resume, adopted report v4 at series revision5, and the exact two-row/three-column source. Opening that source showed table version e23e20be. Screenshots accepted-dev-report-v4.png and accepted-dev-source.png are in the root evidence directory. Scoped cache maintenance receipt: cache-maintenance-20261115-070459-56570.log. No cloud/demo deployment occurred.

The implementation and design branches are closed. Recovery worktree .worktrees/result-row-selection remains detached at dc2aa71a. Pre-integration root drafts are preserved at stash42b8f54f, and feature journal/baton at stash0f46f231. No authentication state or user data was copied or removed. Any final documentation PR requires a new explicit CI approval.
