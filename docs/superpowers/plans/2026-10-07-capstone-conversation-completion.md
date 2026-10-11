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

### Current execution ownership — 2026-10-11

This section supersedes earlier active-priority and direct-integration wording;
older implementation and verification entries remain historical evidence.

- Foundation PR #6 is merged on main c3b78bc and accepted on local-dev. Its
  development branch is closed. local-demo follows cloud-demo ed2524f; foundation
  user-release acceptance is still pending, not a daily dual-deployment task.
- The active delivery is semantic task understanding, goal/scenario coverage and
  formal answers, one package on feat/task-answer-closure under the
  [shared design](../specs/2026-10-10-shared-intent-and-goal-answer-design.md).
  Preparation402ac39 does not implement the complete answer closure.
  The current reviewed source is2473e48: local-dev rebuilt, registered cases,
  reports, evidence replay and formal transport separation passed. PR #9 awaits
  its last exact CI check and integration; human wording acceptance is pending.
  Contract-only checks did not prove completion; the later local report supplies
  execution evidence. The old branch checkpoint below is historical.
  The user approved implementation on 2026-10-11; execute the
  [task-answer plan](2026-10-11-task-answer-closure.md). Initial contract tests
  pass; semantic execution, Pack coverage and product acceptance remain open.
- CONV-04/05 experimental Pi, skills and role resources continue on
  feat/pi-skills-integration under the [resource plan](2026-10-09-business-workspace-agent-resources.md).
  That plan's Tasks8–9 own full task-relevant business context, current-model
  projections, authorized sharing and real business-input acceptance. Routing
  does not replace task understanding. Unified frontend commands remain a
  separate design package; Pi slash controls are reuse prototypes.
- The control graph is a bidirectional execution view. Changes in scope, owner,
  priority or acceptance update this worklist and owning plans/specs; implementation,
  PR and deployment facts update the same graph. Neither direction may be omitted.

### Current priority and release correction — 2026-10-08

Superseded delivery boundary — 2026-10-09: the user approved one native general
Pi executor with delegated and direct entry points. Ordinary/mixed Capstone and
direct Pi implementation now proceed together under the
[joint plan](2026-10-09-capstone-pi-delegation.md). Actual response acceptance
remains separate for each entry point; skills/MCP installation management follows.
The previous empty-tool Pi path does not establish general task delegation.

Ordinary Capstone conversation, including an empty enabled-tool selection, is
the active package. The user directs cleanup, ordinary-answer support and actual
Capstone response assessment first, then pure Pi comparison, then installation
and configuration design for skills, MCP and related capabilities. Local fixture
and transport checks do not complete response-quality acceptance. Do not advance
to CONV-04 until Capstone ordinary-answer behavior has been assessed and accepted.
Earlier priority and pending-release statements below
are historical. CONV-01/02/06 implementations shipped in verified source
`ed2524f` to cloud-dev and demo; independent review and dedicated full interaction
acceptance remain open. See the indexed stage acceptance receipts. No release,
Provider validation, resource removal, or user-data cleanup remains from that task.

### Ordinary conversation implementation

The approved baseline §5.1 and empty-capability decisions govern this work.
Keep the Capstone gateway, immutable Attempt, current model, selection revision,
history, cancellation and replay. This is not CONV-04 reference mode.

- [x] Add failing regression coverage for empty-selection Pi construction:
  application policy and model identity, no Domain Pack extension or built-in
  tools, no result/evidence references, and rejection of unowned tool activity.
- [x] In `kernel_pi_session.py`, accept an application-owned workspace root for
  zero-contribution sessions. Compose the generic policy without domain policy
  or prior result handles, and use the existing bounded Pi launch/RPC lifecycle.
  Pass the same stage workspace root from both registered hosted adapters.
- [x] Replace the App's blanket no-tool message guard with exact empty selection
  dispatch. Preserve catalog-unavailable errors, draft recovery, model controls,
  and scripted-case tool requirements. Cover sending after all tools are disabled.
