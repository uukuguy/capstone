# Railway On-Demand Worker Design

## Decision

For the public demonstration on Railway Hobby, keep the existing API, worker,
PostgreSQL ledger, and artifact contracts. Replace the Railway worker's idle
database polling with a private HTTP wake endpoint. The API sends a bounded,
authenticated wake request after a session is created. It retries while a
session remains pending, so a cold-start 502 does not strand the run. Railway
Serverless may then suspend the worker after all sessions release their leases
and its outbound traffic stops. The first visitor may wait for a cold start.

Local Compose uses the same wake path. Cloud Run worker pools keep their
existing polling mode because they do not expose an HTTP service endpoint.
The selected Domain Pack, current-run evidence, session ledger, and public
`/api/v1` responses are unchanged.

## Alternatives

1. PostgreSQL `LISTEN/NOTIFY` reduces idle queries but a sleeping worker has
   no live connection and cannot be woken by a notification.
2. Combining API and worker in one process makes wakeup simple but weakens the
   existing independent failure and capacity boundaries.
3. **Selected:** the API wakes a private worker HTTP listener. The ledger
   remains the durable queue and authority for ownership; the HTTP request is
   only a hint to check it.

## Lifecycle and failure handling

- The worker accepts `POST /wake` only with a token derived from the shared
  private operator secret. The token is never sent to the App, logged, or
  placed in a URL. The worker service has no public domain.
- On startup and every wake, the worker marks expired leases and claims pending
  sessions. After its final active session exits, it closes ledger connections
  and waits without database traffic. Session threads retain the current lease,
  command, evidence, and idle-timeout behavior while active.
- The API writes the session before waking the worker. Wake failure cannot
  erase or duplicate it. A pending-session status read retries wake with a
  short throttle; worker startup also claims durable pending work.
- Once a worker claims a session, it remains active until close, failure, or
  the existing ten-minute idle timeout. A turn accepted for an active session
  uses the existing command ledger. An interrupted session is never labelled
  complete.
- Railway Serverless is enabled for the App, API, and worker, but not PostgreSQL.
  Measure actual sleep and costs after deployment; network traffic from active
  sessions and external services can delay sleep.

## Acceptance

1. No idle ledger queries after worker startup and no active sessions.
2. Invalid wake credentials cannot activate work.
3. Session creation wakes a sleeping worker; transient wake failure and
   repeated status reads eventually start exactly one session.
4. Existing scripted cases, report, evidence, and recovery tests still pass.
5. Local Compose uses the same wake configuration as Railway; Cloud Run
   remains operable in polling mode.
