# Resource projection verification

The approved architecture improvement plan adds a PostgreSQL resource read model.
Thread events remain authoritative. Three additive tables store a projection
cursor, upload metadata and indexed parts. The cursor and projection rows commit
together. Deleting a cursor cascades only its derived rows; the next read rebuilds
from retained events. Old writers can continue to append events. No existing
event, resource object or user data is migrated or deleted.

Projection recovery reads at most 256 events per database fetch. Transactions
always acquire the Thread row before the projection cursor. Object storage I/O
stays outside these transactions. Part admission reads one indexed part; its
HTTP size check reads only metadata. Listing resources does not load part bodies.
Upload quotas still count published resources and release cancelled reservations.

## Evidence

- 87 focused Python checks passed, including real PostgreSQL and memory paths,
  in 10.05 seconds. Coverage includes cancellation during storage, late duplicate
  acknowledgement, hash checks, attachment adoption, projection rebuild and
  projection/event rollback. One existing Starlette deprecation warning remains.
- Real loopback HTTP, isolated PostgreSQL 16 and temporary disk object adapter:
  uploaded and downloaded 1,077,936,128 bytes in 257 bounded parts. SHA-256:
  `075dd52c81f01dbfa58c6f9d886dce4f3648184bf243e427a99d042c00afe244`.
- Upload: 12.251 seconds; whole-file verification: 0.986 seconds;
  streamed download: 1.030 seconds. First/last 32 part means: 49.744/45.070 ms.
- Peak process RSS: 151,896,064 bytes. Client and API ran in the same process;
  this is not a measurement of the deployed API alone. Temporary files and the
  test Thread were removed after verification.
- Probe script: `/tmp/capstone_resource_scale_probe.py` on the development host.

## Runtime and pagination verification (13:38)

- Candidate source `4e694995` completed the canonical local rebuild. API and all
  three workers use image
  `sha256:53682f0639608ecda03cdb3d5bcee97bedfe1e2dcca19cc986c61e41696a92e3`.
  Readiness returned ready. The existing Vite App remains reachable.
- Scoped cache maintenance completed in apply mode. Receipt:
  candidate `.capstone-agent/cache-maintenance-20261113-133747-3896.log`.
- A separate real loopback HTTP probe uploaded 205 four-byte resources into
  isolated PostgreSQL 16. Pagination returned 100, 100 and 5 entries in exact
  publication order, with no omissions or duplicates. Page times were 33.010,
  32.273 and 24.937 ms. Upload time was 21.595 seconds.
- A directory change made the previous cursor return HTTP 409. Probe:
  `/tmp/capstone_resource_pages_probe.py`. Its test Thread was removed.
  This test uses a memory object adapter and does not measure production storage.
- Browser runtime discovery returned no connected browser. New UI behavior and
  control graph visual acceptance remain unverified.

## Real task path on rebuilt source

Thread `thr_4ccec34faf87ce0cd4d5` used the configured deepseek-flash model
and isolated native tools. Its 20-byte CSV upload took 156.644 ms. The first
instruction opened the resource, calculated 3 + 7 and saved
`architecture-result.txt`; the next instruction opened that saved result
and saved `architecture-followup.txt`. Completion polling measured 10.199
and 10.214 seconds (two-second polling resolution).

Both published products were downloaded through their API URLs. Their bytes
matched `total=10` and `previous_total=10` with trailing newlines, and their
SHA-256 values matched the published records. A fresh snapshot and full event
page retained the completed Work and both products. This verifies API recovery,
not a browser refresh. These are general-task products, not Authority evidence.
The existing PDF resource also remained visible through the paginated runtime API.

Tool dispatch receipts measured resource-open calls at 294.709 and 294.343 ms;
the three shell calls took 21.567, 5.448 and 5.058 ms. Each instruction used three
model responses. Reported total token counts were 119,261 and 121,241, including
85,760 and 87,040 cache-read tokens. Each response carried roughly 40,000 input
tokens including cache. This is a context-size investigation target; do not
infer billing cost or attribute all remaining wall time to model inference.
No further model repetition is needed before identifying the context sources.
Local receipt: `/tmp/capstone-runtime-improvements-20261113.json`.

## Follow-on architecture slices

Candidate `9aa3e8f1` extracts shared terminal preparation for the memory and
PostgreSQL stores. Four terminal phases, immutable preparation, durable Work
state, result delivery and rejection of repeated completion are covered.
138 focused tests passed in one process in 23.67 seconds. Initial parallel
runs against the same fixture database caused DDL deadlock and duplicate fixed
run IDs; those runs failed and are not acceptance. Sequential verification passed.

The following documentation commit `d24f2920` was rebuilt locally. API and all
three workers use `sha256:7d2af407ec90b0e75de5cd9cb933fb0bd6cc2809771cbd84da2ebc5b5c8d1a6c`.
Readiness passed. Scoped cleanup receipt:
`.capstone-agent/cache-maintenance-20261113-134935-24072.log`.
The earlier real model result remains evidence for source `4e694995`.

Candidate `f5e76b96` moves published pandapower tool catalog/execution, executor
cache and receipt ownership into `pandapower_domain.tool_service`. The application
retains management-context validation and selects a bounded workspace identity.
The Pack imports neither the application host nor the old CLI package.
21 boundary/lifecycle checks passed in 0.53 seconds; 51 execution/output/profile/
hosted-consumer checks passed in 76.58 seconds. Existing pandapower deprecation
warnings remain. This is one ownership slice; formal application composition
and historical compatibility modules have not all migrated. Runtime rebuild
for this slice passed at documentation source `8b0c383f`: API and three workers
share `sha256:510687af1863d7dfcb010d8f04cce2e5ce6bab26ebc64fe8fa68e30d0921156c`.
The installed worker used the Pack implementation to publish its 31-tool catalog
and execute `grid_environment_describe` through the actual Authority process.
The saved execution receipt exactly matched the response and recorded process
start, end and capacity release. The isolated temporary workspace was removed.
Scoped cleanup receipt ends `135652-47338.log`.

## Long-history measurement and selective replay

An isolated PostgreSQL probe appended 20,000 unrelated runtime events, each with
a 4,096-byte text payload, after a verified resource. It removed only the derived
projection cursor and measured reconstruction from retained events. Original
source `8b0c383f` took 753.435 ms cold and 21.854 ms warm.

Candidate `afea4e5a` uses the same static resource-event predicate as the existing
partial index. It reads only relevant event bodies and advances the projection
cursor to the locked Thread head, including an irrelevant tail. The same probe
then took 35.017 ms cold and 30.255 ms warm. Both returned the identical resource
page. These are single local measurements, not latency percentiles or a cloud
performance promise. The synthetic Thread was removed after each run.

The added regression first failed because unrelated events entered projection
replay. All 29 resource tests then passed, including PostgreSQL rollback/recovery.
Probe: `/tmp/capstone_resource_history_probe.py`. The selective-replay change
is not yet in the running `8b0c383f` image.

## Open acceptance

This is local implementation evidence, not cloud acceptance or a performance
comparison with the previous version. S3/GCS adapters,
long-history first-rebuild latency, browser checks,
dev integration remain open. The in-memory adapter
still uses event replay. Full resource scale acceptance remains open.
