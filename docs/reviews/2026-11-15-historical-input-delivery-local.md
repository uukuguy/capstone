# Historical input delivery: local verification

Status: PR117 merged into dev5798dad6 after approved macOS CI43704515136 passed
149seconds on tested source6625c0bb. Actual dev rebuild and existing-tab restore
passed. No cloud/demo update. Product source492b78e2, basee0fc951e.
Owner: capstone-agent/capstone-app; destination: dev.

## Merged dev verification

Actual dev and origin/dev synchronized at5798dad6. Canonical rebuild passed;
API and three workers share image
`sha256:1cd6589b0c8b6194fab93f8c0412275bcecd7cf076ebee142eba6ecd1f7a8eb1`.
The existing real Thread restored after refresh in default Vivaldi/5173 with
App revision5798dad6 and both historical delivery messages. Seven downloads
retained their exact sizes and hashes. No new model run was needed for this
same-product restoration. Scoped cache cleanup modeapply is recorded.

Source branch closed locally and remotely. Root drafts were fully preserved in
stash52561c4cfdc6c1c2ad38c66b5db3706866ea9007. Runtime package paths are clean
on actual dev; only control/documentation closeout remains. Machine receipts:
`runs/historical-input-validation-20261115/ci-43704515136.json`,
`pr117-merged.json`, `postmerge-acceptance.json` and
`postmerge-refreshed-restored.json`. The sections below retain the original
candidate verification; their “not merged” state describes that earlier stage.

## Behavior and boundary

The existing protected resource transfer now calls a delivery recorder only
after exact completion acknowledgement. Frozen resource/source identity and
same-Work ownership are checked. Existing Thread lease checks and transaction
locks protect durable, idempotent public receipts. Persistence failure remains
fatal. The existing execution details restore a receipt as a historical input
delivery; the UI does not claim complete analysis or a product derivation edge.
Explicit product references and range-read receipts keep their own semantics.

## Focused evidence

- Initial missing callback and missing module tests failed before implementation.
- 103 backend checks passed with a real disposable PostgreSQL instance, including
  duplicate receipt recovery and changed-origin rejection. No skipped cases in
  that measured set. App projection/recovery:73 passed; TypeScript passed.
- Added focused `historical-inputs` development gate after reproducing the
  previous broad `shared-agent` classification. Its complete local script passed:
  104 backend/governance checks in3.71s,73 App checks in1.04s, and TypeScript.
  Additional scope classifier checks:123 passed in3.81s. This did not run CI.
- `make setup`, `make install-pi`, `make doctor` and whitespace checks passed in
  the isolated worktree. No authentication state was copied there.

## Local runtime and real task

The root checkout temporarily holds the eight package-file changes from492b78e2
to use its existing protected local runtime. These files match that exact commit;
all pre-existing closeout edits and user data remain. Canonical
`make capstone-local-rebuild` passed. API and three workers use image
`sha256:13a0eec29d8687fe167ef70bfb236c9a31fcaccc4d48d1b365afe124c7e1f773`.
Native executor image:
`sha256:3dc6c0a9bcad588d777a09fd0562eb64e9aa1168fa5ec0537563ac97f3ab9952`.
Image layer counts are62 and37; no Dockerfile layer was added. Scoped cache
maintenance recorded mode`apply` after readiness. Temporary test PostgreSQL was
stopped after checks. Existing default App remains5173.

Real Thread: `thr_f73ead1e6d18cd0e63a7`.

1. First instruction generated simulated CSV and report: total31, one tool,
   two main model responses, displayed7.5s total.
2. Follow-up preserved originals and generated doubled CSV/report: total62,
   four tools, four main model responses, displayed17.9s total. This is a small
   mechanism task, not a performance benchmark or business-grid acceptance.
3. Exactly two durable delivery receipts bind the follow-up to the previous
   attempt's `simulation_report.md` and `simulated_items.csv`.
4. Seven downloaded attempt/file records passed size and SHA256 checks.
   Independent CSV parsing confirmed totals31 and62.
5. The existing Vivaldi Capstone tab shows both receipts in execution details.
   Reload preserved the Thread, both instructions, doubled report and both
   delivery messages. No extra tab was created. Product-source count remains0
   because this was implicit continuation, not explicit product selection.

Ignored evidence: `runs/historical-input-validation-20261115/`, including
`source-identity.json`, `runtime-identity.json`, `all-events.json`,
`delivery-events.json`, `download-verification.json`, `expanded.json` and
`refresh-state.json`. Build log:
`runs/harness-chain-20261115/rebuild-492b78e2.log`.

## Review and remaining acceptance

Source self-review completed. Independent reviewer launch failed because the
agent tool selected an unavailable model; there is no independent review result.
No claim of whole-file analysis, output derivation, service-restart acceptance,
remote scale acceptance or full release acceptance is made.

The product CI and merge above are complete. Next: independently approve the
documentation closeout's focused macOS docs gate before its PR can trigger CI.
The initial one-run approval is exhausted. No second CI has started.
