# Capstone Conversation Contract Completion

> **For agentic workers:** Execute inline with test-driven development and focused review. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete remaining requirements in the existing agent-conversation designs while preserving the deployed user version.

**Architecture:** Web consumes committed Thread answers and changes only their visible height. One-time bulk operations record existing completed message IDs; there is no default for future answers or backend summary projection. Domain Pack admission, Authority results, current-run references, and immutable Attempts remain unchanged.

**Tech Stack:** Python, React/TypeScript, assistant-ui, Vitest, local Compose/Vite.

## Sources and scope

- [Mainline baseline](../specs/2026-10-01-capstone-mainline-rebaseline-design.md).
- [Web primary contract](../specs/2026-10-01-capstone-thread-web-ui-main-contract.md), especially §5.3, §5.1 and Phase E.
- [M6 implementation](2026-10-02-capstone-m6-harness-case.md) and [M6 design](../specs/2026-10-02-capstone-m6-harness-case-design.md).
- [Interaction discussion](../specs/2026-09-29-agent-interaction-discussion.md): accepted runtime/reference boundaries remain distinct from proposals.

The user directs continued completion of these conversation plans. The core capability evolution notebook is secondary research and cannot select the next package.

## Delivery ledger

| Package | Status | Scope | Depends on | Acceptance |
| --- | --- | --- | --- | --- |
| CONV-01 | local implementation and verification complete; independent review/release pending | One-time history folding and per-answer bidirectional toggles | Revised Web contract §5.3 | Existing completed answers only; future answers remain full; short/error/running messages remain visible; full copy, stable scroll/draft; local rebuild and browser checks |
| CONV-02 | local implementation; acceptance in progress | Contract audit and completion of evidence-state/action feedback | Existing admitted public projections | Distinguish available/not_applicable/missing/pending/unavailable without inventing references; keyboard and touch interaction |
| CONV-03 | audit complete; record consolidation pending | Reconcile bounded M1–M11 closures and deferred successor work | Existing implementation and review evidence | Preserve M6 lightweight closure and later full gates; consolidate portable M6/M10 review records without reopening completed functionality |
| CONV-04 | needs design review | Accepted pure Pi reference path and context isolation | Conversation completion audit | Separate bounded gateway path and explicit non-authoritative output; exact comparison scope and implementation plan before code |
| CONV-05 | explicitly deferred adapter work; execution integration incomplete | Generic registered runtime capabilities | M2 review's successor requirement and mainline baseline §4.1 | Compile selected verified skill/MCP/plugin registrations into the runtime session and manage lifecycle; preserve domain-tool and authority boundaries; do not reopen M2 |
| Final TUI / real DSH / multi-Run | deferred in existing decisions | Separate client/runtime designs | Applicable design decisions | Do not mark as complete; do not undo the accepted TUI freeze or M6/M11 exclusions |

Status is based on implementation and evidence, not checkbox counts alone. Add newly found contract gaps to the owning package. Do not use the deployed Web version as proof that the complete conversation design is finished.

## Priority correction and major gaps

The user asks for major unfinished work and questions further UI-detail changes.
Do not expand Web styling or polish. Finish verification of the current small
changes, then prioritize CONV-04: the accepted runtime comparison/isolation
contract. `HarnessPiClient.runtime_mode` and the runtime registry are partial
seams; they do not establish gateway switching, immutable Attempt authority mode,
separate business memory, or a non-authoritative reference history.

CONV-05 is the M2 review's explicitly deferred Harness adapter step, not an
uncompleted M2 registration seam or a new capability-evolution research agenda.
The descriptor registry and injected `runtime_capabilities` attributes
exist, but the factories currently retain the registry without compiling its
selected registrations into a Pi session. Define the bounded execution contract
before completing that wiring.

The formal terminal client remains an undelivered product surface, explicitly
deferred by the 2026-10-01 decision. Its interaction design and framework
evaluation must precede implementation; do not style the frozen reference TUI.

M6 implemented Case execution and closed Tasks1–9 for lightweight demo scope.
Task1–8 independent review/fix records exist; Task9 records four boundary checks.
Later M10 and M11 passed full release gates. The remaining issue is consolidating
portable whole-stage review evidence, not unimplemented Case execution or an
absence of later gate runs. M10 likewise has a manual boundary review and explicit
closure but no separate versioned independent report found by this audit.
See the [M1–M11 status audit](../../reviews/2026-10-07-capstone-m1-m11-status-audit.md).

Conversational control resolution, capability-parity reference runs, live
grid-to-Thread interaction, real DSH, WebSocket human-in-the-loop controls and
multi-Run execution remain proposals or expressly deferred scope. Keep their
status separate from approved, incomplete delivery; do not start them implicitly.

## Global constraints