- [x] Verify professional requests cannot produce unadmitted claims or evidence;
  run focused backend/App tests, full App tests/build, type/boundary checks,
  doctor and current-source local rebuild. Verify the actual local entry point.
- [x] Record evidence and limits, journal durable outcomes, and checkpoint.
  Provider tests require separate explicit authorization; no remote release is
  part of this package unless separately requested.

### Ordinary-answer behavior acceptance — active

The governing design is now [conversation continuity and request context](../specs/2026-10-08-capstone-conversation-context-design.md).
User-approved direction: shared history, Pi-native configuration, semantic request
understanding, and selective resource loading. Keyword routing and keyword fallback
are explicitly rejected. The two-stage design is now approved, with an independent
intent node implemented first through Pi and later replaceable by Jev or a dedicated
small model. Follow the [implementation plan](2026-10-08-capstone-intent-context.md).
The earlier separate-ordinary-memory instruction below is superseded:
ordinary and business replies share conversation continuity, while execution
resources and evidence retain their own boundaries.

- User clarification: Pi processes all instructions. Entering Pi is not evidence
  that ordinary answers are supported. Acceptance requires explicit ordinary vs
  business intent recognition and route-specific context preparation before Pi.
- The news-question trace selected `ordinary`, but session preparation still
  combined general conversation policy with the grid-agent role and business
  ModelContext. The new semantic path fixes that context preparation defect;
  real response-quality acceptance remains open. See the [local verification](../../reviews/2026-10-08-intent-context-local-verification.md).
- [x] Give ordinary requests a dedicated Pi context without business role,
  model-analysis constraints, domain tools or Authority result handles. Provide
  bounded catalog metadata only when the request asks about available features.
  Preserve business model and selection in the ledger, outside ordinary prompts.
- [x] Test classification contracts and actual Pi context composition with tools both on
  and off. Preserve shared ordinary/business dialogue, distinguish historical text
  from admitted facts, and clarify ambiguous intent through Pi semantics.
- [ ] Assess real Capstone replies through the local App/API, after explicit
  authorization for billed Provider calls or through user-operated App trials.
- [ ] Cover greeting, general questions, grid concept explanation, available-tool
  questions, and a follow-up referring to the previous answer.
- [ ] With calculation tools disabled, confirm requested numerical analysis gives
  a clear capability prompt, preserves the model, and creates no evidence.
- [ ] Check streaming, cancellation, recovery and replay; record the actual text
  and distinguish response quality from transport or fixture success.
- [ ] Fix observed failures and obtain user acceptance of Capstone behavior before
  starting pure Pi comparison. Skills/MCP installation and configuration design
  follows that comparison; existing CONV-05 wiring does not substitute for design.

