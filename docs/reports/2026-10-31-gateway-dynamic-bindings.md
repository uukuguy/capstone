# Gateway dynamic binding verification

## Outcome

PR81 merged into dev as `61ec56c6`. Capstone no longer branches on the audited
gateway business tool names, provider name or `readonly_sql` toolset label.
Initial business calls remain model-selected from current discovery. Subsequent
calls use returned actions and exact contracts. Supported result schemas and
verified receipts select presentation; they do not grant Authority evidence.

The implementation preserves bounded activation, task grants, protected
credentials, source revisions and reference checks. Mirrored actions deduplicate
by tool and arguments; explanatory metadata does not create false ambiguity.
Actual App reads accept validated pages up to1000 records without rewriting the
published invocation. Frozen view restoration binds schema, source selection,
model revision and expiry.

## Verification

- Final macOS PR gate:41145432600, head `40c4c2e4`, passed in3m33s.
- Scoped setup excludes unrelated PyPSA/tool/workbench installation and builds.
  The gate runs gateway and direct consumer checks, focused App tests and types;
  no full solver, workbench or release suite is selected.
- Independent review findings for real App read limits and restored selection
  defaults were corrected. A live mirrored-action failure produced two regression
  tests and was fixed before acceptance.
- Fresh gateway protocol checks covered task/view state distinction, inspection,
  build,101-block download and full SHA256, full129-device pagination, drilldown,
  unknown jobs, wrong revisions and wrong-view/wrong-stream cursors.

## Actual local dev

Canonical root rebuild passed. API and three workers are healthy on image
`sha256:989226e8c78d9c38111a722c22275f94feef6a8e9a754bba6537f10527f30e11`.
App effective product revision is `d9e24798`, repository revision `61ec56c6`,
product dirty=false. Project-scoped cache maintenance completed in apply mode.
Cloud-dev, demo and local-demo are unchanged.

- Directory task: `thr_e7821b65e9b793665f98`, attempt `attempt_fbabd51e4c871ebb`.
  Completed in62.29s; CSV has five records with source-qualified references.
  Download hashes and refreshed session state passed.
- View task: `thr_807ed824f046e4e03a5e`, attempt `attempt_580c4d414aa92e8d`.
  Completed in81.51s; source descriptor and saved products retained. Protected
  App open restored the same pinned ready view; its default stream returned189
  of189 records. This is API/consumer verification, not human visual acceptance.

Evidence: `runs/gateway-next-action-20261031/` and
`runs/gateway-dynamic-product-20261031/`; rebuild log
`/tmp/capstone-gateway-dynamic-rebuild.log`; scoped cleanup receipt
`.capstone-agent/cache-maintenance-20261031-074504-52484.log`.

## Performance and remaining scope

The directory task is functionally valid but slow for five rows. Event timing
records20 model responses totaling53.27s; gateway calls total approximately1.19s.
There were four searches, three loads, eight script calls, one tool-load name
correction and an invalid regional-alias request. These are generic execution
efficiency gaps, not evidence of slow gateway retrieval. Do not optimize them by
hardcoding this question, provider, tool names or a Beijing workflow.

Future lightweight business trials should run from the user's already-open
visible Capstone browser tab so the execution and products can be observed.
The two recorded tasks were submitted through the API and were not repeated
after this preference was stated.

Live tool-renaming deployment, a second actual gateway instance and browser
visual acceptance of this view remain unverified. No new gateway defect remains
open in the tested protocol scope. Enterprise research-mode delivery is separate.