- Keep `Application -> Domain Pack -> Kernel -> registered Authority` ownership.
- No automatic/compact/full mode selector, future-answer preference, or new summary projection.
- No additional Provider calls. Fold the displayed Markdown height without changing its content.
- New and short answers remain fully visible. Completed long answers support folding and unfolding.
- Copy always uses the complete committed answer. Failed/cancelled/interrupted messages retain their full status and recovery text.
- Folded message IDs are scoped to the live Thread view and survive events/window navigation, but not refresh or Thread switches. Operations cannot submit a command, create an Attempt, change model selection, or clear the Composer draft.
- Preserve existing local state and user data. Local source changes require `make capstone-local-rebuild` before remote validation.
- Each cloud-dev/demo deployment must receive its own pushed acceptance tag after its required checks pass.

## CONV-01 implementation

### Task 1: Remove superseded summary and preference work

**Files:** `packages/capstone-agent/src/capstone_agent/harness.py`, `tests/test_harness.py`, and task-owned untracked summary/preference helpers and tests.

- [x] Remove only this task's uncommitted `answer_summary` addition and its tests. Preserve other Harness behavior and user work.
- [x] Remove `threadReadingMode.ts` and its tests; stop reading old preference keys or summary events. Keep final committed-answer replacement.
- [x] Verify backend tracked files match their pre-task source and that no App imports reference removed helpers.

### Task 2: History actions and bidirectional per-answer folding

**Files:**
- Modify `packages/capstone-app/src/CapstoneAssistantThread.tsx`, its tests, and `styles-light.css`.

**Interface:** `ReadonlySet<string>` of folded message IDs in the current live Thread. A bulk fold adds only completed IDs from the current `allMessages` snapshot; unfold removes those IDs. Neither operation installs a future-message rule.

- [x] Write failing tests for default full display, footer placement, history snapshot, later answers, pending-to-completed answers, individual bidirectional toggles, ignored old preferences, short/error visibility, full copy and draft preservation.
- [x] Add footer button `历史回答` with two explicit actions. Close it after selection, outside click, or Escape; restore keyboard focus after Escape.
- [x] Add a measured answer body, clipped to three text lines only when folded. Measure natural rendered height so short answers need no control; keep hidden links out of keyboard navigation. Add `aria-expanded` and `aria-controls` to the single-message toggle.
- [x] Keep folded IDs in the parent so new events and message-window remounts do not erase them. Reset on Thread switch or refresh; do not write preference storage.
- [x] Preserve the visible scroll anchor during resize operations and retain draft/copy/status/result/evidence behavior.

Run:
```sh
npm --prefix packages/capstone-app test -- src/CapstoneAssistantThread.test.tsx src/ThreadFixtureApp.test.tsx
npm --prefix packages/capstone-app run build
```

### Task 3: Local integration and review

- [x] Run all App tests, package boundary checks, `make doctor`, document links/symlink checks and `git diff --check`. Backend changes were removed; no backend behavior remains to test for this package.
- [x] Run `make capstone-local-rebuild`; record readiness and shared backend identity.
- [x] Use a task-owned headless browser fixture to verify bulk history, bidirectional per-message folding, new/pending messages, scroll stability, full copy, draft recovery, keyboard focus and desktop/mobile layout; message-window behavior is covered by App tests. Do not invoke a Provider just to obtain sample text.
- [ ] Review the change, fix material findings, commit task-owned implementation/plan paths, journal results and update the recovery baton.
- [ ] Close CONV-01 only with evidence. Continue to the dependency-ready package while the user's continuation instruction remains active. Remote release remains governed by local-first verification and stage acceptance tags.

## Follow-up: folded state, instruction focus and useful settings

User directs a subtle folded state, top/bottom controls anchored to the user
instruction, and integration into the existing Settings entry. Implement inline
using the writing-plans and test-driven-development workflows.

**Files:** `CapstoneAssistantThread.tsx`, `ThreadControls.tsx`, `ThreadFixtureApp.tsx`,
`styles-light.css`, their App tests, and new `ThreadSettingsMenu.tsx`.

- [x] Write failing tests for one Settings entry, meaningful default options, unchanged Profile dispatch under Advanced, folded state, two full-answer controls, and instruction focus including window boundaries.
- [x] Extract a shared Settings popover. Pass history actions through the Composer controls render callback so the real App and isolated Thread use the same entry. Remove the independent history trigger and fixed routing/global trace options; keep per-answer runtime actions.
- [x] Move Profile selection under Advanced as professional-function configuration, explain its effect, hide IDs/versions and disable no-change submission. Preserve existing availability and backend selection contracts.
- [x] Associate each answer with its accepted user instruction using Attempt/Turn metadata. Toggle and bulk operations restore that instruction, adjust the loaded message window when needed, and transfer focus after layout. Missing instructions fall back to the answer, never a guessed question.
- [x] Add subtle folded-state styles, top/bottom close controls, keyboard focus and reduced-motion handling. Verify the full clipboard, draft and evidence behavior.
- [x] Run full App tests/build, doctor/package boundaries, local rebuild, link/symlink/diff checks, and headless actual-App desktop/mobile tests with instruction pairs, long answers, top/bottom transitions and Settings/Advanced interactions.
- [ ] Record local verification, request independent review, commit owned paths and refresh the active recovery checkpoint; remote release remains separate.

Run:
```sh
npm --prefix packages/capstone-app test
npm --prefix packages/capstone-app run build
make doctor check-package-boundaries
make capstone-local-rebuild
git diff --check
```

