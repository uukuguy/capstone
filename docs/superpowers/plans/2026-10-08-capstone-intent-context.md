# Capstone Intent and Conversation Context Implementation Plan

**Execution:** In dependency order, with bounded implementation and review delegation; preserve unrelated work. The canonical
delivery ledger remains `2026-10-07-capstone-conversation-completion.md`.

**Goal:** Recognize requests through an interchangeable model node, preserve shared
conversation, and load the appropriate native Pi configuration and capabilities.

**Architecture:** Application-owned intent contracts separate recognition from
context preparation and execution. The first recognizer uses managed Pi RPC.
Thread ledger remains authoritative; Domain Packs retain calculation admission.

**Tech stack:** Python application contracts and services, PostgreSQL, managed Pi
RPC, a trusted TypeScript Pi extension, existing App event projection and tests.

**Approved design:** [Conversation context](../specs/2026-10-08-capstone-conversation-context-design.md).

## Implementation status — 2026-10-08

Tasks 1–4 are implemented in the local hosted path. Their detailed lists below
retain the original execution plan; the [verification receipt](../../reviews/2026-10-08-intent-context-local-verification.md)
records the checks actually run. Task 5 remains open for real model and user
acceptance. Loopback fixtures are not model-quality acceptance.

The implementation adds explicit goal dependencies and frozen execution resource
candidates to the planned contracts. Native Pi extensions are JavaScript modules;
no Kernel policy change was needed. Task-owned implementation is delivered as one
integrated commit after the release gates, rather than separate per-task commits.

## Global constraints

- No keyword intent classification or keyword fallback.
- No separate ordinary/business dialogue histories.
- Stable behavioral instructions use native Pi configuration; history is message data.
- Intent decisions never grant permissions or admit calculation evidence.
- No real Provider calls without explicit authorization; use loopback for transport tests.
- No Pi reference implementation or skills/MCP installation in this package.
- Preserve immutable Attempt identities, model selection, replay and user data.

## Task 1: Engine-independent recognition contract

Create `packages/capstone-agent/src/capstone_agent/request_intent.py` and
`packages/capstone-agent/tests/test_request_intent.py`.

Define frozen input/decision/identity models and the recognition protocol:

```python
class IntentRecognizer(Protocol):
    identity: IntentEngineIdentity
    def recognize(self, request: IntentRequest, control: NodeControl) -> IntentDecision: ...
```

Input fields: Thread/Turn/Attempt identity, original instruction, history cutoff,
bounded source-labelled messages, object identities, capability entries and an
optional user mode hint. Decision fields: ordered goals, relationship, input
message/object references, required operations/capabilities, missing requirements
and optional clarification. Engine identity is separate from the decision.

Operations: answer, rewrite, catalog lookup, external lookup, business-result read,
business execution. Relationships: independent, continuation, supplement, unclear.
Unknown capability needs use missing requirements, not invented catalog IDs.

- [ ] Write red tests for invalid enum/fields, oversized input, unknown source
  references, fabricated capability IDs and mutable nested values.
- [ ] Implement bounded JSON parsing and immutable copies; bind a decision to its
  exact request identity and history cutoff. Reject extra fields and non-finite values.
- [ ] Test that two recognizer implementations return interchangeable decisions
  and that invalid output cannot change selection or invoke an executor.
- [ ] Run `uv run --project packages/grid-agent pytest packages/capstone-agent/tests/test_request_intent.py`.
- [ ] Commit only the contract and its tests after green results.

## Task 2: Shared history projection and frozen recognition input

Modify `thread_service.py`; create `conversation_context.py` and
`tests/test_conversation_context.py`; extend existing service/PostgreSQL tests.

Expose `ConversationContext` as a bounded immutable projection attached to the
claimed Attempt. Keep user/assistant roles, source Turn/Attempt/ModelContext IDs,
terminal status, ordering and cutoff. Preserve cross-topic dialogue. Do not convert
failed partial output into a completed answer or synthesize authority tool results.

- [ ] Write red scenarios for analysis → weather → follow-up, analysis → translation,
  model switch → comparison and cancellation → retry.
- [ ] Build equivalent in-memory and SQL projections from committed events. Enforce
  configured history bounds and explicit truncation metadata.
- [ ] Persist the Attempt input snapshot before recognition; retry uses the original
  cutoff/config identity and excludes duplicate current instructions.
