# 推演步骤与电气拓扑图联动设计

> Status: approved design draft for review
> Date: 2026-09-28

## 1. Goal

After a registered application finishes its reasoning steps, the operator can
select a completed step and inspect the electrical topology state accumulated
up to that step. The topology is rendered once after the run completes; it is
not refreshed during step execution.

The design uses an optional LLM presentation pass to choose which validated
authority-backed elements deserve visual emphasis. The LLM never creates
topology, coordinates, numerical values, result references, or evidence.

## 2. Scope and non-goals

### In scope

- A bounded `capstone-network-story/1.0` projection for one completed run.
- One shared authority-backed diagram plus one cumulative snapshot per completed
  ordinal.
- Current-focus and historical-focus styling.
- One primary numeric overlay per snapshot.
- A single post-run LLM planning pass with strict JSON validation.
- Deterministic Domain Pack fallback when planning is unavailable or invalid.
- A replayable session event and an authenticated story endpoint.
- App step selection, post-completion loading, and refresh/reconnect recovery.

### Out of scope

- Live topology refresh after every answer.
- Simultaneous mixing of incompatible metrics such as loading and voltage on one
  color scale.
- LLM-generated SVG, canvas commands, coordinates, topology edges, or values.
- New authority capabilities that expose raw pandapower or PyPSA objects.
- Changes to the compatibility stdout envelope or the Kernel `core` contract.

## 3. Ownership and boundaries

The ownership direction remains:

```text
Application -> Domain Pack -> Kernel -> registered Authority
```

- **Registered Authority** supplies the immutable diagram geometry, model
  revision, result datasets, and evidence references.
- **Domain Pack** builds bounded candidate directories, applies deterministic
  fallback rules, validates candidate-to-authority bindings, and projects
  domain-specific metrics.
- **Kernel** keeps its existing neutral turns, events, artifacts, replay, and
  `core` output. It does not learn electrical topology semantics.
- **Application / capstone-agent worker** collects committed turn context,
  invokes the optional presentation planner once, assembles the story, and
  emits it before `completed`.
- **Host API** authorizes and returns the persisted story for its session.
- **App** chooses which returned snapshot to render and never derives authority
  facts in the browser.

## 4. End-to-end flow

```text
turn N committed
  -> answer/result/evidence refs are admitted for N
  -> existing diagram/layer projection is recorded

final turn committed
  -> worker gathers bounded answers, refs, candidate directories, and layers
  -> optional LLM returns a candidate-key plan
  -> server validates the plan and binds keys to authority facts
  -> deterministic fallback fills invalid or missing steps
  -> worker emits a bounded network_story event
  -> worker emits completed

App receives completed
  -> GET /api/v1/sessions/{id}/network-story once
  -> defaults to the last completed ordinal
  -> clicking a timeline step switches local snapshot state only
```

The existing `network_diagram` and `network_layer` events remain useful for
single-step compatibility and diagnostics. The App may ignore them while the
run is active.

## 5. Story contract

The new projection is:

```json
{
  "schema": "capstone-network-story/1.0",
  "mode": "cumulative-snapshots",
  "story_status": "complete",
  "plan_source": "llm",
  "diagram": {
    "schema": "capstone-network-diagram/1.0",
    "model": {"id": "...", "revision": "...", "source": "..."},
    "coordinate_system": "geographic",
    "buses": [],
    "branches": [],
    "fingerprint": "topology:sha256:...",
    "ref": "diagram:sha256:..."
  },
  "steps": [
    {
      "ordinal": 1,
      "current_focus_ids": ["line:11"],
      "history_focus_ids": [],
      "overlay": {
        "metric": "loading_percent",
        "unit": "%",
        "source_ref": "result:...",
        "values": [{"id": "line:11", "value": 72.4}]
      },
      "plan_source": "llm"
    }
  ]
}
```

### Contract rules

- `diagram` is one normalized diagram shared by every step. All step layers
  must use its `ref` and model revision.
- `steps` are ordered by ordinal and contain only completed ordinals.
- `current_focus_ids` are the elements selected for the current step.
- `history_focus_ids` are the union of selected focus elements from earlier
  completed steps. They indicate prior discussion, not current abnormality.
- `overlay` contains at most one metric. Its `source_ref` must be an admitted
  result for the same step or an explicitly carried-forward compatible result
  from an earlier step with the same authority revision.
- Overlay values are copied from an authority result after validation. They are
  never accepted from the LLM plan.
- `plan_source` is `llm` or `fallback` per story/step. `story_status` is
  `complete` or `partial`.
- Story payloads are bounded by the existing worker frame and API response
  limits. A story that exceeds bounds is replaced by a fallback story or an
  unavailable status.

The existing `GET /api/v1/sessions/{id}/network?ordinal=N` contract remains
unchanged. A new authenticated endpoint returns the story only after the
session has completed:

```text
GET /api/v1/sessions/{session_id}/network-story
```

Before completion it returns the existing not-ready response. Repeated reads
return the same persisted story and never invoke an authority or LLM.

## 6. Cumulative snapshot semantics

The story is cumulative in the evidence and focus sense, not in the numerical
state sense.

