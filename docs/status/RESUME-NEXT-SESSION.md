# Live Session Checkpoint

> Updated: 2026-09-27 02:40 CST. Active design review, not a final handoff.

## Immediate context

- User rejected the SciGRID 50-bus preview and requested a professional diagram that persists across non-grid steps. They chose the complete geographic topology and approved the authority-backed persistent-view design.
- Verified the installed SciGRID-DE model contains 585 buses, 852 lines, 96 transformers, and finite coordinates for all buses; the current implementation sorts IDs and takes only the first 50 buses. Verified IEEE-39 has 39 buses, 35 lines, 11 transformers, and schematic bus coordinates.
- New design spec: `docs/superpowers/specs/2026-09-27-authoritative-network-diagrams-design.md` (commit `ee835d7`). It supersedes the previous bounded-preview choice. The existing model-facing 50-bus capability stays bounded; an operator-only authority projection will supply the complete diagram.
- User added clickable completed steps and retention of each case's latest execution state when switching cases. The App currently clears state on case selection and locks the catalog during active runs; the spec now requires per-case latest-session restoration and background continuation.
- The revised written spec review is pending under the `brainstorming` skill. After approval, use `writing-plans` to create an implementation plan, then execute focused red-green tests and implement. Do not modify application code before this review response.

## Existing product baseline

- Local Compose API/worker and Vite App are running. The current light App has manual and automatic three-turn execution, per-step bounded graph views, pan/zoom, task focus, and evidence-gated numeric coloring.
- Backend uses one API/worker image for local, Cloud Run, and Railway; Vercel serves the App. User requires local/cloud parity. Five cases were previously completed through the browser, but that validation predates the new diagram design.
- The earlier handoff and design are historical: `docs/superpowers/specs/2026-09-27-operator-workspace-network-design.md`. No broad test rerun is warranted merely for the spec.

## Preserve

- `.codex/config.toml` is an unrelated staged user change. Never commit or reset it.
- Ignored `deploy/local.env`, `.grid-agent/`, `.capstone-agent/`, `runs/`, and container volumes hold local state; do not delete or expose them.
- Do not run billed provider validation or deploy to cloud without appropriate authorization.
