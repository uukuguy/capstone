# Unified conversation and systematic diagnosis

Status: implementation, affected offline checks, canonical local rebuild and real
model/browser acceptance passed. PR60 merged into dev at6f9ca536. This receipt
does not claim cloud or user-trial deployment acceptance.

## Implemented slice

- Current graph-capable native hosts expose shared organization to general and
  research entry presets. Historical bindings remain exact; no keyword routing
  or client-selected execution endpoint is added.
- Version2 model workspace commands use the existing registered catalog, family
  availability, cursor and exact-request receipt checks. An initially model-free
  conversation can open a registered model and continue the same Work.
- Actual execution records select thinking status, visible general tool calls,
  or business task purposes and progress. The existing conversation, composer,
  process reader and task components remain in use. Public error/aborted model
  responses retain their status. Private reasoning is never inferred or shown.
- Built-in guide and record tools support authorized native parent/child sessions.
  The host persists diagnostic records and immutable request receipts outside
  model-writable state. Reported hypotheses are not Authority facts.
- Scoped budgets permit justified repeats, retain failed and unknown outcomes,
  prevent display-name budget resets and block exhausted selections before effects.
  Independent actions and limited final answers remain possible. Repeated ignored
  blocked selections reach a bounded settlement failure.

Research advisory findings remain recorded gaps. Professional calculation
admission remains with its registered Pack and Authority. Neither diagnosis nor
the view selects which numerical claims are valid.

## Focused and development verification

Counts overlap and must not be added as independent coverage.

| Scope | Result | Measured duration |
| --- | --- | --- |
| Independent PostgreSQL, profiles and normal conversation/model workspace |73passed|12.19s|
| Combined diagnosis, server, executor, profile, conversation and model workspace |187passed|19.31s|
| Shared backend, with independent test PostgreSQL |2207passed,2skipped|148.34s|
| Kernel |658passed|6.46s|
| pandapower Pack |144passed|1.02s|
| Capstone client |15passed|13.19s|
| Registered workers |3passed|53.65s|
| App |958passed|11.76s|
| Native SDK fixture gate after final correction guard |367passed|16.96s|
| Final diagnostic host/SDK checks |19passed|6.47s|

Pyright reports zero errors. Package-boundary checks, App production build and
diff checks pass. Loopback HTTP checks use NO_PROXY to avoid the machine proxy.
Upstream Starlette deprecation and existing App chunk-size warnings remain.
These are affected development checks, not release verification. The initial PR
classifier sent shared research-context mirrors and App JSON fixtures to the
product gate. The user rejected this broad early-development scope. Run40198028306
was cancelled after17m11s: unchanged grid-agent tests took706.84s and simulator
tests174.51s before reaching the changed agent code. No failed or unfinished check
is presented as passed. A targeted conversation-runtime gate replaces that scope;
Authority, solver, unknown dependency and explicit release changes retain their
own wider checks.

## Review and corrections

Independent review found and resolved these material problems:

1. A global diagnostic timer/stop prevented limited delivery and unrelated work.
   Scope-aware accounting and an execution gate now preserve those paths.
2. Public model errors appeared as successful returns. Error classification now
   survives projection and replay, including interruption and missing timings.
3. Python and JavaScript JSON numbers produced different hashes. A shared typed
   hash tree uses binary64 bytes and UTF8 bytes; real host/SDK checks cover
   1e-7,1e20,negative zero and restored exhausted selection rejection.
4. The SDK can swallow a hook error. A retained failure barrier stops the next
   model request after an unknown diagnostic receipt. The regression first
   reproduced six executions, then verified a stop after one with work retained.

Review approved the inspected changes with no remaining Important/Critical
findings. Runtime acceptance is separate.

