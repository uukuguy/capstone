# Capstone App and Portable Session Runtime Design

## Decision and first release

Build a professional operator App for the registered pandapower and PyPSA
three-turn demonstrations. The first release is for one internal operator. A
normal Provider session remains an explicit later action; merely opening the
App or a case never sends a billable model request. The browser sees only
application-owned catalog data, committed answers, bounded progress, report
content, and references admitted for the current run.

The same frontend source and versioned `/api/v1` contract run locally and with
Vercel hosting. The same backend image starts in `api` or `worker` mode locally,
on Cloud Run, or on Railway. Platform configuration chooses connection strings,
secrets, and object storage; it does not select another agent loop, result
schema, or evidence rule.

## Alternatives considered

1. **Selected: API plus durable session worker.** A web process accepts bounded
   commands and serves persisted events. A worker owns the existing persistent
   `WorkerSession` and application subprocess. PostgreSQL stores session state,
   ordered commands and events. An artifact store keeps the completed report
   and admitted evidence projections. This permits API instances and stream
   reconnects without assuming that later requests reach the worker instance.
2. A single web process with an attached volume is smaller but cannot safely
   add replicas and loses active session state on instance replacement.
3. Separate Cloud Run and Railway execution implementations would duplicate
   admission and recovery behavior, weakening local acceptance.

## Boundaries and data flow

```text
Vercel or local Vite App
  -> authenticated /api/v1 (catalog, commands, status, SSE, result, report, evidence)
  -> PostgreSQL session/event/command ledger
  -> Capstone worker service -> registered pandapower or PyPSA application worker
  -> selected Domain Pack -> registered authority
  -> admitted answer/result/evidence -> ledger and artifact store -> App
```

The `capstone-agent` host owns API orchestration, operator authentication,
session state, and the fixed worker registry. The worker invokes the existing
`WorkerSession`; it does not implement a second agent loop. `grid-agent` and
`pypsa-agent` remain the application workers in separate pinned Python
environments. The Kernel remains domain neutral; Domain Packs and their
authorities remain the only source of domain results and current-run evidence.
The browser never receives a raw simulator object, network file, local path,
credential, or unadmitted reference.

### Session lifecycle

The API records a new session and returns an opaque ID. A worker claims it,
opens the registered application once, and owns its sequential turns until
close. Commands have a per-session ordinal and unique ID. Only one turn may be
in flight. The worker stores each validated frame with its monotonic event
sequence before readers see it. A reconnect requests events after the last
seen sequence; duplicate delivery does not create a new turn.

An interrupted worker lease marks an active run `interrupted`. The first
release does not silently restart an active model session or label an
interrupted run completed. Committed answers and verified artifacts already
persisted remain readable. A completed run is readable after an API or worker
restart. The command ledger records accepted instructions and prevents a
replayed HTTP request from submitting an extra turn.

PostgreSQL is used in local Compose, Cloud Run and Railway configurations.
Artifacts use one bounded `ArtifactStore` contract: a local S3-compatible
store for development, Google Cloud Storage on Cloud Run, and a Railway bucket
on Railway. Objects are keyed by server-created run and artifact IDs; callers
never supply an object key. Report text is a presentation artifact, while
evidence reads return only the selected worker's admitted and verified
projection. The store retains hashes and MIME types and limits response size.

### Public API

Existing `/api/v1/sessions` routes remain the logical contract. Add:

| Route | Response |
| --- | --- |
| `GET /api/v1/catalog` | Registered applications and runnable case cards, bounded titles, descriptions, and ordered demo instructions |
| `GET /api/v1/sessions/{id}/report` | Completed or checkpointed rendered report, with no filesystem path |
| `GET /health/ready` | Dependency-aware API readiness without secret or run data |

Session creation, turn submission, close, status, events, result, committed
turns and evidence keep their versioned meanings. All run reads check the
operator identity and exact session; reports and evidence remain associated
with one current run. SSE frames retain event sequence IDs and 15-second
heartbeats. Browser `fetch()` uses the same authorization header for requests
and SSE, parses bounded frames, reconnects with `after`, and checks status if
the stream cannot be resumed. Error codes are safe and actionable; progress
remains observational and cannot veto a valid answer.

### Access and configuration