| Package | Status | Scope | Depends on | Acceptance |
| --- | --- | --- | --- | --- |
| Ordinary conversation | local acceptance complete; real Provider and remote acceptance not tested | Capstone ordinary exchange with empty calculation-tool selection | Approved baseline §5.1 and empty-capability decisions | Application-only Pi RPC, exact selection, zero-evidence replies, capability prompt before Provider construction, current-source rebuild and full offline gates; [receipt](../../reviews/2026-10-08-ordinary-conversation-local-verification.md) |
| CONV-01 | deployed and stage-verified; independent review and full interaction acceptance pending | One-time history folding and per-answer bidirectional toggles | Revised Web contract §5.3 | Existing completed answers only; future answers remain full; short/error/running messages remain visible; full copy, stable scroll/draft; local rebuild and browser checks |
| CONV-02 | deployed and stage-verified; dedicated interaction acceptance pending | Contract audit and completion of evidence-state/action feedback | Existing admitted public projections | Distinguish available/not_applicable/missing/pending/unavailable without inventing references; keyboard and touch interaction |
| CONV-03 | audit complete; record consolidation pending | Reconcile bounded M1–M11 closures and deferred successor work | Existing implementation and review evidence | Preserve M6 lightweight closure and later full gates; consolidate portable M6/M10 review records without reopening completed functionality |
| CONV-04 | needs design review | Accepted pure Pi reference path and context isolation | Conversation completion audit | Separate bounded gateway path and explicit non-authoritative output; exact comparison scope and implementation plan before code |
| CONV-05 | explicitly deferred adapter work; execution integration incomplete | Generic registered runtime capabilities | M2 review's successor requirement and mainline baseline §4.1 | Compile selected verified skill/MCP/plugin registrations into the runtime session and manage lifecycle; preserve domain-tool and authority boundaries; do not reopen M2 |
| CONV-06 | deployed and stage-verified; independent review and full interaction acceptance pending | Persistent opened grid models, one current model, saved per-model work, compact model control and close lifecycle | User request and approval of 2026-10-08; existing Authority model references and immutable Attempt contract | Default IEEE-39; nonempty durable collection; exact-reference activation; saved Context/results/source view and camera restoration; atomic close/fallback; draft/recovery preservation; no Provider call for model controls |
| Final TUI / real DSH / multi-Run | deferred in existing decisions | Separate client/runtime designs | Applicable design decisions | Do not mark as complete; do not undo the accepted TUI freeze or M6/M11 exclusions |

Status is based on implementation and evidence, not checkbox counts alone. Add newly found contract gaps to the owning package. Do not use the deployed Web version as proof that the complete conversation design is finished.

CONV-06 model management is deployed. Its design and implementation records follow. See the [opened-model design draft](../specs/2026-10-08-thread-open-models-design.md).
The approved [model work resume revision](../specs/2026-10-08-thread-model-work-resume-design.md)
supersedes fresh Context creation on every activation. Its [local acceptance](../../reviews/2026-10-08-thread-model-work-resume-local-verification.md)
covers stable members, saved Context continuity and view restoration; independent review and dedicated full interaction acceptance remain pending.
User approved the design and historical topology retention; follow the
[implementation plan](2026-10-08-thread-open-models.md) inline.
Local implementation and acceptance are recorded in the
[verification report](../../reviews/2026-10-08-thread-opened-models-local-verification.md).
It is separate from CONV-04's pure Pi reference path. A parser-only fix or a
menu over historical pages cannot close this package. The prior UI corrections
are deployed and stage-verified, with independent review and dedicated interaction acceptance still pending.

## Priority correction and major gaps

The user asks for major unfinished work and questions further UI-detail changes.
Do not expand Web styling or polish. Finish verification of the current small
changes, then deliver ordinary conversation with an empty selection before
CONV-04, the accepted runtime comparison/isolation contract. `HarnessPiClient.runtime_mode` and the runtime registry are partial
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

## Follow-up: compact grid-tool settings

The screenshot still shows the rejected nested Settings design. Apply approved
Web §5.4 inline with writing-plans and test-driven-development. This is a
presentation fix; the zero-tool runtime remains a separately tracked gap.

- [x] Revise `ThreadFixtureApp.test.tsx` to require directly visible grid-tool names, no Advanced or professional-configuration layer, and Save only after a changed selection. Add `ThreadControls.test.tsx` for multi-group selection, family filtering, pending controls and explicit unsupported empty selection.
- [x] Simplify `ThreadControls.tsx` to flat compatible tool rows. Use public grid names for known registered profiles. Keep exact Profile references and the existing replace-selection command. Show a small Save only for changes; block unsupported all-off submission with a short reason.
- [x] Compact `HistoryAnswerActions` and `styles-light.css`: one-line scope hint, no bordered option cards, no nested sections. Check 375px and landscape popovers, keyboard closing and retained drafts in headless Playwright.
- [x] Run App tests/build, doctor/boundaries, current-source local rebuild and document checks. Write a verification report, commit owned paths and checkpoint. Do not claim zero-tool runtime, independent review or cloud release.

