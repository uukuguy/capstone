# Task 3: Bounded background electrical detail download

Status: implemented and focused checks passed. Parent owns workspace integration,
real-browser acceptance, deployment, shared journal, and recovery records.

## API

`createElectricalViewDownload(manifest, read, onProgress, optionalStore?)` returns
`start()`, `pause()`, and `dispose()`. `start()` returns immediately. Explicit
`start()` resumes after pause or error; failed pages are not retried automatically.
The exported progress type has `state`, aggregate `loaded`/`total`, eight per-stream
counts and completion flags, and optional `error`. No summary stream is requested.
An empty detail manifest completes without network reads.

`ElectricalViewStore` exports `initialize(manifest)`, transactional `commitPage`,
`getRecord(viewRef, stream, id)`, and optional `close()`. The default factory is
`createIndexedDBElectricalViewStore()`. Tests inject a transactional memory fake.
Dispose closes an owned default store; the owner of an injected shared store
controls its lifetime. Cache initialization is also the checkpoint-read API.

## Bounds and admission

- Two concurrent workers, 500 records per request, 30-second page deadline.
- Fixed eight detail streams. Overview rendering and chat have no dependency
  on this transfer. This module owns no agent attempt or busy state.
- Each page must match schema, model, revision, view, snapshot, selection,
  stream, manifest total and count/cursor completion rules. Each stream resumes
  only its committed opaque cursor.
- IndexedDB transactions append unique view/stream/record-ID keys, unique cursor
  history, and checkpoint/counters atomically. A duplicate record or cursor cycle
  rolls back the entire page. All stored pages remain available after failure.
- Cached identity includes the cache format, frozen identity, representation and
  all eight manifest totals. Unknown versions, changed totals, stale checkpoints
  and concurrent checkpoint conflicts fail closed.
- Default budget: 1 GiB of serialized page payload, maximum 4 MiB per page,
  5 million records and 50,000 pages across the cache. Browser storage overhead
  is additional; native quota failures also stop transfer. There is no silent
  in-memory fallback or eviction. The downloader holds only the bounded active
  pages and small per-stream metadata; record IDs and cursor history stay in IDB.
- Pause/dispose abort in-flight reads and transactions. Generation checks suppress
  callbacks and commits from obsolete reads, including readers that resolve late.
  Errors stop both workers and retain the last published committed progress.

## Verification

TDD: downloader test initially failed to import the missing implementation.
The page-deadline test then failed with `running` instead of `error` before the
deadline implementation; it passed afterward.

`npm test -- --run src/electricalViewCache.test.ts src/electricalViewDownload.test.ts src/electricalModelView.test.ts`
passed **55 tests in 2.06 seconds** (3 files). New download/cache coverage includes
delayed nonblocking start, two-worker bound, summary exclusion, pause/abort/exact
cursor resume, old callbacks, explicit error recovery, changed manifest identity,
zero counts, deadlines, duplicate IDs, adjacent/nonadjacent cursor cycles, atomic
page rollback, fresh store restoration, quota failure and unavailable storage.
The cache tests exercise the production store with a small asynchronous IDB driver;
this is not real-browser durability acceptance.

`npm run check` passed. `git diff --check` passed. No dependency was added. No model
call, gateway task, browser page, rebuild, or deployment was started by this worker.

## Remaining acceptance

The parent must connect pause/resume and foreground-navigation priority, keep the
complete overview visible, and verify real IndexedDB persistence and quota/UI
behavior in the existing browser. The cache budget counts serialized page payload,
not browser-specific index and filesystem overhead. Download completion means all
eight declared streams were transferred; it asserts no solver or electrical
readiness and does not validate full cross-stream closure in memory.