- [ ] Test that preparation and execution consume the same projection and that
  restoring a Thread does not splice another Thread's messages.
- [ ] Run focused context/service/PostgreSQL checks, then commit task-owned paths.

## Task 3: Native Pi configuration and first recognizer

Create application-owned `pi_intent.py` and a trusted Pi context extension beside
existing application runtime resources. Add `configs/runtime/capstone-pi/` settings
and prompt resources. Modify Kernel `runtime/environment.py` only for neutral
explicit loading controls; keep application intent semantics out of Kernel.

Implement `PiIntentRecognizer` against `IntentRecognizer`. It receives a managed
session factory; it does not resolve secrets, choose arbitrary endpoints or directly
call a Provider SDK. `NodeControl` supplies cancellation, deadline and lease heartbeat.

- [ ] Add a loopback failing test that captures Pi's actual preparation request:
  native base config plus shared messages and bounded capability descriptions,
  with no grid role, business constraints or calculation tools.
- [ ] Load controlled `SYSTEM.md`/`APPEND_SYSTEM.md` and permitted settings via Pi's
  supported mechanisms. Preserve protection from host HOME/repository discovery.
- [ ] Use the pinned Pi structured-output mechanism to produce one decision and end
  preparation. Validate through Task 1; bound the call and close resources on all exits.
- [ ] Verify message roles through the Pi context hook, not a history block inserted
  into the system prompt. Never expose secrets in event payloads or capture reports.
- [ ] Test timeout, cancel, invalid JSON/IDs, missing config, exactly one preparation
  per Attempt, and interchangeable injected recognizers. No heuristic fallback.
- [ ] Run real managed Pi with the loopback Provider; record request capture assertions.
- [ ] Commit configuration, adapter, extension and tests together.

## Task 4: Recognition → resource preparation → execution

Modify `thread_worker.py`, `turn_router.py`, `thread_application.py`,
`kernel_pi_session.py`, hosted assembly adapters, and their focused tests.
Audit `catalog_answer.py` for implicit keyword reclassification.

- [ ] Write red worker tests proving recognition precedes domain preparation,
  ordinary interpretation cannot activate tools, and missing capabilities remain
  explicit even when the model asks for them.
- [ ] Inject the recognizer through application assembly. Remove `_heuristic_route`
  and its failure fallback; preserve deterministic scripted Case plans.
- [ ] Validate intent then construct resources from registered capability identity,
  enabled selection and model applicability. Keep model state unchanged.
- [ ] Route clarification to the normal answer path without preparing execution
  resources; report recognizer faults as faults, not ambiguous user intent.
- [ ] Load business policy and evidence only for goals that require them. A mixed
  request gets the union of validated needs; unrelated instructions get no business
  execution role. Keep historical text available for translation and follow-ups.
- [ ] Use the recognized catalog operation in catalog admission; remove sentence
  matching as a second intent classifier. Bind all numerical claims as before.
- [ ] Persist public preparation/execution state and a bounded decision receipt;
  keep detailed prompts/credentials private. Do not persist hidden reasoning.
- [ ] Test lease renewal/cancel in both stages, replay, retries, model switches,
  disabled tools and no accidental Domain Pack provisioning.
- [ ] Run focused backend, adapter, Pi extension and App checks; commit passing code.

## Task 5: Acceptance and recovery records

- [ ] Run the approved scenario matrix with scripted recognizer outputs to verify
  contracts. Do not label fixture results as model intent accuracy.
- [ ] Run managed Pi loopback scenarios for actual message/config composition and
  two-stage execution; include unavailable weather/news capabilities.
- [ ] Run types, boundaries and full integration gates appropriate to the change.
- [ ] Rebuild through `make capstone-local-rebuild`; verify real App/API entry,
  API/worker identity, stream/cancel/replay and retained model/draft.
- [ ] After explicit Provider authorization, assess real interpretation and answers
  for contextual minimal pairs and mixed tasks; report latency and usage for both stages.
- [ ] Record local evidence and remaining user acceptance in a review receipt;
  update canonical worklist, journal and live checkpoint. Advance to pure Pi only
  after user acceptance of Capstone behavior.

## Review checkpoints

No runtime acceptance is implied by finishing Tasks 1–3. Task 4 must wire the node
into the real hosted path, and Task 5 must verify it. Jev/small-model enhancement is
a later implementation of the same interface, not a dependency of initial delivery.