## Follow-up: stable answer toggle

The user supersedes forced instruction navigation: collapse and expand should
use the same position, minimize screen movement and retain focus. Apply revised
Web §5.3 inline; no backend, answer content or evidence changes.

- [x] Revise `CapstoneAssistantThread.test.tsx` to require a single persistent toggle, retained button focus and no forced message-window navigation. Keep folding/copy/draft coverage.
- [x] In `FoldableAnswer`, retain one fixed-width sticky toggle in both states. In the reading context, capture its element and viewport position, pause bottom-follow and restore after resize; preserve visible message position for bulk actions without stealing Settings focus.
- [x] Verify real long answers at top, middle and end with consecutive mouse/keyboard collapse/expand on desktop/mobile/landscape, including scroll bounds and bulk actions. Require stable toggle coordinates when feasible and identical focus.
- [x] Run App tests/build, doctor, local rebuild and document checks; report measured limits, commit and checkpoint. Keep unsupported all-off runtime and remote release pending.

## Execution record

### Follow-up: global tool preferences

Tool enablement is an application-wide preference, independent of the open model.
All registered tools are enabled by default. A model switch must preserve user
choices. Execution still uses compatible registered tools; this grants no model
conversion. Configuration persistence and reload remain a future extension as
the tool catalog grows.

- [x] Separate global preferences from the current model's effective selection; remove model-family disabling of Settings switches.
- [x] Apply the compatible enabled subset before execution and preserve choices across model/conversation switches. Cover empty effective selections explicitly.
- [x] Verify App/runtime behavior, rebuild the current checkout and record exact completion limits.

Local delivery: global preferences now default all registered tools on, remain
independent of the selected model and survive conversation changes within the
mounted App. Every Web task binds the exact compatible enabled subset in the
message transaction, including after model activation. Empty global preferences
can be saved, but the existing zero-Pack runtime is still incomplete: ordinary
messages and model switches with no compatible enabled tools are blocked before
submission with retained drafts. Persistent configuration/reload remains future
scope. See [verification](../../reviews/2026-10-08-thread-global-tools-local-verification.md).

### Follow-up: plain folded answers and visible instructions

The user removes folded backgrounds and redundant state text, and requires
the complete associated instruction to be visible after toggling long answers.
Preserve the same control focus, using only the scroll needed for context.

- [x] Revise App tests for no “已折叠” label and revealing a loaded instruction outside the message window with control focus retained.
- [x] Remove the folded surface color/state label; extend stable reading anchors to ensure the exact instruction is fully within the viewport. Reveal it if loaded outside the current window; never choose an unrelated instruction.
- [x] Verify long/wrapped instructions and very long answers on desktop/mobile, both toggle directions, scroll bounds, draft/copy and missing-instruction fallback. Run App tests/build, rebuild, doctor and document checks; commit owned changes and checkpoint.

### Follow-up: distinct system notices and consecutive history actions

The user requests a quiet visual distinction between system notices and folded
answers, and a stable reading subject during repeated global fold/unfold actions.

- [x] Reproduce the global anchor defect in a real headless component: the current instruction moves up to 2,201px because the preceding long answer is anchored. Add a failing geometry regression, then retain the visible instruction and Settings focus across repeated actions.
- [x] Remove the notice's answer-like left rail and full green surface; use an inset neutral notice, small label/icon and horizontal separator. Retain alert/status roles and recovery actions.
- [x] Verify repeated actions at start/middle/end on desktop/mobile/landscape, explicit user scrolling, hidden-instruction fallback and existing per-answer behavior; run App gates and local rebuild. Record [local acceptance](../../reviews/2026-10-08-thread-notice-and-global-anchor-local-verification.md) and commit only owned paths.

### Follow-up: answer icon beside the role label

