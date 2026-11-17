# Durable instruction admission

Owner: capstone-agent, with capstone-app consumer and native runtime adapter.
Branch: feat/durable-instruction-admission-20261118. Destination: dev c8de9924.
Status: queue, native transport and App integration implemented; real local browser
acceptance passed. Final clean-source rebuild and dev integration remain pending.
Parent: [accepted intervention design](../specs/2026-11-17-conversation-intervention-design.md).

## Confirmed implementation seams

- `thread_work.py` currently applies send_message as work_message and immediately
  queues execution. project_work reports attempt_in_progress for queued/running work.
- `thread_service.py` has separate in-memory and PostgreSQL command implementations;
  admission guarantees must be tested on both, including concurrent transactions.
- `harness.py` heartbeat checks lease ownership and cancellation, but does not admit
  supplementary instructions. Event persistence alone does not establish consumption.
- `resources/general-sdk.mjs` reads the initial stdin frame, awaits runSettledPrompt,
  then closes input. It cannot currently receive a steering frame during that await.
  Existing managed-subagents validate the SDK steer method, but this does not prove
  a durable host-to-session intervention channel is implemented.

## Implementation boundary

Persist a pending instruction under existing Thread/Work ownership, with immutable
text, submission identity, target execution and sequence. Acknowledged storage and
actual context admission are separate events. Do not append supplementary input
to a mutable initial prompt or admit it twice after a lease change.

First implement and test server submission, ordered retrieval, withdrawal and exact
worker acknowledgement. Frozen resource selection and authorization apply to each
instruction. Stop suspends automatic consumption without deleting pending text.
Then add a bounded native transport for steering frames and correlate SDK consumption
with a persisted receipt. A transport write alone is not an admission receipt.

Tests must exercise duplicate request recovery, concurrent withdrawal/admission,
worker lease loss, stop with pending instructions and terminal/admission races.
Only then enable execution-time sending in the App and add the compact status strip.
Real acceptance requires a changed next action during a running task and recovery
after browser refresh. Existing product bytes and prior process records must survive.

Current implementation: durable pending/delivering/admitted/withdrawn states, explicit
delivery_unknown at uncertain terminal boundaries, leased reservation and consumption
events, supported-runtime gating, text-only supplements under existing grants, compact
status strip and independent send/stop. Existing old/professional executors retain
their prior submission path. Real dedicated PostgreSQL tests cover reservation races,
restart, stop/resume and stale leases. Native transport uses owned-task authority.

SDK message_end consumption and negotiated-capacity corrections are implemented.
Real thread thr_6587521a9aa46fe3f111 changed the saved artifact after a supplement
arrived during a slow tool. Refresh restored the receipt. Cancellation raced delivery
and retained delivery_unknown without auto replay; a later execution admitted a new
instruction and recalled an exact unique prior constraint.390px reader-source navigation
kept the composer within viewport. Evidence runs/durable-instruction-admission-20261118/
browser-validation.json. File marker matched; terminal newline means it was not a
byte-exact compliance proof. Pending-before-reservation stop is covered by real PG tests.

401 backend,123 scope and194 App checks passed; review-driven followups add context
and capacity coverage. Next finish clean-source rebuild, scoped CI and realdev entry.
Do not report the overall goal complete from unit tests alone. After this gate, integrate
through scoped macOS CI and continue intent-only Mission planning and equipment.
