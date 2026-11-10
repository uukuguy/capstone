# Presentation template library implementation

Accepted design: ../specs/2026-11-08-presentation-template-library-design.md.
Base: remote dev d7358eac. Existing renderer, template artwork and argument review
are byte-identical to the old template branch; do not merge duplicate history.

## Scope and ownership

Application/native report capability only. Keep baseline capstone-report behavior,
existing conversation, product versions, Authority boundaries and source evidence.
Reuse the protected native resource workspace and its persistent volume. Library
metadata/files must never become caller-selected host paths or storage credentials.
Use application-admitted workspace/session identity, exact version/digest and grants.
Keep upload/storage quotas separate from bounded PPTX processing and model context.

## Delivery sequence

1. IG1 native failure recovery: reproduce frozen skill identity mismatch through
   GeneralPiHost, preserve its fixed failure code, publish actionable reader text,
   and verify later valid execution and saved products survive. Do not expose
   arbitrary exception strings or recreate the removed manual selection UI.
2. Durable template catalog: built-in State Grid, immutable uploaded versions,
   explicit library publication, session selection and per-render override.
   No uploaded file is globally published by default. Validate confined source,
   package structure, digest, grants and processing bounds before publication.
3. Native semantic tool: catalog/select/publish/materialize through a fixed private
   host adapter. Bind workspace/thread from admitted task context, never arguments.
   Reuse existing permission rules and task grants. Add sources to existing Docker
   responsibility groups and runtime identity closure; retain baseline CLI.
4. Repeatable rendering: freeze template/content/dependencies, render new PPTX
   versions without business requery, save content and receipts, preserve history.
   PDF derives from this PPTX through the admitted renderer; unsupported/failed
   conversion is explicit and must not claim PDF delivery or weaken acceptance.
5. Focused local tests, canonical rebuild and real two-turn generation/change/
   restore trial. Verify exact products and hashes, selection after refresh,
   immutable old versions, no new business calls, and actual rendered pages.
6. Reconcile the old template branch: close it only after all unique work is
   accounted for; preserve its dirty journal and recovery checkout. Prepare a
   dev PR only after scoped checks and separately approved CI.

## Files and acceptance

- Native failure: general_pi_server.py, failure_delivery.py and direct tests.
- Library: new presentation_templates.py with durable catalog/selection operations
  and contract tests; no Kernel semantics or second task ledger.
- Adapter: existing NativeTaskRunner/private task route, general-sdk.mjs and one
  semantic presentation tool module with grant/identity/unknown-outcome tests.
- Rendering: existing native_report.py/presentation modules and real PPTX tests.
- Operations: existing Docker source groups, native identity and focused CI route.
- Durable state: canonical worklist, actual-dev version register/HTML, append-only
  journal and live checkpoint. Keep implemented/verified/merged/deployed separate.

Default template, conversation changes, explicit library save, rerender identity,
PDF outcome, source isolation and final visual checks each have separate gates.
Unimplemented gates remain open. Browser unavailability does not imply acceptance.
No CI is currently approved for this branch; no remote deployment is in scope.
