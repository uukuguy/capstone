# Conversation intervention and Mission entry

Status: direction and right-panel placement accepted by the user; implementation pending.
Owners: capstone-app, capstone-agent, capstone-harness, capstone-control.
Destination: dev through a scoped implementation PR. No runtime change in this draft.

## Accepted boundaries

- Reuse the existing main conversation, composer, message history and product readers.
- `/goal` assigns a goal to one responsible Agent, which may later delegate internally.
- `/mission` creates a Mission managed by capstone-control (Mission Control).
  MissionController organizes Goals and overall delivery. Multiple Agents are supported,
  not mandatory. Existing Control Goal records retain identity during migration.
- Mission creation accepts rough intent without a complete task list. Each dispatched
  task still needs an executable objective, grants, bounded budget and return contract.
- Task equipment is selected from registered, authorized capabilities. Defaults allow
  work to start without a configuration form. Users can adjust conditions in dialogue.
  Recommendations may evolve; explicit restrictions cannot be silently relaxed.
- No mode icon or modal creation form. Slash commands are the explicit entry.

## Composer status strip

Replace the divider immediately above the existing composer with a stable, single-row
status strip. Keep its height stable while execution changes; do not move the composer
or reset conversation scroll. Preserve existing theme, typography and icon family.

Left: a small status symbol and one short label. Use `执行中`, `待你回复`, `正在停止`
or `已停止`. Idle has no unnecessary status sentence. A Goal or Mission indicator may
appear only when associated with the current conversation, with details on demand.

Right: a pending-instruction control with count, and a separate stop button when an
execution can be stopped. Sending remains in the existing composer, always in the
same position. It never becomes the stop button. Stopping is not represented by a
pause icon. Do not add a pause action until its semantics are implemented.

Use flat SVG icons, approximately 16–18 px, with consistent stroke weight. Hit targets
are at least 44 px; visual icons remain compact. Icon buttons have accessible names,
keyboard focus and tooltips available on focus as well as hover. Status has short text
as well as color. Respect reduced motion; avoid continuous decorative animation.

Suggested symbols: square for stop, stacked lines for pending instructions, chevron
for disclosure. `立即介入` retains a short text label in the expanded queue because
an unfamiliar icon alone cannot communicate its effect.

The queue expands inline above the strip, not in a modal. Show pending text previews
and actions without replacing messages or the composer. Collapse by default; bounded
height prevents a long queue from consuming the conversation. Narrow screens preserve
status, queue count and stop, with secondary details in disclosure.

## Submission and intervention semantics

Typing remains available during execution. Sending persists a distinct instruction
with stable identity and order. Display `待接纳` only after durable acknowledgement;
uncertain submission retains the same retry identity. A network failure preserves draft.
Refresh and reconnect restore the queue from the server, not local component state.

Default submission does not cancel the current execution. Harness checks queued
instructions at safe boundaries and admits them before the next model/tool step.
The admission point records exactly which instructions entered the Agent context.
`已接纳` means included in execution context, not fulfilled.

Pending instructions may be withdrawn. Withdrawal racing admission has one atomic
outcome; never report withdrawal after execution has admitted the instruction.
An `立即介入` action requests cancellation of the current cancellable step and admission
of pending instructions in order. It cannot undo completed side effects. For a tool
that cannot safely stop, show `等待当前操作结束`. Preserve all prior execution records.
Keyboard shortcut selection is deferred until existing composer and browser shortcuts
are audited; the visible action works without a shortcut.

Stop requests cancellation of the current execution and suspends further automatic
admission in that execution. Pending instructions remain visible and durable; they do
not silently restart stopped work. Explicit continuation resumes their processing.
Fence stale workers and make acknowledgement, retries and cancellation idempotent.

The main message history keeps original user text and concise admission/redirect
receipts. Detailed tool events stay in the existing process reader. Do not duplicate
user messages when a pending instruction becomes admitted. Background polling must
not reset focus, draft, selected products or navigation.

## Persistent right-panel readers

Reuse the existing right resource panel with two primary views: `执行详情`
and `制品`. Execution details combines the existing process reader and full answer
in one view, in that order. Preserve existing model/source and delivery views where
applicable. This is not a new modal or a second conversation implementation.

