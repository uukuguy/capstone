# Service-bus execution records

Source: `eb481485bb21ce0b36d7fdd8ba53f0218e5be9ab`, branch
`uukuguy/ppt-template-library-20261110`. Implemented and verified locally;
dky3-dev deployment and bounded acceptance passed. Not merged into dev. No new CI run.

## Accepted scope

The user requires service-bus statistics in the execution-process window title
bar, with per-tool details. Only `provenance.service_bus_calls` with
`scope=current_tool_call` is displayed and aggregated. The client ignores
`data.service_bus_calls` job accumulation. No background-job monitor is added.

The adapter issues bounded statistics in the host's immutable observation receipt.
The host verifies that receipt before it emits public metadata. Existing events
save and restore the same values, including business-error and child-tool events.
The UI deduplicates tool-call records and excludes host-marked historical reuse.
Unknown is distinct from zero. Full attempt counters do not use detail-row length;
details are limited to the latest ten. Counts mean bridge attempts, not database
executions. Source-duration sums include network/queue time and overlapping calls.

## Live contract and bounded local trial

三区研发 instance `0c266ac6-bf86-4137-ab7c-0e283331ab1f` publishes 14 business
and 5 platform tools. Catalog revision:
`fe9077d7fd55dd2472c5b7666ca46f9e946ed4f8f23b438fc0d126ff0e5b71a3`.
Contract and zero-source probe: ignored `runs/2026-11-10-gateway-service-bus/`.

The first model trial completed28.90s and exposed a real propagation defect:
delegated_runtime discarded the host's statistics. It is retained as a failed
acceptance, thread `thr_ef754df5cd25910032ad`. A failing persistence regression
preceded fix `f3d1f5cf`.

The corrected normal task `thr_d380ead17af9fe8e21e1` completed24.90s. It made
one source directory query, types/交流线路, limit1, page1, source access; it did
not continue pages, read measurement/business records, retry or launch a job.
The published current-call receipt records one attempt, one response, no
transport/declared error and69.339ms. The separate discovery tool supplies no
counter and stays unknown. The title therefore shows `服务总线 ≥ 1 次`
with one tool's statistics unavailable. Source service/method/table, elapsed
time, page, returned rows and request ID are visible per tool.

Browser checks reused the existing Capstone tab. The process-window title and
tool details were inspected; full page reload retained the same count. Screenshots
and event receipts: ignored `.capstone-agent/service-bus-live-20261110/`.
The bounded trial followed current tool contracts without redundant source reads;
it does not justify a new fixed initialization sequence or business-name routing.
No inference policy change or broad performance claim is made.

## Verification and deployment

Gateway/relay/host/graph/transport295 checks pass,32 environment checks skip.
Application persistence/diagnostics99 pass. App parser, title, replay, call-trace
and graph323 pass. Scoped types pass. The prepared joint macOS gate includes
these direct consumers; governance256 pass/3 skip. CI remains unapproved.

local-dev uses the canonical rebuilt candidate, API/three-worker image
`f8488c5b5e927a11bf79c50c620c013dc56a41d212ac55da8f0a39637418a95f`, native
`382a14ced31d344e3a2e4301aca669e0bad8a5432a1f01709ebfd2cf0f18d922`.
PPT generation on this same source completed33.81s with four verified products.

dky3-dev images have exact eb481485 source labels. Native PDF smoke and275
canonical runtime-input byte comparisons pass. The remote build reused installed
dependency images and an offline amd64 LibreOffice package bundle. APT local-file
installation, executable-mode staging and unavailable registry resolution each
failed before activation; final recipes use the bounded offline package set,
canonical executable permissions and installed App base. Failed build logs remain.
This is a scoped development image update, not clean-image/release acceptance.
Activation preserves the old images, protected configuration and a PostgreSQL dump.
All four remote roles are healthy and carry the exact source label. API and worker
share image `1582f4266b7d`; native `3f84382d948c`, App `405f4258bfda`. RootFS
layer counts are108/41/20. Both stages pass458 backend and275 native source-file
byte checks. Protected credentials, gateway selection, existing data and original
model defaults were retained. Other environments were not updated.

Remote task `thr_dcac776c667066f52c1f` completed89.41s, including one current-call
source attempt59.346ms and actual State Grid template-tool generation. Four
downloads, the complete source/PPTX/PDF receipt and two PDF pages pass; both pages
were visually inspected. Browser reload retains `服务总线 1 次`; the process title
and exact dky3-dev App source were checked. Opening the action with the pointer
first hit the existing footer overlay; the keyboard path opened the process window.
That existing interaction issue remains separate polish, not a statistics failure.

[Public verification receipt](receipts/2026-11-10-dky3-dev-eb481485.json).
Annotated acceptance tag: `dky3-dev-20261110-1729-eb481485`, exact deployed source
eb481485. CI approval and dev PR integration remain separate next steps.
