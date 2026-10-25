# Enterprise research through production-data MCP

Status: real model functional acceptance passed on runtime source 2f9c6b56.
Runtime22e61786 includes the later type correction and passed the final rebuild,
source/permission checks and retained-product browser recovery. Test-only29e43835
does not change that running source.
Dev integration and required PR checks are separate. No cloud/demo promotion.

PR #58 first failed type checks; correction015112a7 passes Pyright and105focused
checks. The next CI run40138770412 failed one authorization test after22m36s:
2007agent checks passed. A simulated11-second server startup reproduced the
failure. Starting the test grant after host/server/client setup fixes that case
without extending production authorization. The delayed-start check and8gateway
relay tests pass. User requested lighter development CI;60scope/contract tests
and362native SDK tests pass for the bounded native-runtime gate. Its remote
duration is pending. Independent review could not start because its configured
model is unavailable; no independent approval is claimed.
The following CI attempts exposed macOS single-child fixture cleanup and a
cancelled-request assertion that preceded handler lease release. Existing macOS
cleanup now covers the RPC fixture module; cancellation waits for completed
release.54checks pass under simulated group-signal denial, and delayed handler
release passes. Production process-group termination is unchanged.

## Delivered scope

Enterprise-research uses application-admitted data-gateway tools through a fixed
host connection and task-bound relay. The observed catalog admits 41 data tools.
The gateway owns backend selection. Six model operations remain excluded;
professional Authority and local PowerMCP contracts remain separate.

Accepted catalogs bind tool schemas and hashes. Calls validate arguments, preserve
the full structured result, and issue task/call/result receipts before research
source admission. Actual isolated research nodes receive the same tool catalog.
Revocation cancels an inflight exchange; failed/unknown calls are not replayed.

## Credential isolation correction

The first actual setuid10000 probe could open a mode0600 host-bound connection
file even with zero effective capabilities. Mode inspection alone was therefore
insufficient in this local file-sharing environment. No credential bytes were
printed and no model task had started. The native service was stopped for repair.

The connection mount now resides beneath image-native /run/capstone-private,
owned by root with mode0700. Startup checks the parent and fixed child path.
After the canonical rebuild, actual setuid10000 open was refused while the host
successfully published the 41 admitted gateway tools. The connection file stays
in its original operator directory; it is not copied into a task or Git.

## Focused checks

- 14 gateway checks: real authenticated HTTP MCP, schemas/admission, public error
  codes, actual pinned Pi SDK child call, host receipts, inflight revocation and
  protected-parent configuration.
- 102 focused host checks passed in10.86s, including the gateway checks; do not
  add these counts as independent suites. Existing host and graph guards are
  included. Another 62 SDK/research checks passed.
- Existing native graph/runner checks passed after managed Pi installation.
  Fourteen ordinary research/conversation checks passed with15 platform skips.
  Initial missing-runtime/proxy failures were setup failures, then corrected.
- Package-boundary, link/symlink and doctor checks passed.
- Independent review agent could not launch because of an unavailable configured
  model. Manual boundary review was completed; no independent-review pass claimed.

## Real model execution

The actual local API, workers, native container, configured Provider and MCP
service executed these tasks. Offline scripted-provider checks were not used as
a substitute for these runs.

Thread: thr_1897f293f4778aa394ad. Work: work_933aff1d8c8316ffd4db.

| Case | Attempt | Observed seconds | Gateway calls/errors | Child tool calls/errors | Child model responses | Product records |
| --- | --- | ---: | --- | --- | ---: | ---: |
| Discover, retrieve and analyse a bounded production window | attempt_a064c1744e3f09b5 | 216.411 | 19 / 0 | 33 / 1 | 26 | 6 |
| Management follow-up using saved material in the same Work | attempt_29ca9301923d867a | 58.847 | 0 / 0 | 6 / 0 | 6 | 1 |

Times are observer measurements for these inputs, not comparative performance
baselines. Response counts are child model responses, not total Provider calls.
The one initial producer-return rejection was repaired within the same task;
it was not a gateway failure. All final task outcomes were completed.

The first task discovered the object, metric, window and explicit sources. It
queried native samples and also used prepare_data_query/execute_data_query for a
bounded semantic-table query. Both semantic calls completed without error and
the resulting product retained the query fingerprint and two source rows.
That real execution covers the planned table path; no additional duplicate
table-only model task was run.

Five primary-source CSV strings match the independently obtained gateway samples
exactly, including declared decimal digits. Independent decimal arithmetic
matches the report statistics. The report preserves the window, MW unit, source
selection and quality limits; sources are not merged. The follow-up preserved
the same statistics and unit without new gateway queries.

All published files were downloaded through the public artifact contract and
checked against their saved SHA256. Six first-turn product records include two
retentions of the same JSON bytes; they are not six distinct contents.

## Browser recovery

The real workspace opened the completed conversation and management summary.
After page reload, the selected summary title, content and download action were
restored. The browser download bytes matched the retained artifact hash, and no
horizontal document overflow was observed at the inspected desktop viewport.
The expected v1-to-v2 snapshot negotiation returned409 before successful recovery;
no new UI implementation was required.

## Source and operational receipts

Original acceptance rebuild: /tmp/capstone-gateway-private-rebuild.log,
API/workers e69d4f1b6e56 and native b605fa2b1a6c.
Final rebuild: /tmp/capstone-gateway-final-rebuild.log,
API and all three workers share image87e9bae78f79; native imagef2c3afaf5b5f.
Eight relevant source files in all five roles matched runtime22e61786.
Readiness returned200. The running App serves the actual root checkout and its
unchanged App product source e8bfb5ae. Operator gateway mount selection is retained
in the existing ignored root deploy/local.env, without embedding credentials.
Scoped image/build-cache maintenance ran after the rebuild.
Post-use scoped maintenance also completed. The real management summary remains
selected after reload on the rebuilt services; its download still hashes to
778b135c4f96a7b2f654ff543aa6e78145543a91718882edef5b1251bb0f7927.

Ignored ROOT evidence, not public source-data fixtures:
- outputs/data-gateway-20261025/local-source-verification.json
- outputs/data-gateway-20261025/final-local-source-verification.json
- outputs/data-gateway-20261025/final-browser-recovery-verification.json
- outputs/data-gateway-20261025/direct-query/
- outputs/data-gateway-20261025/real-series-1/
- outputs/data-gateway-20261025/real-followup-1/
- outputs/data-gateway-20261025/numeric-product-verification.json
- outputs/data-gateway-20261025/real-task-metrics.json

Browser screenshot: /tmp/capstone-gateway-real-report.png.
No source rows, operator connection credentials or downloaded model files are
included in this acceptance document.

## Deferred completeness and polish

- The reader-facing JSON explicitly discloses that the model omitted bulky
  per-column semantic echoes. Exact gateway responses remain in host observation
  storage. Direct read-only materialisation of full gateway responses for native
  programs is a later improvement; do not call the assembled product a byte-exact
  full MCP response.
- Reports remain technically verbose, and repeated source discovery/producer
  retention can be reduced later. These do not block the verified task path.
- Eight gateway service families are discoverable; this check does not claim
  production-data coverage of every operation or large-scale load acceptance.
- Unified conversations, model ingestion/calculation and 100k+ graph rendering
  remain later work. The identical calculation SDK versions and WebGL direction
  are recorded in the owning designs.