The user replaces the full-width answer-toggle row with a small icon next to
CAPSTONE and a hover hint. Keep the same control, keyboard access and instruction
visibility, with no extra row between the role label and answer.

- [x] Extend the persistent-control regression for an icon-only header control and both hover hints; reproduce failure before implementation.
- [x] Verify compact header geometry, desktop/mobile touch targets, long-answer instruction visibility and repeated global anchors. Run App gates and local rebuild; record [local acceptance](../../reviews/2026-10-08-thread-answer-header-icon-local-verification.md) and commit owned paths.

### Follow-up: registered-tool visibility and compact history menu

User rejects hiding PyPSA and the history-menu heading/hint rows. Apply these corrections inline
to the existing approved UI contract; do not implement cross-family conversion.

- [x] Show every registered catalog tool group in `ThreadControls`, with disabled incompatible rows and a short visible model-family reason; preserve exact compatible selection dispatch.
- [x] Remove the redundant “历史回答” heading and scope hint from `HistoryAnswerActions`; retain only the two named history actions and their scope semantics. Preserve the verified stable answer toggle and focus behavior.
- [x] Run focused red/green tests, full App tests/build, local rebuild, doctor and headless real-component desktop/mobile checks. Record scope, commit owned changes and checkpoint; no cloud deployment.

- 2026-10-08: User screenshot identifies two missed requirements. Settings now shows all registered tool groups with visible compatibility reasons instead of hiding PyPSA. History controls retain only the two actions; redundant first/last text rows are removed. App298/build, rebuild and headless desktop/mobile/landscape checks pass. See [local verification](../../reviews/2026-10-08-thread-tool-menu-local-verification.md). Answer folding itself retains the verified stable-toggle behavior.

- 2026-10-07: User supersedes forced instruction navigation with same-position folding controls and retained focus. One sticky toggle persists across both states; regular desktop/mobile/landscape cases move 0–0.44px. A last-answer boundary jump of about 465px was reproduced, then removed with only the required reading tail space; the corrected case moves 0px and expansion clears the space. Bulk Settings focus and drafts survive. See [local verification](../../reviews/2026-10-07-thread-stable-answer-toggle-local-verification.md). Earlier top/bottom-to-instruction receipts describe the superseded interaction.

- 2026-10-07: User screenshot disproves the claimed Settings completion: nested Advanced/professional configuration and old names remained. Flat grid-tool rows now replace them; Save appears only for a changed selection, and unsupported empty submission is blocked with a short reason. App298/build, rebuild and headless desktop/375px/landscape checks pass. See [local verification](../../reviews/2026-10-07-thread-compact-grid-settings-local-verification.md). This closes the compact UI fix, not the zero-tool runtime or cloud release.

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

## 2026-10-11 Research Model 工作包推进

research独立实验进入R0已验证、R1待实施阶段。采用[研究模型演进计划](2026-10-11-research-model-evolution.md)作为R1–R5执行清单；当前正式回答包继续独立收口，不将实验混入local-dev候选。Research Model按任务跨轮次延续，知识包、可组合工作流和结论验证共同支撑自主推演。

2026-10-11开发组织调整：用户批准dev默认开发集成主线、main发布基线主线。
PR #9/#10已合入main723b8e8；dev从该点建立，PR #11文档与治理改为面向dev。
先按[dev组织实施计划](2026-10-11-dev-integration.md)完成保护、CI、工具与全局记录集成，
再登记精确2473e48本地技术基线并从已接受dev建立Research Model实施分支。
实验R0和Pi保持独立；人工回答验收、CLI退出迁移、Issue验收与云发布仍分别记录。

最新顺序：先同步项目文档和控制记录，再完成正式回答PR #9及新技术基线；CI调整PR #10保持独立。随后从新基线开启Research Model实施分支。旧CLI兼容要求已撤销，运行入口迁移按[退出计划](2026-10-11-retire-grid-cli.md)单独核验，不能以删除兼容测试冒充迁移完成。