## Follow-up: system notices in conversation

User approves moving command errors and operation outcomes into the message
area, while keeping lightweight connection state and local UI feedback.
Use writing-plans and test-driven-development inline; no backend contract change.

- [x] Write failing App tests for inline notices, command rejection with retained draft, one connection entry, terminal-error deduplication and notice ordering.
- [x] Add a bounded client notice projection with stable IDs and event-position anchors. Keep notices separate from answers, evidence, commands and model prompts. Project durable model/selection events from the existing ledger.
- [x] Render quiet system rows with recovery controls; move App banners into them. Keep UI-only feedback at the model pane. Preserve existing failure retry and diagnostic details.
- [x] Run App tests/build, local rebuild, doctor/boundaries and headless desktop/mobile checks; confirm history focus and drafts survive without Provider calls.
- [x] Record verification and review status, commit task-owned files and update the active checkpoint. Remote release remains separate.

## Execution record

- 2026-10-07: User approves system feedback in the message area. Quiet rows replace top banners; connection recovery updates one entry, rejected commands retain drafts, and Attempt errors keep partial answers without repeated error text. A diagnostic-only cursor regression was reproduced and fixed so recovery remains reachable at the live edge. See [local verification](../../reviews/2026-10-07-thread-system-notices-local-verification.md). Independent reviewer dispatch remains unavailable; no remote release.

- 2026-10-07: User clarifies that manual tool-group selection is necessary; the advanced assessment concerns a full unified grid-model system for multi-tool operation, not pairwise conversion. User explicitly defers implementation. Record the assessment in the evolution notebook; do not add a current work package, start adapters or make unified modeling a prerequisite for conversation/UI completion. Existing family compatibility remains enforced.

- 2026-10-07: User defines the public grid meaning: one ApplicationProfile represents one set of grid calculation and analysis tools. Larger tool systems split into multiple Domain Packs under the same Profile. Keep Pack composition internal and manage model identity separately from tool enablement. This clarifies §5.4; it does not claim the compact selector or zero-tool runtime is implemented.

- 2026-10-07: User corrects the proposed removal of Profile selection and the misleading “应用” label. The public concept is “电网计算分析工具”; enabling/disabling compatible tool groups is meaningful. Retract the uncommitted UI removal and retain verified 7b6524e source while correcting §5.4. All-disabled selection preserves the model but must stop tool-dependent calculations; the current empty-selection session failure/rollback is an implementation gap, not a reason to remove user choice. Next implementation must simplify the small control, use business tool-group names, make compatibility clear and verify zero-tool behavior. No remote release.

- 2026-10-07: User requests distinctive folded states, instruction anchors and useful unified Settings. App293 tests/build and desktop/mobile/landscape/reduced-motion browser checks pass; a runtime bottom-follow race and message-window focus timing were reproduced and fixed. Profile purpose was explained; selection remains behind Advanced with unchanged backend contracts. See [local verification](../../reviews/2026-10-07-thread-settings-and-instruction-focus-local-verification.md). Independent review dispatch is still unavailable; no remote release.

- 2026-10-07: User rejects the two-purpose global mode and approves one-time history actions plus per-message folding. Revised §5.3 supersedes the earlier mode/summary implementation and acceptance. Re-test the new interaction; remove task-owned backend summary work.
- 2026-10-07: Revised implementation passes App290 tests/build and headless desktop/mobile checks. A browser-found scroll-offset issue was fixed and re-tested, including collapse from inside a long answer. Backend source returns to its pre-task state. See [local verification](../../reviews/2026-10-07-thread-history-folding-local-verification.md). Independent review dispatch remains unavailable; no remote release or new tag.

- 2026-10-07: User corrects delivery direction. Core evolution research is secondary; continue existing conversation plans.
- 2026-10-07: Source audit finds Web §5.3 modes absent. Legacy answer bundles do not provide a Thread summary projection. CONV-01 starts with the existing approved display contract.
- 2026-10-07: CONV-01/02 local implementation passes App289 tests/build, backend550 tests with35 skips, package boundaries and doctor. Local rebuild readiness and API/worker digest039ddb77e1f1 match. Isolated headless browser checks pass modes, per-answer expansion, event preservation, full copy, draft/reload, all five evidence states and390px keyboard/44px control target. Screenshots/log: `output/playwright/conversation-completion-20261007/`. No Provider or remote deployment. Independent review dispatch is unavailable because the platform selects unsupported model `gpt-6.1-luna`; review and release are not marked complete.
- 2026-10-07: User requests major unfinished items. The next major delivery is CONV-04; CONV-05 is incomplete existing M2 execution wiring, formal TUI is explicitly deferred, and M6 retains full acceptance gaps. Stop expanding UI detail scope.
- 2026-10-07: Correction after M1–M11 evidence audit: M6 Task1–8 independent follow-ups passed and Task9 closed for lightweight demo scope; subsequent M10/M11 full gates passed. M6/M10 need portable whole-stage review-record consolidation, not automatic reopening. M2 intentionally deferred native capability materialization to successor Harness work. Preserve these bounded milestone closures.