The Stop→new-input regression required two corrections. First, accepted new input
retires pending messages from cancelled/failed/interrupted Attempts; explicit
retry retains the old request. Memory and PostgreSQL coverage passes. Real replay
then showed a second problem: historical terminal status was discarded before the
model request, while a retained Work goal appeared as current work. The new graph
planned both old and new tasks. The current instruction itself was correct.
Terminal history now retains host identity/status, and native research projections
label the retained Work goal as background. The durable ledger is unchanged.
Current-turn and explicit-resume context tests pass. Real replay onafe173cf started
a fresh CSV task, cancelled it after planning, then sent a process query on the same
Thread/Work. The new graph contained onlyinspect-processes; it completed89.073s
later with a PID/name CSV and notes. The old Attempt remains cancelled. Reload
retained both history and products. The simple query's organization overhead is a
non-blocking efficiency gap; no old CSV work was resumed.

The first canonical rebuild failed before service replacement: the native image
explicit COPY list omitted the new Python and JavaScript modules. The image
manifest and import smoke check were corrected. Source00fb086d was rebuilt and
verified across API, three workers and native executor with50exact source checks.
The latest Stop correctionafe173cf passed the canonical rebuild with84exact
source checks across all five roles. API and all workers use image012d101db1fd;
native executor usesaa1b86ffa8b7. Readiness and candidate App checks pass. The
scoped cache maintenance receipt is211057-30406.

One Thread/Work completed a direct answer(16.203s), native tool task(70.620s),
production-data research(207.959s) and registered IEEE39 calculation(26.4s).
Saved tool CSV verifies100squares and total338350. Research sampled real gateway
values with first-five mean6745.8721MW. Grid returns current-run Authority-backed,
lineage-verified refs: total active loss43.64112576085046MW and voltage range
0.982–1.0636pu. Desktop/narrow-screen replay retains selected model and products.

The initial diagnostic run failed at child source admission; the allowlist was
corrected. The next run produced a valid mean4 and saved files but repeatedly
submitted invalid record metadata; it was cancelled after226.283s. This failure
motivated one-shot diagnosis reports with bounded correction guidance. It is not
successful diagnostic acceptance. The final native fixture run also exposed two
ungranted diagnostic watchers subscribing unnecessarily. The grant/path guard
fixed both; all367native fixture tests pass.

Explicit diagnostic recovery onafe173cf completed178.175s after submission,
including about88s in the worker queue and90s of execution. It read two frozen
saved products, reused mean4 without reading/recalculating CSV, submitted exactly
one report with zero rejected submissions, and saved3545bytes of recovery notes.
The host record isreported_only/advisory withretain_gap. Historical uncertain
records remain uncertain. Saved bytes and artifact hashes were verified.

After the registered grid calculation, the same Work accepted a normal direct
question and completed in12.294s without tool calls, products or new result/evidence
refs. Selecting a registered model does not force subsequent ordinary input into
professional calculation. Diagnostic exhaustion is covered by host and actual SDK
regressions; no extra paid-model rejection loop was forced for this receipt.

## Dev integration

PR60 passed targeted macOS CI40201683198:8m11 overall,6m14 for the affected
consumer step. A previous run passed2069backend tests with146skipped but exposed
one old UI test race. A delayed first replay reproduced it; waiting for the actual
SSE connection before asserting cancellation fixed it. Eight focused tests passed
in3.51s, and the final required gate passed. Product code was unchanged by that
test repair.

The actual dev checkout is6f9ca536. All84running-source checks match that checkout
and the existing verified runtime images. Backend and native production files are
identical toafe173cf; App production files also match, with only a test changed.
The root App5173 was restarted through its existing entrypoint and inspected with
the saved Work: grid evidence, subsequent direct reply, selected IEEE39 model and
normal composer remain available. API readiness passes. This reuses the verified
build and real-task receipts; no duplicate backend rebuild or model calls were
needed. Scoped cache maintenance completed after use.

The automatic post-merge duplicate run40202723488 hit an unchanged timing test,
test_request_budget_cancels_and_deduplicates_events: an80ms request budget expired
before the first event on that runner. Its assertion requires one event, even
though expiry before that event is valid. The merged tree is byte-identical to
the passed PR tree9367fc2b. Keep this as a separate test-stability follow-up; the
duplicate failure is not represented as a pass, and unchanged suites were not
rerun to obtain a favourable result.

Cloud-dev, cloud-demo, local-demo and user-local installations are unchanged.
The production-data gateway model export remains topology-only; calculation
acceptance uses an existing registered calculation-ready model.
