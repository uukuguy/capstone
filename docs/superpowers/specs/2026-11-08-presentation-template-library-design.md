# PPT template library and repeatable rendering

## Accepted scope

The application provides a PPT template library. The default is
`data/国网ppt模板.pptx`. New PPT products use this template unless the user
selects another template. PDF exports derive from the same rendered PPTX.
Users can change the template through conversation and render an existing
presentation again. An uploaded PPTX applies to the current session by default;
only an explicit request to add it to the library makes it persistent there.

## Ownership and selection

This is an application product capability. It does not add presentation semantics
to the Kernel or change Authority results. The application owns the template
catalog, access checks, selection, render records and product history. The native
executor receives only admitted template and content references in its private
workspace. It receives no host path or storage credentials.

Each catalog entry has a stable ID, display name, immutable version, digest and
durable file reference. The built-in entry is available after installation without
depending on the operator checkout. Uploaded templates use existing resource
ownership and version checks. The host freezes the selected template per render;
later selection changes do not change an active render or historical products.

The model interprets requests such as “use the uploaded template” or “restore the
default template”. The host validates exact references and permissions. There is
no keyword router or fixed first tool action. Ambiguous uploaded-template choices
require clarification. A selection is scoped to the conversation and remains in
effect until changed; an explicit one-render selection overrides it for that render.

## Content and rendering

Save a versioned presentation content document with ordered slides, text, tables,
figures and source references. Its dependent files use immutable admitted resource
or product references. The content document is the input for later rendering;
an existing PPTX alone does not imply that its original content document exists.
For older products, report this gap and offer content recovery rather than claim
an exact re-render.

The renderer maps cover, contents, content and closing roles to the selected
template. Preserve master/theme, logos, colors and footer styling. Do not retain
sample business claims, sample figures or placeholder text from template slides.
Keep content editable where supported. Page expression is part of template style.
For a management briefing, plan one main point per slide, usually one focused
figure or compact table with concise reasoning that supports its claim on the same
page. Keep full derivations and secondary detail in speaker notes or supporting
files. Keep limitations that affect the conclusion visible on the slide.
Do not mechanically split blocks into extra slides or reduce text size to make
long prose fit. Report overflow so the author can revise the content or explicit
page plan. Preserve the existing untemplated generator as a separate baseline.
The first delivery adds opt-in template generation; it does not change that
baseline or establish persistent library selection and runtime PDF support.

### Accepted report argument refinement

A complete briefing has a cover, agenda, connected chapters, synthesized
conclusions and a closing page. The agenda expresses the report argument rather
than listing unrelated slide titles. Each chapter answers a report-level question.
Visible chapter context connects its pages. Each opinion page presents a supported
claim, the evidence for it, an explanation of that evidence and a relevant
implication where warranted. These can be concise sentences or other appropriate
compositions; a fixed number of tiny bullets is not the writing standard.
Page count follows the argument and readability, not the source deck's 14 pages.

For the current briefing, the runtime report generator derives the main topics
from admitted findings and organizes an opening overview, themed analysis and
closing synthesis (total/detail/total). The agenda lists only the main chapter
titles, without questions, slogans or method prose. Each opinion page responds
to one agenda topic: the exact numbered chapter title appears on the right of
the title bar in22pt bold using the title font, with a separate27pt page claim on the left. Reserve both
rectangles; an overlong claim requires rewriting, not overlap or smaller fonts.
Developers provide generic mechanisms and review criteria, not topic names or a
fixed chapter count. Verify independent organization in a fresh Work context
without a prior developer outline. The argument plan and final agenda/section
mapping are saved products for review.

Compile the current main report using existing data and products first. Record
report-led acquisition planning as a separate later implementation: audience and
decision questions lead to candidate claims and evidence needs, which guide
targeted data acquisition and analysis. Save gaps and revise unsupported claims.
Do not claim this upstream behavior is implemented by a post-analysis rewrite.
Autonomous quality must be assessed on the visible page, excluding speaker notes.
Each opinion page needs sufficient evidence and explanation to support its title
and advance its chapter; a context or boundary page may explain what can and
cannot be concluded. Do not force operational recommendations, a bullet count or
a word count. The runtime reads back final slide text, records actual semantic
defects, makes bounded targeted revisions and reviews again after layout edits.
The reusable mechanism must contain no case-specific chapters, metrics, thresholds
or preferred conclusions. V6 is a reviewed quality reference, not a runtime input
or a source of prescribed wording. V7's numeric-fragment pages fail this criterion.
Self-assessment records are evidence of a check, not independent acceptance.

When the application grants an isolated text reader, the report workflow uses it
after a draft exists. Supply bounded visible text and relevant source facts,
excluding author notes, the argument plan and previous self-review verdicts.
The reader returns material issues and evidence locations. The author checks
actual findings against sources, records dispositions, revises and renders again.
Required pending reviews stay pending through collection timeouts. A critic is
another model observation, not Authority truth. The existing local text-pool
experiment provides this capability without new child tools or data access;
availability and production-default acceptance remain separate.

For new evidence briefings, the executable `capstone-presentation/2` contract
requires a template and `argument: {explanation: <literal text>}` on each ordinary
content record. The renderer writes that authored explanation into the visible
body and applies the same overflow budget. It records page/explanation digests;
it does not certify the inference. Agenda/closing records omit argument.
Version1 remains compatible for the baseline and historical rerendering. This
prevents the saved report argument from being silently relegated to notes during
composition; it neither generates business conclusions nor imposes a prose count.

See the [compilation plan](../plans/2026-11-08-briefing-report-compilation.md).

A render record binds content version/digest, template version/digest, dependent
source references, renderer version, output hashes and conversion status. Changing
templates reuses the content document and source files, without rerunning business
queries or calculations. Publish new product versions and retain all old products.
Template choice and provenance survive page refresh and continuation.

## Failure behavior

Reject invalid, inaccessible or changed template references before rendering.
Validate PPTX package structure and bounded processing separately from upload
quotas. Do not execute embedded macros or external links. Render to temporary
outputs, validate them, then publish. Failed rendering must not publish an old file
as a new success. If PDF conversion fails, retain a valid PPTX with an explicit
PDF failure status; do not claim that both formats were delivered.

## Acceptance

- A real conversation generates PPTX and PDF with the default State Grid template.
- A continuation changes to an uploaded template and renders the same content.
- An explicit request saves that template to the library and permits later reuse.
- Returning to the default template works after refresh.
- Output version history, content identity and source references remain intact;
  re-rendering requires no new business tool calls.
- Focused checks cover reference ownership, version changes, selection precedence,
  missing historical content, invalid packages and conversion failure.
- Inspect rendered pages against the template for Chinese text, tables, figures,
  logos, footers, sample-content removal and overflow. Unit checks alone do not
  establish visual acceptance.

## Implementation constraints

Extend the existing capstone-report and product/resource mechanisms after checking
their actual contracts. Preserve current standalone HTML behavior. Reconcile the
existing Python presentation renderer with the presentation skill's artifact-tool
guidance during implementation planning; this design does not prescribe a new
dependency before that evaluation. No separate conversation UI is required.
Remote deployment and CI need their existing explicit authorization and gates.
