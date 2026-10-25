# Unified conversation and systematic diagnosis

Status: user approved on 2026-10-25, including the clarified task-chain policies.
Implementation is active; no runtime acceptance is claimed.

## Intent and owning contracts

Continue the unified execution work in
[the canonical plan](../plans/2026-10-16-enterprise-unified-execution.md).
The user requires three process priorities: direct answers focus on thinking;
general tool execution focuses on tool calls; enterprise research and grid
analysis focus on business task planning. These are process views within one
continuing conversation. They do not impose a permanent capability ceiling.

The product is a coding agent for enterprise work: it uses real business data
to perform real analysis and calculation. The user controls direction, judges
key outcomes and supplies information across turns. The agent handles detailed
data acquisition, task planning, computation, analysis and professional products.
Do not require the user to manage internal nodes or approve every tool call.

Preserve the [framework](../../architecture/capstone-framework.md),
[enterprise baseline](2026-10-15-enterprise-design-final.md), existing workspace,
conversation components, Thread ledger, Work binding and Authority admission.

## Current implementation findings

- `native_conversation.binding_for_session` and Thread submission still select
  execution bindings using session type. Unified presentation alone is insufficient.
- `CapstoneAssistantThread`, `TaskStepProcess`, `ExecutionGraphProcess` and
  `ProcessCallTrace` already provide reusable process views and replay inputs.
- `general-sdk.mjs` loads allowlisted skills for native parent and child sessions.
  It also stops repeated rejected graph selections without accepted progress.
  This guard is not a complete root-cause diagnosis workflow.
- `agent-resources.json` provides versioned role resource registration. Personal
  workstation skill paths cannot become a deployed runtime dependency.

## Options

1. Recommended: one organization mechanism, per-turn capability selection,
   evidence-based process views, and a shared diagnosis capability. This matches
   the accepted direction and supports mixed follow-up requests.
2. Presentation-only integration: cheaper initially, but session type would still
   constrain execution. It does not meet the unified-conversation requirement.
3. One mandatory business planner for every request: structurally uniform, but
   adds planning cost and artificial tasks to direct answers and simple tool use.

## Execution and process view

Application-owned selection resolves each instruction against enabled resources,
explicit grants and available model contexts. Session type may retain entry
defaults and historical identity; it must not be the sole execution authority.
Persist the accepted selection for retries. A later instruction may select a
different supported capability without creating a separate conversation.

| Actual execution | Primary process view | Expandable detail |
| --- | --- | --- |
| Direct LLM answer | Thinking state, duration, available public summary | Actual model request status |
| General tool work | Actual tool order, parallel calls, results and errors | Model requests and authorized tool details |
| Research or grid task | Business purpose, task dependencies, progress, revisions and outcomes | Associated model/tool calls, sources and admitted results |

Thinking denotes public provider events or summaries when available. Do not
invent reasoning text or infer thinking content from elapsed time. A provider
without a public summary has a status/timing view only.

Choose the view from accepted execution and recorded events, not keywords or the
session title. Support transitions and mixed work in one instruction. A business
task without a recorded plan must not display fabricated plan steps. Live and
replayed views must agree after refresh, continuation, failure and cancellation.
Reuse existing message, composer, fold state, products and source components.

## Different task-chain acceptance policies

The user clarified these requirements on 2026-10-25. They constrain the proposed
implementation; they are not claims about current runtime behavior.

| Concern | Enterprise research and analysis | Grid analysis and decision support |
| --- | --- | --- |
| Main alignment loop | Multiple user turns refine the question, interpretation and output | Multiple user turns guide the business goal; registered tools objectively check calculations |
| Instruction completion | Complete the feasible chain, record gaps and deliver useful work | Execute valid calculations and pass contract-valid results to dependent nodes |
| Quality-control node | Record findings and release by default; advisory failure does not force repair | Enforce applicable objective model, solver, unit, revision and result contracts |
| Retry | Allow justified retries without requiring a new hypothesis for every attempt | Allow bounded targeted diagnosis and correction when objective checks fail |
| Unresolved issue | Keep findings and limitations for user judgement and later revision | Mark invalid/unavailable calculations explicitly; block only dependent claims or actions |

