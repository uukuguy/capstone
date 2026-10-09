# Shared general Pi final code review

Date: 2026-10-09. Reviewed range: `c70bc7e..7f0f174`.

Specification verdict: **PASS** for the delivered local implementation scope.
Code quality verdict: **APPROVE**. No material source finding remains.
Final repository gates and the current-source local rebuild remain root-owned
acceptance steps. This review does not approve a cloud release or real Provider
answer quality.

## Scope

Read the repository contract, framework architecture, approved
[delegation design](../superpowers/specs/2026-10-09-capstone-pi-delegation-design.md),
[implementation plan](../superpowers/plans/2026-10-09-capstone-pi-delegation.md),
and Task 1–4 review records. The review covers contracts, private transport,
native tools, storage, per-goal execution, accepted retry state, hosted wiring,
App controls, documentation, and the local rebuild path.

The executor is separate from the professional worker. Each native task has a
private workspace and UID. Provider credentials remain in the host. General
observations retain their own identity. They do not enter Authority result or
evidence collections. Frozen input, decisions, and task identities prevent
silent general-task repetition during retries.

## Findings and resolution

### P1 — Bound and revoke accepted Provider relay requests — resolved

Location at first review: `packages/capstone-agent/src/capstone_agent/general_pi_server.py:301`.

The relay checks its grant once, then makes an upstream request with a
60-second socket idle timeout. It has no per-task or service request cap, no
absolute task deadline, and no connection shutdown on grant revocation. A
native tool can reuse its grant to start concurrent requests. Accepted requests
can continue after cancellation, task completion, and downstream disconnect.
This can exhaust service capacity and keep Provider work active after the
parent stops.

A local delayed upstream reproduced six concurrent upstream requests from one
grant while the host task cap was one. All six remained active after grant
revocation and downstream disconnect. This used local HTTP only.

Required fix: finite per-task and service relay concurrency, tracked exchanges,
absolute deadlines, and prompt connection shutdown on grant revocation. Cover
request bodies, response headers, streaming reads, and downstream writes.
The first fix draft also needs bounded DNS cleanup. A local blocked resolver
check used a 0.1-second lease and a 1.2-second resolver delay. The lease was
cancelled, but per-request `asyncio.run()` returned after 1.27 seconds because
it waited for resolver executor shutdown. Use a bounded service-owned async
runner so cancellation does not join a blocked resolver for each request.

Resolved in `18b58f7`. The service limits relay requests to 16 total and two
per task. It tracks each deadline and shuts down the downstream socket and
cancels the upstream exchange on revocation. HTTP handlers have a separate
32-request cap. The shared HTTP loop has 64 exchange slots, four DNS slots,
and four write slots. DNS and write work keep their slots until the operating
system operation stops. The control client also uses this loop. Receipt
publication now syncs the parent directory after atomic replacement.

Reviewed the committed patch and its covering checks. The parent reports 70
focused passes, clean changed-module Pyright, and a rebuilt native worker check
for both routes, tools, history, artifacts, and deadline termination. These
unchanged checks were not repeated during review.

### P2 — Accept the service's bounded assistant delta event — resolved

Location at first review: `packages/capstone-agent/src/capstone_agent/delegated_runtime.py:115`.

The service converts native text events to `assistant_delta` with a `text`
field. The application callback accepts `text_delta` or a raw native
`assistantMessageEvent`. The real HTTP path therefore saves only diagnostic
events and does not publish text deltas to the App. The fake executor test uses
raw native events and misses this mismatch.

A local `GeneralPiHost` → `HttpGeneralPiExecutor` → worker check reproduced the
defect for both entry points. Each Attempt completed with the expected final
answer. Each had zero public `assistant_text_delta` events, although it saved
the diagnostic `assistant_delta` event.

Required fix: consume the bounded event shape and test both entry points
through the real private HTTP adapter.

Resolved in `7f0f174`. The application accepts `assistant_delta` and retains
the bounded text-only public projection. Tests cover both entry points through
the real host and HTTP adapter. The parent also reports the pinned native Pi
worker check passing both entry points with public text-delta assertions.

### P2 — Bound the rendered answer to the parent event contract — resolved

Location at first review: `packages/capstone-agent/src/capstone_agent/delegated_runtime.py:280`.

The scheduler joins full child answers without a parent answer or encoded
terminal-event budget. The child result contract permits valid answers that,
alone or in combination, exceed the parent's bounds. Two completed child
answers of 40,000 ASCII bytes each caused the parent to fail with
`runtime_failed`. One completed answer with 40,000 quote characters also
caused that failure: JSON escaping exceeded the Thread event's 64 KiB bound.
Both reproductions used the worker with a local fake executor. Successful
child receipts were present, but no final answer was committed.

Required fix: bound the rendered aggregate against the encoded parent payload,
including its other fields. State clearly when public text is shortened, and
retain the full saved child results. Cover multiple goals, JSON escaping, and
multibyte text.

Resolved in `7f0f174`. Rendering and Harness persistence use the same terminal
payload projection. The budget includes JSON escaping, UTF-8 bytes, admitted
references, diagnostic codes, and result projections, with a 2 KiB reserve.
The visible reply states when text is shortened. Professional text has priority;
if it also needs an excerpt, its full typed receipt is saved in bounded,
hash-bound diagnostic chunks first. Full general results remain saved in the
executor. Metadata-only overflow fails instead of dropping Authority refs.
Repeated projections are deduplicated only when their ID and complete document
match. Conflicting content fails admission.

## Task review follow-up

Task 3 identified two separate P2 defects: missing admitted business dependency
output and the dropped professional network projection hook. Both are resolved
in `7f0f174` and were checked in this final review.

Business dependencies use immutable application receipts. The prepared goal
receives admitted text, refs, projections, and filtered tool receipts. The
boundary checks the current Attempt, model, resolved source goal, and selected
capability scope. The selected Domain Pack still verifies current-run refs;
historical messages and general observations do not carry these dependencies.
Foreign and untyped receipts are rejected. Cross-profile access needs a separate
application grant and is refused by this scoped contract.

Professional network hooks run while each child context is still held. The
wrapper retains a bounded, normalized projection for the claimed model and
admitted refs. It also preserves the unavailable event. General-only tasks do
not enable this hook. Task 1, Task 2, and Task 4 retain their passing reviews.

## Evidence and limits

Only the focused local reproductions above were run during this review. The
committed fix and its covering tests were read. The Task 3 fix report records
153 focused passes, one optional PostgreSQL skip, and zero changed-source
Pyright errors. It includes actual payload-size checks with projection overhead,
full professional receipt recovery, all 128 refs retained on metadata overflow,
and identical versus conflicting projection reuse. The parent reports the real
native worker stream check passing in 7.53 seconds. Previously reported suites
were not repeated. No paid Provider call, remote action, source edit, user-data
change, or branch mutation was made by this reviewer.

Remaining live acceptance is separate from code approval: real Provider answer
quality, external-source quality, cost, and latency need authorized checks. The
relay supports API-key chat-completions transports; Anthropic and OAuth are
rejected at startup. Native costs remain unknown. Tool observations prove
which output was recorded, not that an external document is true. The App has
no product download control. Private storage retains content for a finite
period and keeps replay tombstones; full capacity requires operator action.
Automatic external-data mapping into business models and skills/MCP installation
remain separate work. External observations alone grant no model change.
The public network view contains the last prepared business projection.
Cloud deployment and acceptance are outside this local delivery.
