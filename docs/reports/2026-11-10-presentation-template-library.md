# PPT template library integration

Status: candidate deployed and checked on local-dev and dky3-dev. Not merged into dev. CI is not approved.

The user includes the PPT template library in this closeout. The owning contract
is [the accepted design](../superpowers/specs/2026-11-08-presentation-template-library-design.md).
Old template-branch renderer work is already in dev through PR100. Do not merge
its older runtime copies over the accepted execution baseline.

## Source and implementation

Branch `uukuguy/ppt-template-library-20261110` starts from remote dev `d7358eac`.
Worktree: `/Users/sujiangwen/orca/workspaces/capstone/ppt-template-library-20261110`.

- `0dd953c0`: fixed frozen-skill failure codes and actionable recovery text.
- `2a8d97e6`: application PostgreSQL catalog, private object storage and session selection.
- `760caf31`: task-bound native adapter and SDK tool, with host-owned scope and grants.
- `bde30e8f`: frozen content/dependency bundles, new output paths and PPTX-derived PDF.
- `1a081533`: bind renderer bytes to the native configuration identity.
- `2bbc2c54` and `1c2407f0`: bounded layout diagnostics and exact model-facing argument schemas.
- `e05dea18`: focused macOS presentation-library development gate; no CI execution.
- `b296abc0`: integer uploaded-resource versions and safe adapter rejection codes.
- `922b0956`: preserve State Grid body and agenda layouts when rendering frozen bytes.

Uploads stay session-only until explicit publication. Published templates survive
source-session deletion. Conversation selection persists; per-render overrides
do not change it. The built-in template is State Grid. Metadata uses the existing
ledger, with immutable references and bounded private object chunks. No second
task ledger, caller-selected endpoint or storage credential is introduced.

Rendering saves content and exact dependency bytes with digests. A source bundle
can render again after source deletion without business queries. Existing
untemplated `capstone-report` remains available. PDF conversion failure retains
PPTX and records a separate status. These products are not Authority evidence.

## Focused evidence

- Skill host/scope: 129 passed, 32 skipped; scoped types passed.
- Isolated temporary PostgreSQL catalog/API: 17 passed, one memory-only skip.
  Only the test-owned database was created and dropped; live data was preserved.
- Adapter/catalog/package: 25 passed, 14 PostgreSQL checks skipped locally.
- Host/native regression: 137 passed, 33 environment skips.
- Context/task grants: 20 passed; scoped types have zero errors.
- Renderer/baseline/image packaging: 66 passed in 8.31 seconds.
- SDK binding/fixed renderer/recovery: five passed.
- `make doctor` and `git diff --check` passed.

Canonical feature-checkout rebuild passed, including real PDF conversion and equal
PPTX/PDF page counts. Exact source `1a081533`: API and three workers use image
`7273329dcaa1`; native image is `4bd2eaa9b841` with 37 layers. App source remains the actual dev
checkout, product `d78cc528`; no App code changed in this candidate.

The first synthetic task `thr_519c6cc0781a538152b5` was rejected before model
execution. The rebuild command overrode the environment file's protected gateway
directory with an empty directory. The original files were preserved. Rebuilding
with the original environment-file path passed; the registry and its existing
selection are restored. This is an environment
setup error, not a template generation result. No authentication state was copied.
Synthetic real-model trial `thr_1488f150d33f201e379f` completed in104.46s.
The direct tool had three invalid/failed render attempts. Generic failure text
hid a missing `/2` slide argument and layout overflow, causing repeated shell
diagnosis. The model eventually rendered through the fixed CLI. Four delivered
PPTX/PDF/source/receipt digests, content and dependency digests and three PDF pages
were verified. All three PDF pages were visually inspected: State Grid cover,
readable Chinese text and table, no clipping. This does not accept the direct tool.