1. Snapshot 1 uses only answer and result references admitted for step 1.
2. Snapshot N may use steps 1 through N to build `history_focus_ids`.
3. The primary overlay prefers a new compatible metric from step N.
4. If step N has no compatible metric, the snapshot may carry forward the last
   compatible overlay; otherwise it has no overlay and displays the focus only.
5. Values from different steps are never summed, interpolated, or placed on one
   mixed color scale.
6. The App renders current focus strongly and history focus with a muted style.
7. Selecting a prior step restores exactly that snapshot; it does not recompute
   using later results.

## 7. LLM planning contract

The planner receives a bounded request assembled by the worker and selected
Domain Pack. It may include:

- ordinal and bounded answer summary;
- a candidate directory containing opaque candidate keys, element IDs, kind,
  metric, labels, and admitted result identity;
- already selected focus keys from earlier steps;
- finite presentation modes.

It must return only:

```json
{
  "schema": "capstone-topology-plan/1.0",
  "steps": [
    {
      "ordinal": 1,
      "focus_candidate_keys": ["c1"],
      "primary_candidate_key": "c1",
      "presentation": "highlight"
    }
  ]
}
```

The validator rejects unknown fields, missing ordinals, unknown candidate keys,
more than three focus keys, a primary key outside the focus list, unsupported
presentation values, oversized text, and non-JSON output. The server then
resolves candidate keys to authority-owned IDs, metrics, values, and refs.

The planner is one bounded request after the final answer. It uses the existing
configured Provider route in the worker and does not create a new browser or
public credential path. Provider timeout, refusal, malformed output, missing
planner support, or an offline/scripted run selects deterministic fallback.
Planner diagnostics are recorded as best-effort presentation metadata; they do
not fail answer submission, report generation, or session completion.

## 8. Deterministic fallback

Each Domain Pack supplies fallback selection over its own authority results:

- ranked branch results select the first bounded elements;
- voltage results select the largest admitted deviations from nominal;
- AC/DC cases prefer registered links when the step concerns interconnection;
- cases without numeric results retain registered structural focus;
- missing intermediate metrics produce a valid focus-only snapshot.

Fallback must use the same candidate validation and current-run admission as
the LLM path. It must never infer a value from answer prose.

## 9. Failure and security behavior

- A malformed or foreign diagram, layer, revision, candidate, or result ref is
  discarded and replaced by a valid fallback or partial status.
- A planner exception is isolated from application answer and report status.
- A missing story leaves the App with its current static preview and a bounded
  “暂无步骤图层” state.
- Public demo credentials remain scoped to registered cases; the browser gets
  only the bounded story projection.
- No provider key, raw authority object, arbitrary endpoint, shell command, or
  unbounded result data enters the planner request or story.
- Existing compatibility stdout remains exactly one JSON object with
  `question_id` and `answer_output` for pandapower compatibility commands.

## 10. Implementation units

1. **Domain Pack story projection** — candidate directory, fallback planner,
   story assembly, and schema validation for pandapower and PyPSA.
2. **Worker integration** — collect final-run data, issue one optional planner
   request, emit `network_story` before `completed`, and preserve replay.
3. **Protocol and API** — validate the new event, persist it in the existing
   ledger, and expose the authenticated story endpoint.
4. **App state and rendering** — load once after completion, select snapshots,
   style current/history focus, and recover after refresh.
5. **Tests and fixtures** — authority-binding negatives, planner validation,
   fallback behavior, replay equality, API authorization, and browser state
   transitions.

## 11. Verification and acceptance

### Unit and boundary checks

- Foreign revision, unadmitted ref, unknown candidate, invalid metric, and
  invalid story identity are rejected.
- LLM numeric values and coordinates cannot enter normalized story output.
- Existing single-step network projection tests remain green.

### Worker and API checks

- No planner call occurs before the final answer.
- Exactly one planner attempt occurs for a supported provider run.
- Timeout, malformed JSON, and unavailable Provider all produce fallback.
- `network_story` precedes `completed`, survives event replay, and is stable on
  repeated authenticated reads.
- Incomplete sessions cannot read the final story.

### App checks

- The topology does not change while a step is executing.
- Completion loads the story once and selects the final step.
- Selecting step N shows only the snapshot through N.
- Current and historical focus have distinct visual treatment.
- Refresh/reconnect restores the persisted story and selected final snapshot.

### Repository gates

Run focused Kernel/Domain Pack/Capstone Agent/App tests first, then the required
offline gates for the implementation scope: `make doctor`, `make test-e2e`, and
`make validate`. Provider billing is not required for the offline gate; one
authorized Provider run can confirm the optional LLM path after deterministic
coverage is complete.

## 12. Acceptance examples

- A three-step PyPSA case finishes with one story containing one shared diagram
  and three ordered snapshots.
- Clicking step 1 never shows a result introduced by step 2 or step 3.
- Clicking step 3 can show a final loading overlay while retaining muted focus
  markers from earlier steps.
- A malformed planner response produces the same valid story shape through the
  fallback path and leaves the run completed.
- A user without the session credential cannot read the story endpoint.
