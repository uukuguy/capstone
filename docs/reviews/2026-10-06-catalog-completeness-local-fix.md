# Local repair of incomplete model catalog answers

Demo pressure testing found a completed informational answer that claimed 21
registered PyPSA models but omitted `congested-two-bus`. The registered catalog
contained the missing model. The user requested a local repair first.

## Cause and repair

The application supplies its complete bounded catalog to the runtime. Ordinary
answer admission previously accepted the returned prose without checking that a
full-list answer included the selected registered models. A model could omit an
entry while still completing successfully.

Source `39007a1` adds an application-owned completeness projection. It uses the
immutable catalog attached to the current Attempt. For a full model-list request,
it selects the named registered implementation families, or all families for an
unscoped request. It checks exact model identifiers rather than substrings.
If entries are missing, the application replaces the incomplete list with a
bounded table containing the registered names, identifiers, families and supplied
availability states. The count comes from these entries; no model count or
particular missing identifier is hardcoded.

Complete answers keep the model's prose. Explicit examples, shortlists and
recommendations remain outside this completion check. General explanations and
mixed calculation requests retain their existing paths. The listing predicate
is shared with the existing application router; routing behavior is preserved.

The repair belongs to Application presentation and admission. It changes no
Domain Pack tool, Kernel SPI, registered authority access or numerical admission.
The corrected catalog answer is `offline_information` with
`deterministic_information` assurance and no result or evidence references.
No extra Provider call is made to repair an incomplete list. It checks list
completeness; it is not a general factual verifier for arbitrary LLM prose.

## Local verification

Four omission, family-scope and identifier-substring regression cases fail before
the repair and pass after it. A separate subset-request regression also fails
before its exclusion is added. The actual worker/Harness regression confirms
that an incomplete streamed answer commits the corrected final answer, closes
the runtime, and creates no numerical evidence.

The final backend suite passes 540 tests, with 35 optional PostgreSQL checks
skipped. The 109 focused admission, routing and Harness tests pass. Type checks,
package boundaries and doctor pass. Three registered worker integration tests
pass. The saved original demo answer is replayed locally and produces the complete
21-model list, including the omitted model, without evidence references.

The checked-in `make capstone-local-rebuild` entrypoint completes for final
committed source `39007a1`. All 344 backend Python source files match in API and
both workers; all three roles use image
`sha256:ebe52977550ca4f42b0a69ab61f317976f8af7e198c85e88530038c57b542e70`.

Actual local App submissions verify the original Chinese query, an English
catalog query and the Chinese query again after switching to two-bus through the
model control. All three final answers contain all 21 registered PyPSA model
identifiers, render in the App and have zero result/evidence references. Reload
preserves the answer. These three live responses were already complete and kept
their LLM prose. The repair branch is verified by replay of the saved omission
and the deterministic worker/Harness regression rather than by forcing a live
Provider failure.

The same App then completes real two-bus economic dispatch plus AC validation
with four result references, four evidence references and verified lineage.
There are no App alerts, and the 390-pixel layout has no horizontal overflow.
Desktop and mobile screenshots are inspected. The owned browser session
`catalog-completeness-local` is closed; its browser list is empty.

The exact-source local receipt is
`runs/catalog-completeness-local-20261006/acceptance.json`. This is local
verification; it does not establish that either cloud stage contains the repair.

Private local receipts are stored under
`runs/catalog-completeness-local-20261006/`; rebuild, backend and integration logs
use the `runs/catalog-completeness-` prefix. Existing user data is preserved.
At local acceptance, cloud development and demo remain on their prior source.
No cloud deployment or configuration operation is performed during the local
repair. The later [automatic promotion report](2026-10-06-catalog-completeness-promotion.md)
records exact-source acceptance and deployment to both cloud stages.

The [demo pressure report](2026-10-06-demo-load-validation.md) remains the record
of the observed cloud defect. Cloud verification follows the
[release lifecycle](../architecture/capstone-development-lifecycle.md).
