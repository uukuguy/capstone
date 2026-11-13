# Branch ownership audit — 2026-11-14

Follow-up: the user approved PPT integration and reference-research closure.
Reference head 2bd086af is now archived, with dirty docs preserved. Its composition
proof runs on the current lightweight chain; remaining projection questions are
design backlog. PPT increments are in candidate29c0ce72 plus renderer fixes,
not yet merged. See [integration receipt](2026-11-14-presentation-integration.md).
The original audit below records the earlier disposition.

## Result and scope

Baseline dev is `4b857ac9`. This audit changes references and control records,
not runtime code. The previous statement that the architecture slice was closed
did not mean every development branch was integrated. Git ancestry alone also
does not prove feature acceptance or the absence of equivalent later changes.

Thirty non-archive/non-recovery local work heads were reduced to two delivery or
research heads. A separate temporary docs branch carries this audit. Twenty-eight
original heads are retained under `archive/branch-ownership-20261114/<old-name>`:
22 are ancestors of dev;6 are classified historical sources below. Seventeen old
remote heads were closed. This is an ownership decision,not a claim that their
withdrawn or experimental code was merged as accepted product.

During reference cleanup all14 worktrees retained their exact HEAD commits and
53 dirty files retained their SHA256 and size. No worktree,terminal,resource,
volume or ignored runtime state was removed. See the
[machine-readable mapping](receipts/2026-11-14-branch-ownership.json).

## Remaining delivery and research ownership

| Source | Owning work | Disposition and next boundary |
| --- | --- | --- |
| `uukuguy/ppt-template-library-20261110`,local`81dd3652`,remote`43acac28` | dev/shared application presentation;execution observation;App maintenance | The only pending implementation candidate. Keep it. Its retirement changes were already extracted through PR101. Extract remaining functional slices onto current dev;do not merge the whole historical branch or restore old CI/runtime code. |
| `uukuguy/reference-execution-research`,`2bd086af` | Secondary core-evolution/reference research notebook | Keep as independent paused research,as the user required on2026-11-07. Three commits contain designs,baseline records and a composition feasibility test. No runtime implementation is being delivered. Sync current dev and isolate validation before an explicitly resumed research slice. Do not automatically merge it into the delivery worklist. |

The PPT candidate contains three kinds of work that need their own acceptance,
without creating three idle branches now:

- Presentation library,versioned template selection,grants,source freezing,
  PPTX/PDF products,render contracts and default State Grid rendering belong to
  application presentation. Existing owners are `presentation_templates.py`,
  `native_presentation_tasks.py`,the template adapter and `tools/native_report.py`.
- Service-bus counters and current-call projections belong to the shared execution
  observation contract and its existing App consumers. Historical unknown counters
  must remain unknown.
- Gateway/sidebar/model-context and version-display changes belong to App/runtime
  maintenance. Their presence in the PPT branch does not automatically make them
  presentation features. Review direct consumers and already-accepted fixes before
  extracting them. Preserve current retirement and initial-snapshot recovery fixes.

Current local source is newer than the published remote PPT head. The remote
head is not the current local candidate and branch HEAD is not a deployment.
The archive-to-dev audit ran no model calls,solver suites or deployments.

## Six non-ancestor historical sources

| Old branch | Exact source | Verified owner and disposition |
| --- | --- | --- |
| `docs/ci-consent-policy` | `d1653424` | Current dev AGENTS contains all13 nonempty added policy lines and later refinements. Archive the duplicate policy head;repository governance remains in dev. |
| `improve/run-process-window` | `22acf1bb` | `git cherry dev` reports patch equivalence. Archive the early presentation head;the conversation UI is maintained in dev. |
| `uukuguy/presentation-templates-20261108` | `cadc2f3a` | Eight renderer/runtime/test files exactly match dev,including native report/template/layout/environment/pool code. `llm-call-tools.mjs` differs only by dev's added orchestrator role metadata;selected-call wait behavior is present. Historical design/benchmark records remain recoverable. Current incremental presentation delivery belongs to the retained PPT candidate. |
| `feat/work-attempt-binding` | local`c9e57152`,remote`5e7fccc1` | The review explicitly withdrew the simplified save/start UI and marked PR50 draft. Current Work/native conversation is owned by dev and later workspace adaptation (`b703e37b`,`7877dfaf`). The old patch is not claimed byte-equivalent. Close stale PR50;retain both source identities instead of merging the rejected application proposal. |
| `feat/research-model` | `275dc00f` | The two unique commits modify six documents only. R1 code does not exist. Move branch ownership to the Research Model design/backlog;future implementation starts from current dev under a scoped task. R0 is not R1 completion. |
| `experiment/autonomous-research` | `bf678f21` | Preserve the bounded grid R0 experiment as research reference. It owns experimental code and original evidence,not formal grid or enterprise acceptance. Do not merge it by branch-age or ancestor counts. |

The Research Model evolution plan and original R0 evidence remain the owning
design references. The exact archived sources can be opened without copying
their old runtime or replacing current architecture. `feat/business-analysis`
had no independent implementation and was already an ancestor of dev;A1 remains
planned under dev until a real scoped implementation starts. The accepted model
decision baseline and unified agent loop are already in dev,not pending branches.

## Remote preservation and closure

Before deleting the two unmerged remote aliases,annotated archive tags were pushed
and their peeled sources verified:

- `archive/20261114-branch-ownership/research-model` → `275dc00f`.
- `archive/20261114-branch-ownership/work-attempt-binding` → `5e7fccc1`.

These are recovery tags,not release or deployment acceptance tags. PR50 is closed
without claiming its old UI was accepted. Remote deletions used source-SHA leases
and an atomic transaction to reject concurrent changes;dev and main were excluded.
No commit history was rewritten. The complete local-to-archive mapping is in the
receipt;local Work source `c9e57152` remains preserved even though only the older
`5e7fccc1` was published in PR50.

Orca metadata now marks the historical template and release checkouts completed,
the PPT candidate in progress with explicit dev ownership,and reference research
paused/todo. Files and terminals were kept. Branch names under `archive/` are
recovery sources,not active delivery streams.

## Governance boundary

The checked-in workflows have no push/tag/delete or pull-request-closed trigger:
verify runs on pull_request or explicit dispatch;issue intake is manual only.
Reference cleanup,archive tags and PR50 closure therefore did not start CI.
The audit documentation must still enter dev through a PR. Creating that PR
requires a separate explicit approval for its focused macOS docs CI. No runtime
rebuild,cloud deployment or product acceptance is implied by this audit.