The first release has one internal operator credential. Local development
continues to use ignored project-owned token state. Hosted services receive
the credential from their secret manager or environment; it is not placed in
the frontend bundle, URL, logs, result, artifact or repository. The App asks
the operator to enter it and keeps it in memory for that tab only. A future
team identity provider implements the same principal-to-session check without
changing the application, worker, or evidence contract.

The API has explicit allowed Host and Origin values per environment. Local
development and Vercel both call the same `/api/v1` paths; the frontend's API
origin is configured at build or runtime, never hardcoded to a provider.
Cloud Run and Railway set the listening host/port through environment
configuration. Provider credentials stay only in backend secret state and
reach only the selected application worker.

## Operator experience

The App is a separate React/TypeScript/Vite package, not an execution mode of
the read-only trajectory workbench. The first viewport is a working surface:
application and case selection at left, the ordered instruction/answer
timeline in the center, and a compact run status and evidence summary at
right. Report and evidence detail open without discarding the current turn.
The selected case displays its model origin, scenario assumption and
interpretation boundary from its registered presentation metadata. Numerical
values appear only after a current-run result arrives.

Visual direction: a restrained engineering console with deep slate surfaces,
warm neutral typography, one muted cyan interaction accent, clear numerical
hierarchy, and precise spacing. Dense data remains readable; decoration does
not compete with evidence. Desktop uses a three-column working layout;
smaller screens stack catalog, active turn and detail in that priority. Each
control has keyboard focus, semantic labels and visible loading, empty,
failed, interrupted and completed states. No marketing hero precedes the
primary action.

The default flow is choose a registered three-turn case, inspect its exact
instructions, start one session, and submit each turn in order. The operator
can pause between turns and inspect the committed answer and admitted refs.
After close, the result, report and evidence remain available. Provider mode
is a separate, clearly labelled route; it is not launched by case selection.

## Portable deployment topology

| Environment | Frontend | API | Worker | State/artifacts |
| --- | --- | --- | --- | --- |
| Local | Vite | Same backend image, `api` | Same image, `worker` | Compose PostgreSQL and S3-compatible object store |
| Cloud Run + Vercel | Vercel static App | Cloud Run service | Cloud Run worker pool | Managed PostgreSQL and Google Cloud Storage |
| Railway + Vercel | Vercel static App | Railway Web service | Railway worker service | Railway PostgreSQL and private bucket |

Both cloud targets use the same image digest for their API and worker roles.
Each image contains both pinned application environments and checked official
PyPSA model assets. Build-time asset verification is mandatory; an agent turn
never downloads a model. Deployment configuration supplies only role, port,
database, object-store and secret bindings. No deployment is performed as
part of this local implementation.

Cloud Run streaming requests can reconnect after its request timeout and may
reach another instance; Railway SSE has a bounded lifetime. Neither platform
is treated as an affinity or filesystem authority. The durable event cursor
and artifact store make the browser flow the same in local and hosted setups.

## Work packages and acceptance

1. **Durable host contract:** add a session ledger and API/worker split behind
   the existing application workers. Exercise sequential turns, cursor replay,
   interruption and restart reads with local PostgreSQL and artifact storage.
2. **App presentation:** implement catalog, timeline, report and evidence
   views against the versioned API. Validate both registered three-turn cases
   through the real local host with no Provider request. Validate keyboard and
   narrow-screen states with focused frontend tests.
3. **Portable packaging:** build one image with two roles and a local Compose
   topology. Provide Cloud Run, Railway and Vercel deployment templates and
   configuration documentation; perform dry-run/build validation locally.
   Actual cloud deployment and billed Provider validation occur in later
   separately authorized work.

The repository's focused tests and supported offline gates must preserve the
grid CLI's exact stdout envelope, simulator boundary and current-run evidence
admission. The user's staged `.codex/config.toml` remains outside these work
packages.

## Platform references

- [Cloud Run worker pools](https://docs.cloud.google.com/run/docs/deploy-worker-pools)
- [Cloud Run request timeout and reconnect guidance](https://docs.cloud.google.com/run/docs/configuring/request-timeout)
- [Railway background workers](https://docs.railway.com/guides/cron-workers-queues)
- [Railway SSE lifetime](https://docs.railway.com/guides/sse-vs-websockets)
- [Railway private buckets](https://docs.railway.com/storage-buckets)
- [Vercel external-origin rewrites](https://vercel.com/docs/routing/rewrites)