Default release means that the quality-control node completes its record and
allows continuation. It does not mark a failed check as passed or invent missing
inputs. A truly missing required input can still block its dependent action.
Permission, source identity, safe file access and required product persistence
remain enforced for both applications.

Bind policy to each task and result contract under application selection and
Pack-owned rules. A mixed chain may contain research nodes with advisory checks
and calculation nodes with strict objective checks. Neither the conversation
label nor a global strictness switch may weaken a calculation contract or impose
scientific acceptance on an exploratory report.

Business adequacy belongs to continuing user review. Automated checks provide
findings and enforce declared objective contracts; they do not become a universal
judge of whether the user's business question has been fully answered. The user
can change direction, add information and request revisions while prior inputs,
results, failed checks and product versions remain traceable.

## Built-in systematic diagnosis

Adapt the local systematic-debugging method into a repository-owned, versioned
foundation resource. Do not copy workstation paths, coding-agent tool names,
mandatory human approval after three repairs, or unverified success statistics.

Provide an allowlisted structured diagnostic tool and a short on-demand guide.
The shared organization layer and authorized executors can use it. The contract
records the issue, observed evidence references, one falsifiable hypothesis,
a minimal probe, actual outcome, rejected hypotheses and next disposition.
Probe execution uses existing authorized tools; the diagnostic tool grants no
shell, file, network, business-model or credential access.

Use the method when an error needs investigation, results conflict, or repeated
attempts produce no new evidence. Normal answers and successful tool chains do
not require a diagnostic phase. A diagnostic record does not certify its own
hypothesis or produce Authority evidence.

Record the reason for a retry: for example a transient failure, a changed input,
a corrected call or a new hypothesis. A repeated call is not by itself grounds
for rejection. Observe retries within the issue and input-version scope, and
track elapsed time, use, outcomes and information gained. Retry allowance must
have an explicit finite budget in the accepted task policy; the implementing
plan must define its configuration and exhausted-state contract. Do not reset
that budget by renaming a node or reopening its diagnostic record.

When repeated attempts provide no useful information, use systematic diagnosis
to decide whether to change method, retain a gap, or stop the affected dependent
path. Do not turn an advisory research check into a hard rejection because a
hypothesis or optional proof field is absent. Keep existing hard guards for
authorization, persistence and unknown execution outcomes.

If investigation cannot progress, retain useful work and the unresolved issue.
The organizer can try an evidence-supported alternative, continue independent
work, deliver an honest limited result, or request required missing input. It must
not restart the whole task automatically or retry unknown side effects blindly.
Repeated repair failure prompts reassessment; it does not establish an arbitrary
global three-call limit or force an otherwise unnecessary user approval.

Persist diagnostic state through the existing task context and event contracts.
Expose a compact diagnosis status under the affected task; details remain
expandable. Resume must retain rejected hypotheses and completed probes.

## Delivery sequence and acceptance

1. Define accepted per-instruction execution selection and process focus; keep
   legacy session replay readable. Implement direct and general-tool paths first.
2. Connect research and registered grid execution through the shared organization
   contracts. Keep Pack semantics, model grants and current-run evidence intact.
3. Add the versioned diagnostic resource and typed tool with durable recovery and
   scoped repetition checks. Apply it to parent and authorized child execution.
4. Verify real direct answer, general tool work, research and registered grid
   tasks, including mixed follow-up, saved products and refresh recovery. Exercise
   one recoverable failure and one no-progress case with actual tool results.

Acceptance must also demonstrate that a failed advisory research check allows
delivery with a recorded gap and later user revision; an invalid grid result
cannot satisfy a dependent calculation contract; a justified retry is allowed;
and exhaustion preserves work without a long repair loop. Verify both policies
within mixed work and after refresh, not only in isolated session types.

Use focused contract and UI tests before local rebuild and real acceptance.
Inspect runtime screenshots against the accepted workspace. Record timing and
limitations; existing offline checks do not replace real execution acceptance.
Scope development CI to affected consumers. Cloud and demo deployment are separate
release work. Production gateway topology is not an accepted calculation model;
use registered calculation-ready models for the grid execution acceptance.

No implementation or verification in this document has yet been completed.
