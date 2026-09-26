# Capstone Agent Multimode Host Design

## Decision and scope

`capstone-agent` is the application-level entry point for Capstone. It supports
headless ordered requests, an interactive terminal session, and a local HTTP
service with server-sent events (SSE). All three modes use one application
session lifecycle and the same Kernel turn, context, evidence, and output
contracts. A Web page is a later client of the HTTP service; this work delivers
the service and its contract, not a page.

`grid-agent` remains the stable pandapower compatibility CLI. Its generic
application composition is extracted into the neutral package, and its existing
generic entry points delegate to that code without
changing the two-field compatibility stdout envelope. The mature Pi transport,
tool extension, runtime lock, application runner, and evidence admission paths
are reused. No second agent loop or model tool executor is introduced.

## Alternatives considered

1. **Recommended: neutral host and persistent application workers.** The host
   owns mode adapters, trusted application selection, and session orchestration.
   A selected worker owns its installed Domain Pack, authority, and model
   runtime. This preserves the existing package and evidence boundaries and
   allows pandapower and PyPSA to retain incompatible Python dependencies.
2. Extend `grid-agent` to select all applications. This would make a
   pandapower-owned package the public framework entry point and put PyPSA
   dependencies in its application boundary.
3. Implement another agent runner for each CLI and service mode. This would
   duplicate the tested turn and evidence lifecycle and invite divergent
   behavior between modes.

## Components and ownership

| Unit | Responsibility | Dependency |
| --- | --- | --- |
| Neutral `capstone-agent` host | Fixed worker registry, process routing, session protocol, and CLI/HTTP adapters; no Domain Pack imports | Fixed worker declarations and bounded worker protocol |
| Kernel incremental runner | Prepare once, start one provider transport, consume instructions lazily, commit a turn, expose its admitted answer, finalize once | Existing `AgentApplication`, context, turn and artifact primitives |
| Pandapower worker | Existing application profile, Pi setup, `gridctl` authority, compatibility projection | `grid-agent` and pandapower Domain Pack |
| PyPSA worker | Promoted trusted two-binding application profile, Pi setup, registered model and operations authorities | PyPSA Domain Packs in their own environment |
| HTTP service | Loopback run control and ordered event stream | Neutral host session interface |

The neutral package also takes ownership of the already verified generic Pi
runtime locator and lock handling now under `grid-agent`; the compatibility
package retains forwarding imports. Worker declarations supply each
application's Profile factory and runtime paths explicitly. This avoids a
neutral package importing `grid-agent`, and avoids a PyPSA worker depending on
the pandapower distribution.

The host registry is source-defined and closed. It maps application IDs to
fixed worker commands and environments. The worker independently resolves its
own registered Application Profile. The host never imports a Domain Pack or
an authority. Requests cannot supply an executable,
module import, authority endpoint, tool name, filesystem path to read, or
Domain Pack selection. The model still sees only capabilities published by the
selected application profile.

The process protocol is bounded JSON lines over the worker's stdin and stdout.
The host sends `open`, `turn`, `close`, and `evidence` messages; the worker sends
`ready`, `progress`, `answer_committed`, `completed`, `evidence`, and `failed`
messages. The worker is persistent for exactly one session. Every message has
a session ID and monotonic sequence. The host validates type and size before
relaying it; it does not parse domain payloads to make business conclusions.
Stderr remains diagnostic. No HTTP server or generic shell runs inside a
Domain Pack or Kernel process.

## One session across three modes

A session has one application ID, one run ID, one prepared application, one
current-run authority set, one provider transport, and sequential turns. The
state machine is `created -> ready -> executing -> ready -> closing -> completed`
or `failed`. Only one instruction may execute at a time. Closing finalizes the
report and composite output, then releases the provider and authorities. A
worker crash yields `failed`; the host never synthesizes a successful answer.

The existing `AgentApplication.run(ApplicationRequest(...questions))` stays a
compatible headless entry. Its turn loop is refactored behind one incremental
instruction-source API that can block until the next instruction or close.
`run()` supplies the existing fixed tuple through that API. This avoids
restarting the provider or creating a new run for each instruction. The already
tested preflight, invocation projection,
answer admission, turn commit, report publication, and cleanup remain the
single execution path. The worker emits an answer only after commit and can
then wait for the next instruction. The final input question list and question
count are recorded from accepted instructions. Turn start already durably
records the instruction; the incremental context input list is updated through
a Kernel-owned transition. A closed source finalizes the run.

