# PPT integration and reference research closure

## Scope and source

User approved integration of the verified PPT candidate and closure of the old
reference-execution research branch on 2026-11-14. Integration source is
`29c0ce72`, based on actual dev `b4992b94`. It is not yet merged or CI-approved.
The original PPT source remains `81dd3652`, with published head `43acac28`.
Keep that source until the accepted changes have entered dev.

## PPT differences reconciled

Dev already contained the State Grid PPTX and the opt-in renderer. It did not
contain the persistent template catalog, session selection, task-bound template
adapter, frozen content/source bundles, same-PPTX PDF conversion or the ordinary
entry's default State Grid correction. Those increments are now in the integration
candidate, together with confirmed-product delivery and current-call service-bus
records. App version display uses eight characters.

Do not overwrite dev's on-demand domain discovery, structural context identity,
resource migration, retired package removal or initial-snapshot recovery. The old
candidate also moved a React Hook below conditional returns and removed its
regression test. Both changes were excluded; dev's Hook order and test remain.
Gateway/sidebar/model-context fixes already present in dev need no duplicate patch.
The focused presentation CI route preserves the existing retirement gate. Its
renderer check uses `python -m pytest` so added rendering dependencies use the
selected interpreter rather than an inherited pytest script.

## Reference research disposition

This is reference-based execution and data-projection research, not a pending DR
runtime or a second lightweight chain. Its three commits contain two designs,
a baseline record and one mocked composition feasibility test. No runtime module
is uniquely implemented there.

| Original objective | Current implementation evidence | Disposition |
| --- | --- | --- |
| Compose dependent calls and bounded independent analysis using saved references | Current `resources/tool-composition.mjs`, observation helpers and 50 composition tests | Reuse the lightweight chain; no second executor |
| Fetch once and send the dataset reference to two remote analyses | Original `2289ab3a` test extracted onto current source; full composition suite passes | Preserve as a regression test; mocked provider is not real gateway acceptance |
| Admit exact tool/schema/version, source identity and observations | Existing discovery and gateway relay contracts, including selected instance and current-run observations | Existing foundation; opaque reference ownership across arbitrary services still needs actual contract review |
| Cancel, retain observations and recover after local failures | Existing composition failure, cancellation and observation-reuse tests | Reuse current mechanism; not proof of an end-to-end reference-only business investigation |
| Compare opaque-only, structured findings and approved summaries sent to an external model | No separate complete projection policy or audited comparison identified in this branch | Design backlog; no claim of zero data egress |
| Produce reports from immutable remote references and revise after a scope change | Research designs only; actual gateway publications must be verified | Design backlog; no new implementation gate for PPT integration |

Archive head:
`archive/branch-ownership-20261114/uukuguy/reference-execution-research`
points to exact `2bd086af19bd7b19173a58a151d38ac78faad856`.
Published recovery tag:
`archive/20261114-branch-ownership/reference-research-local`.
The worktree and its three dirty documentation files are preserved byte-for-byte.
The original designs and baseline remain recoverable there. Remaining questions
belong to the core-evolution notebook, not an active branch or automatic delivery.
Future experiments start from current dev with an explicit scoped task and real
published gateway contracts. No research runtime or old deployment is merged.

## Verification

Local focused checks: 251 backend passed and 46 skipped without the PostgreSQL
fixture; a separate real PostgreSQL template/resource check passed 46 with one
existing skip. Renderer/PPT bytes: 85 passed. App: 378 passed and TypeScript clean.
Template SDK: 12 passed. Current composition: 50 passed. Governance/image/runtime
contracts: 218 passed and four pre-existing conditional skips. Selected backend
Pyright: zero errors. A missing PIL collection error came from using the pytest
script outside uv's added-dependency interpreter; rerunning with `python -m pytest`
passed. No product regression was hidden and skips are not counted as passes.

## Final local acceptance

The reviewed runtime is `ddc3df02`. Review identified missing renderer identity;
`a7440980` binds renderer version, three fixed source hashes and library source hash.
The installed symlink entry exposed a path lookup failure during image smoke.
A new regression reproduced it; `ddc3df02` resolves the source location correctly.
The final renderer suite passes 86 tests; the additional direct runtime consumers
pass 213 tests with one existing conditional skip. No new important review issue
remains. The failed build did not replace the running services.

Canonical rebuild is ready. API and all three workers use
`sha256:bd4bb567941b51ac7a8617f239188116fa2a8c86aed122145f09aa55a2b1537d`.
Native image is `sha256:ddedbbc35932c48be2096354b5e73e7fa32f06659c365c522e5a8910ade27008`.
Backend/native images have 62/37 layers. Existing Docker responsibility groups
were extended; no per-file copy layers were added. The pinned Pi dependency layers
were cached. Scoped image/cache maintenance completed after the rebuild.
Default App5173 remains the dev checkout. Candidate App5174 runs this integration;
that temporary source difference is recorded in the environment register.

Real Thread `thr_04e92aa2a510c0434678` completed four stages in 16.333, 42.674,
32.520 and 40.664 seconds. The initial library stage selected an existing blue
library template without the probe explicitly requesting it; this is not accepted
as a default-template test. The next stage reused its frozen content with State
Grid. The final post-rebuild stage explicitly selected the built-in State Grid
session template and verified both library/PDF and ordinary omitted-template
rendering. All 47 downloaded file records match their registered hashes. The
final saved receipts match the installed renderer and library source hashes;
content identity remains the same after bundle rerendering. Old products remain.
The session restores after backend recreation, and the selection remains State
Grid on a new HTTP read. Cover/body images were inspected. This is mechanism
acceptance using synthetic text, not business-analysis or report-quality acceptance.

Control graph regenerated from the actual dev register; all six deployment
reference paths sampled without crossing cards. The archived research source is
removed from active milestones. Same-tab candidate App5174 restore displays all four completed rounds and final PPT/PDF products; the page shows ddc3df02. Screenshot: `/tmp/capstone-ppt-final-app.png`.
See the [bounded receipt](receipts/2026-11-14-presentation-integration.json).
No CI, remote PPT deployment or dev merge has occurred for this candidate.

## First approved CI and local repair

PR104: <https://github.com/uukuguy/capstone/pull/104>.
Run43494883528 tested5cb6b6e1 on macOS. Runner execution lasted2m00s
(19:48:51–19:50:51 UTC), after about5m18s in the queue.
Governance:256 passed/3 skipped. Native environment:19 passed. Pyright clean.
Backend direct-consumer group:584 passed/66 skipped/1 failed. Later renderer,
Node and App steps were not reached; prior local acceptance remains separate.

The failure is the existing `test_slow_response_obeys_parent_deadline`, not
PPT output. That test requires cancellation confirmation after the60ms parent
deadline but supplies only0.5s for cleanup. CI records a cancellation transport
timeout before the fake server observes DELETE. A local600ms cleanup-dispatch
injection reproduces the same empty cancellation list. The test now uses the
configured cleanup budget (currently5s) while retaining its60ms parent deadline.
Separate slow-body/header/nonstopping-task tests keep their0.5s cleanup limit.
No production deadline or runtime code changed.

The injected failure passes after the fix. All86 Pi delegation tests and113
focused scope/governance checks pass. The amended test is already a named
consumer in the existing PPT CI command; its path is now explicitly registered
in the focused route. This does not add a suite or expand the approved gate.
The first approval is consumed. No second CI, push or PR update has started;
new explicit approval is required before publishing this repair.