## 2026-10-12 当前阻断包：轻量路由与本地回答回归

当前源码1013dd2已规范重建，515项三角色/镜像329ae580及App同源。
fb6a921整体10/12失败：两条概况请求重复拆成多个专业契约或普通业务场景，
原AC→复用已通过。新修复在接受前核对组合候选，独立普通目标仅走无工具
会话，宿主合并已验证专业信息；历史v2回放保持。207项检查与复审通过，
真实整体9案例12轮4b19beeaa3d349c6及专项3轮独立PASS，浏览器通过，待人工。
复杂业务几十秒至分钟属正常范围，记录阶段耗时，不凭总时长判失败。
依赖型一般任务交接和需要专业执行的混合隔离保持开放，不以本轮修复认证。
整体与专项分别出结论；专项从同一真实整体收据选出三个修复轮次，保留
来源哈希，避免重复收费执行。以下早期候选状态均为历史。

当前候选b5fcc63恢复既有指南中未指定命名空间的Authority名称/别名查证路径，typed契约以user_label保留标号；禁止数字回退索引，真实缺失/歧义仍澄清。规范重建515项三角色/App同源；原始负荷指令和AC→复用三轮专项dccbeb158aea4086独立证据/工具/浏览器验收PASS。整体9案例12轮正在复验；负荷98.252秒、AC38.003秒、复用22.082秒主要耗在后续执行，性能仍开放。以下a4ea668整体失败和早期收据保留为历史，不覆盖当前专项结果。

人工回归更新：潮流执行完整报告被typed正式结论摘要替换；明确沿用已有潮流列出前三条线路在编译/解析阶段被错误澄清。两项均为已有功能回归。先对照2473e48前后的回答准入及已有prior_results读取链路，恢复通用行为与精确目标/证据检查；不新增样例专用系统提示。整体样本扩为9案例12轮，原范围通过不能认证本次回归。新业务基线继续阻断。

a4ea668已规范重建，完整回答与复用原始两轮专项经Authority/工具/浏览器独立验收PASS；复用仅4次读取/排序、零重算。整体9案例12轮11/12，负荷标识namespace在编译时被提前澄清，未进入Authority查询，整体FAIL。保持专项修复完成与整体阻断分别登记；不改样本为通过，不任意扩展领域包标识政策或添加个例提示。下一收口项是通用对象引用解析/编译边界，仍不得建立新基线或进入R1。见[实际验收报告](../../reviews/2026-10-12-answer-and-result-reuse.md)。

PR #9/#10已集成；后续真实对话暴露回归，当前先按[识别与耗时计划](2026-10-11-recognition-latency.md)收口PR #13，不进入Research R1。用户明确：意图识别只做轻量LLM普通/专业路由，领域要求编译与契约校验移到路由后的链条；复杂发电N−1样本当前仅验路由，研究完成留给Research Model。完整打开模型时预热已实现；a634257将首次创建、新模型打开及切换绑定收敛到同一应用初始化实现。新源码需规范重建、真实支持业务样本、逐阶段耗时及浏览器验证通过，才能交人工；发布、合并和研究完成均不得由路由通过替代。

beef6d4历史验收完成local-dev同源重建、9业务＋1路由范围验收、独立证据复核及等待/窗口实测；[验收记录](../../reviews/2026-10-12-lightweight-routing-local-verification.md)保留逐轮耗时与负荷81.747秒执行限制。新候选按[模型打开准备报告](../../reviews/2026-10-12-model-opening-preparation.md)记录。9843b04整体失败2轮，8ec1e1a整体9业务＋1路由独立核对通过；保留前者原始收据和业务身份/结论覆盖风险，不将后者通过解释为根因关闭。统一入口a634257已完成同源重建与真实专项复测。PR13仍草稿，Issues2/3仍打开；随后按范围推进dev集成，研究后置。