- **Headless:** `capstone-agent run --request <json>` submits a validated
  ordered list, waits for final output, writes one JSON object to stdout, and
  streams progress to stderr. The existing `capstone-client-request/1.0` and
  `capstone-client-result/1.0` remain accepted for current callers.
- **Interactive:** `capstone-agent chat --application <id>` creates one session;
  each entered line is submitted after the preceding answer, and the answer
  plus admitted references are displayed immediately. An explicit exit/EOF
  closes the run. A scripted demo accepts only its registered instruction
  sequence; arbitrary new tasks require the normal Provider route.
- **Server:** `capstone-agent serve` exposes session creation, one-turn submit,
  close, status/result, and event streaming. It uses the same host and worker
  session interface as the two CLIs.

## HTTP and event contract

The local API is versioned under `/api/v1`:

| Operation | Result |
| --- | --- |
| `POST /sessions` | Select registered application, mode and optional registered case; return opaque session ID and state |
| `POST /sessions/{id}/turns` | Accept one nonempty instruction; return ordinal and accepted status; reject overlapping execution |
| `POST /sessions/{id}/close` | Stop accepting turns and finalize the run |
| `GET /sessions/{id}` | Return state, run ID, accepted and completed counts, latest safe error code |
| `GET /sessions/{id}/events?after=<sequence>` | SSE replay from a monotonic cursor, then live progress, committed answer, failure, or completion events |
| `GET /sessions/{id}/result` | Return final composite/application result only after completion |
| `GET /sessions/{id}/turns/{ordinal}` | Return committed answer and admitted result/evidence references for that turn |
| `GET /sessions/{id}/evidence?ref=<opaque>` | Return a bounded read-only projection for a current-run admitted reference |

SSE events have a stable schema, session ID, sequence, event kind, and bounded
payload. Answer events are emitted only after the Kernel turn commits. Progress
events are observational and cannot veto an answer. Reconnection with `after`
replays retained events without starting another run. At minimum, events and
turn/result metadata remain available while the server process lives; run
artifacts remain on disk under the existing ignored `runs/` directory. Server
restart recovery of an active session is outside this scope and reports it as
interrupted, never completed.

The evidence endpoint asks the selected worker to resolve an exact admitted
reference in that session's run. The host never reads a caller-selected file
or interprets a Domain Pack result. The server binds only to loopback, checks
host and origin, requires `Authorization: Bearer <operator-token>` for every
route, uses a bounded request and
event size, and returns sanitized errors. The token is stored in ignored
operator state with restrictive permissions and is never put in a URL, answer,
event, or log. Evidence reads resolve exact references through current-run
registries; they do not accept a path from the caller. The service exposes no
generic filesystem, subprocess, Python, or raw authority operation.

## Application parity and limits

Pandapower and PyPSA use the same generic `core` turn and evidence machinery.
Each retains its own Domain Pack output contract and optional presentation.
The PyPSA two-binding assembly is promoted from the acceptance script to a
trusted application registration. Its deterministic three-case provider stays
as a regression/demo route; normal Pi/LLM composition is a separate route
using the same registered profile and allowlisted tools. Local tests do not
invoke a billable Provider. The existing `grid-agent` compatibility commands
and stdout behavior continue to work.

## Acceptance

1. A fake provider proves that two interactive instructions share one run,
   provider start/stop, context, and ordered answer/evidence commits; a
   headless request with the same instructions follows the same path.
2. The local HTTP service proves session creation, sequential turn submission,
   SSE replay, close, final result, current-run evidence lookup, rejected
   concurrent turns, and sanitized worker failure.
3. Registered pandapower and PyPSA scripted demos complete through the neutral
   host with real authority results and current-run references. The pandapower
   compatibility CLI still emits exactly its original stdout envelope.
4. The PyPSA application profile can be selected by the generic Pi route in
   its own environment; fake Pi proves tool exposure and session wiring.
   Live Provider behavior is reported as unverified until explicitly
   authorized and run.
5. Focused tests and repository gates `make doctor`, `make test`,
   `make test-e2e`, and `make validate` pass. README files and the runbook show
   all three supported modes and the API contract.
