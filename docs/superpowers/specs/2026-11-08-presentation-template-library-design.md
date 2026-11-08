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
Keep content editable where supported. Paginate content within layout bounds;
report unsupported layout objects or overflow rather than silently dropping text.

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
