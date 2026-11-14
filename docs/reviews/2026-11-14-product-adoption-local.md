# Product comparison and adoption local verification

Scope: application-owned immutable file versions, explicit series membership, literal Markdown comparison and durable user adoption. Product implementation is on feat/product-comparison-adoption-20261114, targeting dev. This record does not establish cloud or release acceptance.

## Implemented and checked

- Original ProductRefs stay exact; multiple admitted paragraph sources remain separate from explicit series membership. A product has one series, with indexed membership and bounded pages.
- Registration, adoption, change and clear persist trusted actor scope, time and revisions. PostgreSQL owns a Thread row lock; state, membership, audit and retry receipt commit together. Memory storage is Thread-scoped.
- Adoption verifies retained bytes through fixed 64 KiB streaming chunks. Storage and comparison budgets remain separate. A 6 MiB binary test rejects whole-object get calls; it is not a measured GB trial.
- Markdown comparison admits fixed byte/line/output budgets, returns literal line opcodes and specific failure codes. The existing preview hosts comparison, source links, member navigation and adoption controls; existing composer references stay version-fixed.
- Independent review found and prompted repairs to memory isolation, inappropriate adoption format limits, generic failure messages and member cursors. Actual browser inspection found toolbar width collisions and duplicate sibling keys; regression tests reproduced the duplicate preview before repair.

## Measured local checks

After the review fixes, the focused gate passed 122 backend/database tests, 58 frontend tests, TypeScript and App build. Supplementary backend checks covered 71 database/host/streaming checks and 24 source/cloud-error checks. Frontend fixes passed 43 focused checks, then 40 preview/identity checks. Counts overlap and must not be added.

The canonical rebuild completed with project-scoped cache maintenance. Latest backend image: sha256:8bcee8cd3516ed4e801b0c92c391e788ab6f7eb635a25dd1e7b2336df45a9059. API and worker readiness passed. Candidate App uses port5176. Subsequent frontend commits397d43b6/928c7aee were served by the worktree Vite process. A source docstring correction changes no behavior. Exact final PR source and post-merge source checks remain integration work.

## Real model and browser

Dedicated verification Thread: thr_82eab8cb58cc8741909b. Its real saved paragraph-validation.md and paragraph-followup.md retain the original two selected paragraph identities. Live sources API returned two full local selections; comparison returned five line ranges. Original series registration and adoption each returned identical receipts on exact retry.

An explicit adopted ProductRef was submitted to the same Work. The real model saved adopted-continuation.md, referencing blue cup and green notebook, with no rewrite of prior files. The attempt reached terminal state. This extends the original real-model paragraph continuation, rather than treating fixtures as model acceptance.

Vivaldi existing tab verification on the final frontend passed:

1. Open saved follow-up, select the original default and compare literal text.
2. Clear adoption (series revision4), adopt it again (revision5), refresh and recover.
3. Open newly generated continuation, explicitly choose follow-up as original and associate with its series (revision6). The prior adopted version stays selected until a user decision.
4. Adopt the continuation (revision7), switch to another conversation and return; the exact adopted file and series revision restore.
5. The compact drawer has one comparison panel; buttons and bounded source labels remain readable in the existing workspace layout.

Ignored receipts and screenshots: runs/product-adoption-validation-20261114/ in the implementation worktree, including sources.json, comparison.json, receipts.json, continuation.json, continued-products.json, comparison.png and restored.png. These contain dedicated verification content, not operator credentials.

## Remaining acceptance

Final original-byte readback matched the saved original digest. Seven series decisions restored at revision7. Nine additional ObjectStore/direct gate checks passed. Independent final review found no blocking defects; its21 backend checks included one skipped database check and do not replace the actual PostgreSQL gate. Control graph inspection and dev PR integration remain required. Each CI run still requires explicit approval. Deployment remains local-dev only; demo and cloud are unchanged. A decision timeline and automatic scrolling to a source paragraph are deferred presentation improvements, not replacements for saved audit and exact source references.
