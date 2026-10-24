# Enterprise research: real continuous-session check

Date: 2026-10-17 22:30 CST. Local development only.

## Scope and source

The user prioritizes a working real task path over complete polish. This check uses the configured Provider, real Pi tools, stored files and the actual App. No scripted model response was used.

- Source: `159803897127b33d791ef77298ba9fbe5da13a2b` plus uncommitted changes in `.worktrees/model-decision`; not merged into dev.
- API/worker image: `sha256:bdae9325a9fbe2c7dbcaf4acc6b17c9f4757e1a960fdafe34cd12caa4e4c82c8`.
- Canonical rebuild passed. App: `http://127.0.0.1:5173/`; API: port 8767.
- Test Thread: `thr_6d09b90dbbc1eb119617`. Work: `work_edc38073b98b3acd3616`.
- Main, cloud and user-trial deployments were not changed.

## Actual result

1. Reopened the stored task delivery v1 after service rebuild. Its original file contains 796 bytes.
2. Used the App to select that exact delivery as input, then requested a report revision. Attempt `attempt_f6c4de759ee330a4` completed in 33.0 seconds. The public execution display showed eight tool calls.
3. Resolved `revised-review.md` through the product API: 3016 bytes, SHA256 `88c1985d3b8752e82e15443b09d1ead88f7e8a2908a31c4066936a034eca3ad0`. The first 796 bytes exactly match v1. The added analysis reports monthly profits 40 and 60, total 100, and growth 50%.
4. Opened the actual file in the right workspace. Used the existing delivery form to publish v2 of the same task delivery.
5. Refreshed the page. Both v1 and v2 were present. Selected v2 and requested a separate executive summary. Attempt `attempt_2d96989a932e95dc` completed in 22.6 seconds with six displayed tool calls.
6. Resolved and opened `executive-summary.md`: 1668 bytes, SHA256 `a0f261d1032adb2a3baee926adeb019c77d1ed881026eb3fff79c4eb46239730`. It cites the actual v2 file and retains the correct figures. This is a new instruction product; the task session remains open.
7. Actual research-state updates reached revisions 3 and 4. The shared research tools were invoked by the model, not synthesized by the frontend.

Browser check: 1440 CSS pixels, viewport scale 1, no page-width overflow. Screenshot: `/tmp/capstone-research-real-continuation.png` (local review artifact).

## Startup failures fixed

Earlier attempts failed before Provider execution. The failures remain in the task history.

- Research mirror used the read-only container root. It now uses the existing task temporary mount.
- Shared research extensions could not resolve the pinned Pi SDK. The container now links to the existing pinned dependency directory.
- Changing request-directory permissions after transferring ownership failed under the existing container capabilities. Permissions are now set before ownership transfer.

The real Linux container completed the full inventory startup with nine tools before the successful Provider checks. Focused startup tests passed (15); types passed. The earlier broad backend run had 1493 passes and three stale test assumptions; those assumptions were corrected and all 64 affected tests passed. This is not a release-gate claim.

## Remaining scope

This proves the basic enterprise file-task continuation path. It does not prove all enterprise tasks, cross-Thread references, or native Pi delegation from the default professional grid research loop. That grid-loop integration remains active work. Non-blocking presentation issues, including incomplete material counts in the context label, stay in the follow-up list and do not invalidate the actual saved inputs and products above.
