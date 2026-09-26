# Live Session Checkpoint

> Updated: 2026-09-27 05:20 CST. Public demo opens directly; completed-run reset, layout, and line coloring have focused local verification.

## Current result

- Selecting a registered case shows its complete grid before a run. The API prewarms and caches authority-backed diagrams; the authenticated preview endpoint creates no session or run evidence. The case workspace retains its latest run and completed-step selection when another case is opened.
- The first manual click creates the session and submits instruction 1. Automatic completion remains the primary action. The fixed interpretation-boundary box is removed; the model label and IEEE-39 text are shorter; the breadcrumb is above the original hero image; the hero caption is smaller.
- The network view has a thin flat border and a shorter canvas, preserving the complete topology while exposing the analysis timeline sooner. The original hero art content remains unchanged. The central report and existing current-run evidence behavior remain in place.
- Local Compose enables a public demonstration credential issued by the API, separate from the private operator token and limited to registered scripted cases. The App obtains it on each load and enters directly; unavailable service shows a retry action. The diagram title is “电网拓扑图”; schematic buses use busbars, geographic buses use location points, and zoom needs Shift + wheel.
- At browser 100% zoom, the desktop App uses a compact presentation density calibrated against the user's 03:43–03:44 screenshots, restoring a centered workspace with outer margins and the original light-theme font values. Mobile width retains normal density.
- A completed case offers 「再次分析」, which returns that case to its initial manual/automatic choice without starting a run. The right detail column now extends with the long report like the left column. The hero's `CAPABILITY / EVIDENCE / CONTROL` line sits at the image's lower left; the remaining text has clearer vertical groups and uses the Chinese-only 「电力科学 AI」 theme. The header has no decorative link-like label. Line loading uses a clearly labeled within-run relative scale; returned lines use warm shades with the highest shown deepest red, without implying overload. Sidebar eyebrows read `CASE LIBRARY` and `CURRENT RUN`; redundant case-card registration text is removed.

## Verification

- All five registered authority preview CLIs returned complete diagrams. The local API image was rebuilt, the API container restarted without replacing the active worker container, and authenticated API calls returned IEEE-39, SciGRID-DE, and AC/DC preview diagrams.
- Focused App and API tests, the App production build, `make doctor`, `make test`, `make test-e2e`, `make validate`, and `git diff --check` passed. A real browser layout inspection used the authority-returned AC/DC diagram; its saved screenshot is `output/case-preview-layout.png`.
- New public demo API and host-setting tests passed; all 43 App tests and the App production build passed. The local API demo-credential, catalog, and provider-denial paths were exercised through the live Vite proxy. A browser reload returned to the workspace without the login form. A 2048×1152 browser screenshot confirmed desktop margins and a 390px viewport showed no horizontal overflow. The previous full repository gates predate these presentation and demo-access changes; they were not repeated.
- For the latest UI fixes, 25 focused App/network tests, the production App build, `make doctor`, and `git diff --check` passed. In the live browser, refresh returned directly to the workspace, a completed scripted run exposed 「再次分析」, the next click produced a distinct run ID, and the long report kept the left, center, and right columns aligned to the same bottom. Desktop and 390px hero measurements confirmed the image footer does not overlap the model list; no full repository gate was rerun.
- After removing the login screen, 25 focused App/network tests and the production build passed. A live browser refresh showed `CASE LIBRARY`, no credential form, equal sidebar widths, and no horizontal overflow. Deployment instructions now describe automatic public demo entry.
- For a phone on the same LAN, a separate Vite process can bind the computer's LAN IP on port 5174 while its development proxy keeps the API on loopback. The LAN page, demonstration credential endpoint, authenticated catalog, and 390px layout were checked locally at `192.168.2.24:5174`; the temporary Vite process was left running for the user to try.

## Preserve

- `.codex/config.toml` is an unrelated staged user change. Do not commit or reset it.
- Ignored `deploy/local.env`, `.grid-agent/`, `.capstone-agent/`, `runs/`, `output/`, and container volumes hold local state or artifacts; do not delete or expose them.
- Cloud Run, Railway, and Vercel have not been deployed. Provider validation has not been run.