Move the existing execution process reader into `执行详情`, retaining tool details,
folds, durations, recorded results and diagnostic links. It continuously displays
current work and permits history inspection. New instruction admission adds a
source-linked boundary; it does not clear earlier records. Select records by stable
Thread/Attempt/event identities, never by message-array position.

Keep the existing full answer renderer after the process reader in `执行详情`.
Select current or historical answers with their original instruction and execution
identity. New answers indicate updates without switching tabs or replacing an answer
the user is reading. Interrupted or redirected execution is not labelled completed
and does not require a fabricated final answer.

The conversation shows a short completion receipt at the end of an execution phase,
not a full answer under the original instruction bubble. It names what completed,
what remains or stopped, and links to the answer and products. Do not derive factual
completion claims by truncating arbitrary answer text. Initial layout migration may
use a neutral status receipt plus `查看回答`; semantic summaries require an admitted
execution result. Ordinary short conversational replies remain directly readable.
Long deliverables become products progressively; do not silently convert or delete
historical answers.

The right panel follows live execution until the user browses history. Then preserve
selection, folds and scroll, and show `回到当前`. Closing/reopening the panel and
switching tabs retain reading state. Mainline links locate the exact right-panel
record; records link back to the source instruction. Missing or inaccessible sources
show an unavailable state instead of falling back to a different execution.

Narrow screens reuse existing resource-pane navigation and return behavior. Restoring
the conversation restores its draft and scroll. Avoid a new overlay stack.

## Implementation seam and migration order

`ThreadWorkAdapter.tsx` owns the existing resource views and their session-scoped
selection. Add the combined reader there; preserve existing product/source readers.
`CapstoneAssistantThread.tsx` currently owns `ChatMessage`, `AttemptActivity` and
`CompletedAnswer`. Reuse these rendering mechanisms with a shared execution-detail
projection. Avoid rendering a second assistant runtime or copying the tool-detail UI.
Keep original standalone/legacy rendering as fallback until its reader migration is
verified. The existing `onOpenAnswerDetail` closes the resource panel for native chat;
change this integration deliberately so opening details does not close its own host.

Today the process reader resets folds when `finishedAttempt` changes. The combined
reader must not apply this reset to historical records being inspected. Preserve
per-execution fold state separately from whether the right panel is visible.

Frontend migration acceptance comes before changing instruction admission: exact
source selection, existing process details, answer rendering, live/history following,
tab/close restoration, products and legacy history. Do not enable concurrent send
until durable server admission and harness boundaries pass their own acceptance.

## Scope and authority

Ordinary conversation intervention targets its active Agent execution. Mission mainline
instructions target the organization layer, which determines affected Goals. Never
broadcast automatically. A task-specific intervention must name its target visibly.
Deterministic grant/budget restrictions are enforced before subsequent affected actions;
semantic redirection is interpreted by the Agent. In-flight effects remain explicit.

## Delivery sequence and acceptance

1. Implement the durable instruction queue, boundary admission and receipts for one
   active Agent. Reuse existing Thread/Work ownership rather than a second task ledger.
2. Integrate the status strip, independent send/stop, queue disclosure and intervention,
   plus persistent execution/answer/product readers. Reader relocation is independently
   testable but does not establish concurrent instruction support.
3. Apply the accepted Mission naming/compatibility and mainline organization separately,
   using the same intervention mechanism. No claim that steps 1–2 implement Mission.

Focused checks must cover ordering, duplicate retry, admission/withdraw races, stop
with queued input, restart recovery, stale-worker fencing and cancellation limitations.
Real acceptance: start a tool task, submit a direction change while it runs, observe
its boundary receipt and changed next action, inspect saved products, refresh and
continue without lost/duplicated instructions. Verify existing legacy history remains
readable and cannot accidentally start execution.

Browser acceptance uses the existing Capstone tab and actual local entry after the
canonical rebuild. Check desktop/narrow layouts, keyboard/IME behavior, focus and scroll
stability, and persistent queue state. Fixtures alone do not establish real acceptance.

## Current implementation evidence

ThreadWorkAdapter currently renders pending command recovery, GoalControls and the
existing conversation input. These are integration points, not proof of safe concurrent
instruction admission. Control creation currently requires nonempty tasks and acceptance
criteria in `capstone_control/contracts.py`; intent-only Mission creation needs a new
compatible contract. The existing ControlHost tick is not a conversational planner.
