# Capstone Framework Overview HTML Design

## Purpose

Create one self-contained HTML page for product and business decision makers.
The page explains Capstone's design ideas, framework boundaries, implemented
capabilities, deployment stages, and normal usage without requiring a build
step or a running Capstone service.

## Audience and message

The primary audience is product and business decision makers. The page leads
with the business value and trust model. It keeps implementation detail behind
progressive disclosure sections. The central message is:

> The agent organizes an analysis; the registered authority owns the facts and
> calculations; the application presents only evidence admitted for the run.

## Source of truth

Content must follow these repository sources:

- `docs/architecture/capstone-framework.md`
- `docs/architecture/capstone-development-lifecycle.md`
- `docs/RUNBOOK.md`
- `README.md`
- `docs/status/CURRENT-STATE.md`
- `docs/status/RESUME-NEXT-SESSION.md`

Do not present deferred or planned work as released functionality. State that
M6 through M9 are complete for their recorded scope, M10 is scoped but pending,
and Railway remains a single-family deployment.

## Information architecture

1. Hero: purpose, value statement, live implementation status.
2. Four-layer ownership explorer: `Application -> Domain Pack -> Kernel ->
   Registered Authority`.
3. One-run timeline: request, bounded tool call, authority result, admission,
   evidence binding, answer, and report.
4. Trust and evidence: explain why model prose cannot invent numerical or
   network claims.
5. Capability maturity: M6 Harness, M7 Result Projection, M8 Unified Thread,
   M9 PyPSA projection, and M10 topology provider.
6. Deployment stage explorer: local Compose, isolated cloud development, and
   isolated user trial.
7. Operator workflow: select case, inspect model, run instructions, review
   result layers, report, and evidence.
8. Local usage: concise commands and URLs with expandable operational detail.
9. Boundaries and next step: current limits, release rules, and M10 scope.

## Interactions

- A keyboard-accessible range slider highlights one framework layer and updates
  its responsibility, output, and forbidden ownership.
- A second range slider switches deployment stages and updates components,
  data isolation, and verification gates.
- A play/pause timeline animation advances through the run sequence. It has a
  visible current step, a restart action, and a static final state for reduced
  motion.
- Capability cards expose detail on click and keyboard activation.
- A compact disclosure control reveals technical notes without hiding the main
  business narrative.

## Visual and technical system

- One file: `docs/capstone-framework-overview.html`.
- Tailwind CSS loaded from its browser CDN; no package install or build step.
- All page content, inline SVG diagrams, CSS overrides, and JavaScript remain
  in the same HTML file.
- Dark navy and slate foundation, white content surfaces, emerald trust status,
  and amber boundary warnings.
- Use a restrained Swiss-style grid, strong contrast, visible focus rings,
  44px minimum interactive targets, and responsive layouts for mobile,
  tablet, and desktop.
- Respect `prefers-reduced-motion`; do not rely on animation to convey state.
- Use inline SVG line icons. Do not use emoji as interface icons.

## Verification

- Open the file directly in a browser without a local server.
- Check that the layer slider, deployment slider, timeline controls, cards, and
  disclosures work with mouse and keyboard.
- Check that the page remains readable at narrow widths and at 100% zoom.
- Check `git diff --check` and confirm only the specification and the requested
  HTML are task-owned changes.
