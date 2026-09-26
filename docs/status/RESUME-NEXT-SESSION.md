# Live Session Checkpoint

> Updated: 2026-09-27 04:17 CST. The operator App changes have passed local gates.

## Current result

- Selecting a registered case shows its complete grid before a run. The API prewarms and caches authority-backed diagrams; the authenticated preview endpoint creates no session or run evidence. The case workspace retains its latest run and completed-step selection when another case is opened.
- The first manual click creates the session and submits instruction 1. Automatic completion remains the primary action. The fixed interpretation-boundary box is removed; the model label and IEEE-39 text are shorter; the breadcrumb is above the original hero image; the hero caption is smaller.
- The network view has a thin flat border and a shorter canvas, preserving the complete topology while exposing the analysis timeline sooner. The original hero art content remains unchanged. The central report and existing current-run evidence behavior remain in place.

## Verification

- All five registered authority preview CLIs returned complete diagrams. The local API image was rebuilt, the API container restarted without replacing the active worker container, and authenticated API calls returned IEEE-39, SciGRID-DE, and AC/DC preview diagrams.
- Focused App and API tests, the App production build, `make doctor`, `make test`, `make test-e2e`, `make validate`, and `git diff --check` passed. A real browser layout inspection used the authority-returned AC/DC diagram; its saved screenshot is `output/case-preview-layout.png`.

## Preserve

- `.codex/config.toml` is an unrelated staged user change. Do not commit or reset it.
- Ignored `deploy/local.env`, `.grid-agent/`, `.capstone-agent/`, `runs/`, `output/`, and container volumes hold local state or artifacts; do not delete or expose them.
- Cloud Run, Railway, and Vercel have not been deployed. Provider validation has not been run.