The diagnostic fix returns only bounded structured renderer errors, preserves
generic handling of arbitrary process failures, and publishes exact argument
fields plus minimal content contracts. Regression: four render tests and six
template SDK tests pass. The second trial `thr_e87dc0142922a5b39896` completed in33.88s on
source `e05dea18`, API/three workers image`faeb0d680ece`, native`b20f770b89d5`.
Canonical rebuild and PDF image smoke passed;95 cache hits,37 native layers.
The model used the template tool, corrected two explicit layout rejections and
saved the four products. Four download digests, source/content hashes and three
PDF pages pass. No renderer-source inspection was needed in this round.

Its continuation uploaded a blue test template and requested library publication
and a one-render override from the saved source bundle. The new SDK schema wrongly
declared resource.version as string; uploaded-resource versions are integers.
The adapter rejected import. This trial was deliberately cancelled after161.34s,
with receipts retained. It is not accepted. `b296abc0` fixes the type and safe
rejection projection;10 Python checks/4 database skips,7 SDK checks and types pass.
Review also found that the new wrapper treated State Grid as a generic uploaded
layout. `922b0956` retains the built-in body/agenda contract while reading exact
frozen bytes;77 renderer checks and7 SDK checks pass. Rebuild and continuation
retest are in progress. No old product was overwritten.

The complete proposed focused gate passed locally:256 governance checks/3skips,
312 backend/host/direct-consumer checks/58 environment skips,76 renderer/baseline
checks and10 template/skill SDK checks. Scoped types report zero errors. Isolated
PostgreSQL catalog/API/native-port checks:29 passed/1 memory-only skip in93.70s;
the temporary database was dropped. CI routing resolves to `presentation-library`.
These are local checks, not an approved CI run or complete product acceptance.
The reviewer tool failed before starting because its configured
model is unavailable; no independent review is claimed.

## Final local candidate evidence

Candidate `eb481485bb21ce0b36d7fdd8ba53f0218e5be9ab` includes the service-bus
execution-record follow-up. App product revision is `f3d1f5cf`; the later commit
changes only the focused CI route. Local API and three workers share image
`f8488c5b5e927a11bf79c50c620c013dc56a41d212ac55da8f0a39637418a95f`.
Native image is `382a14ced31d344e3a2e4301aca669e0bad8a5432a1f01709ebfd2cf0f18d922`.
The canonical local build uses its existing `development` image-source label;
source-byte matching, image identity and the exact App receipt must be read
together rather than treating that label as a Git revision.

The corrected continuation completed55.41s, publishing/selection completed70.81s,
and restoration to State Grid completed44.33s. Real tool operations cover session
import, per-render override without changing the default, explicit library
publication, independent cross-session selection, persisted selection and frozen
content rerender. All saved PPTX/PDF/source-bundle/download digests match. Original
and rerender content hashes match; template hashes change only on selection.
State Grid and blue-template PDF pages were inspected. Historical missing source
bundles have explicit recovery; PDF failures retain the PPTX.

On the final local source, thread `thr_f47f3cf9fa60fed92cc6` completed33.81s using
the actual template tool. Four product downloads and the complete render receipt
passed digest, content, dependency and PDF-page checks. The default is State Grid.
Receipts: ignored `.capstone-agent/template-library-live-20261110-service-bus/`.

Latest focused additions: gateway/host/transport295 pass/32 environment skips,
application persistence/diagnostics99 pass, App323 pass, types zero errors,
governance256 pass/3 skips. No new CI or independent-review acceptance is claimed.

## Remaining integration

The same exact source passed dky3-dev real task89.41s, four product digests,
two-page PDF inspection and browser refresh. See the
[deployment receipt](2026-11-10-service-bus-execution-records.md).
Obtain review and request a focused CI run only when the local candidate
is ready. Integrate through a PR into dev, verify its actual entry point, refresh
the control graph and account for all unique work before closing the old branch.

Explicit remaining design gaps: orphan-copy/session-template quota and garbage
collection, plus updates that create multiple immutable versions under one stable
template ID. Current add creates a new ID with one immutable version.
