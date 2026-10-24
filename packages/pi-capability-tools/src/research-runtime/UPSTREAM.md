# Research runtime core

Adapted from `timaliev/pi-deep-research`, commit
`3470ed76411886338b525f32c3d6778e22e2bab4`, package version `0.33.0`.
Source: `extension/state-machine.ts`, `research-round.ts` and
`research-run-orchestrator.ts`. Copyright 2026 Timur Aliev. The retained MIT
license is in [LICENSE](LICENSE).

The original nine source modules are retained byte for byte in `upstream/source/`.
`upstream/manifest.json` records their SHA256 values. `upstream/generate.mjs`
checks those values, applies the narrow stage-port patch, erases TypeScript using
Node's built-in transformer, and writes `upstream/runtime/`. Production imports
the generated JavaScript; no runtime TypeScript loader or install is needed.

The facade imports and drives this actual upstream ResearchStateMachine. Its
original search round, semaphore, profile resolution, question parsing, depth
router, report styles, draft serialization and next/resume methods remain. The
default web path still runs with injected `searchFn` and `scraper`; a focused test
executes search → extraction → parsed follow-up → second search → draft → done.
No network engine is bundled or imported: callers supply admitted retrieval.

Enterprise stage ports replace the environment-specific stages: local/native
execution, committed findings, supplied assessment, delivery guidance and actual
product inspection. This path fixes the missing findings record and avoids
upstream's draft-length completion predicate. TUI, global settings, release
checks, independent report assembly and subprocess model calls are not included.
The unadapted web stages retain their upstream limitations, including depth-only
routing and empty retained findings; do not claim those establish enterprise
acceptance. Use the governed facade for enterprise execution.

## Porting map

| Original source retained | Adaptation |
| --- | --- |
| `state-machine.ts` | Constructor accepts optional phase ports; five existing stage methods consult their port first. Original `next` switch drives both paths; unknown phases now throw. All other original methods remain. |
| `research-round.ts` | No semantic patch; original concurrent injected search/scrape/URL collection and queue diagnostics. |
| `concurrency.ts`, `ids.ts`, `logger.ts`, `profile-resolver.ts` | No semantic patch. |
| `report-styles.ts`, `research-draft.ts`, `search-queue.ts` | No semantic patch. |
| Generated `.mjs` files | TypeScript erasure and relative `.js` → `.mjs` import suffixes only, plus the documented state-machine port patch. |
| `index.mjs` | New facade: JSON/capacity/cancellation checks and application-owned stage adapters. It does not copy the upstream phase dispatcher or create a model/ledger. |

Regenerate with `node src/research-runtime/upstream/generate.mjs`. Generated files
are checked in to avoid changing the runtime dependency/bootstrap boundary. The
transform command requires a Node version with `stripTypeScriptTypes` transform
support; it is not run by the deployed task. Retained original source is for
provenance and regeneration, not a separately installed extension.

## Public API

```js
import {ResearchRuntime, serializeSnapshot, restoreSnapshot}
  from './index.mjs';

const runtime = new ResearchRuntime({
  executeRound, recordResult, inspectProducts,
  assess, // optional: validates/transforms supplied assessment, never auto-called
  prompts: {extraction, questioning, delivery}, // optional text-producing ports
}, {maxRounds:64, maxFindings:4096, maxQuestions:256,
    snapshotBytes:16777216, timeoutMs:1800000});

let snapshot = runtime.init({runId, goal, questions, sourceRefs});
const result = await runtime.advance(snapshot, {
  assessment, // optional, normally captured from an existing managed Pi tool
  signal, deadline, // optional; deadline is epoch milliseconds
});
snapshot = restoreSnapshot(serializeSnapshot(result.snapshot));
```

Pass the same capacity overrides to serialization/restore as to the runtime.
Initialization does no work and calls no port. Each advance uses a copy; caller
snapshots are not mutated. All ports receive an abort signal and deadline. They
must propagate cancellation into their actual executor; aborting the wait cannot
undo side effects in an adapter that ignores its signal. The caller retains the
task's original deadline across advances, rather than resetting it for each phase.

| Port | Input | Return |
| --- | --- | --- |
| `executeRound` | `{runId,round,objective,questions,sourceRefs}`, control | `{findings,observations,limitations,productRefs}` |
| `recordResult` | `{kind,recordId,snapshot,result}`, control | committed `{checkpointRef,revision}` |
| `assess` | `{snapshot,result,suppliedAssessment}`, control | assessment; called only when one was supplied |
| `inspectProducts` | `{snapshot,requested,productRefs}`, control | `{ready,actualProductRefs,limitations}` |
| prompt function | snapshot, control | nonempty prompt text |

Findings are `{id,text,status,refs}` with status
`hypothesis|supported|refuted`. Observations and products are opaque reference
strings. An assessment is `{decision,summary,refs,followUpQuestions}` with decision
`continue|revise|deliver|blocked`; continue/revise require actual follow-up questions.
The runtime cannot certify sources: **recordResult must admit references, validate
ownership and use the host's existing CAS/idempotency/receipt recovery**. A model
self-assessment is not independent verification or Authority evidence.

`recordId` is deterministic: `runId:round:round` or `runId:round:assessment`.
The caller must bind a unique run identity and immutable accepted input. A failed
record returns `record_pending` with the completed result still in the snapshot;
retry that snapshot and recover the same receipt instead of repeating execution.
The core is not a ledger. Persist snapshots and findings through the existing
research controller. Persist final phase snapshots through the caller's existing
checkpoint seam as well; the runtime creates no private database or filesystem.

Statuses are `in_progress`, `needs_assessment`, `record_pending`, `needs_products`,
`limited`, `blocked` and `done`. No missing assessment or absent product can become
done. Capacity errors include `code`, dimension, actual and configured limit;
round exhaustion returns `limited` and preserves findings. Cancellation and
deadline throw `AbortError` and `TimeoutError`. Port failures in execution or
product inspection propagate; only uncertain persistence is returned for recovery.

Host-only phases can advance consecutively without model calls. An execution
adapter can run real native local work or an authorized Pi subagent, or consume
observations already produced by the managed session. A registered assessment
tool can supply the decision when that same session performs useful work. Do not
start a nested prompt from inside its own tool execution. The host must schedule
continuation through the existing session lifecycle. No separate planner or
evaluator model is required by this core. Direct chat need not instantiate it.

The delivery prompt is a request, not evidence of file creation. The caller's
product port checks real saved files and preserves the existing report/version.
It may also accept a supported text-only result when no file was requested. The
core does not invent a report, reopen Authority access or confer evidence status.

Focused acceptance: `node --test test/research-runtime.test.mjs`. The CSV test
uses actual temporary source/report bytes, detects a conflicting first result,
revises that same report, and checks committed record order. It is an offline
integration fixture; it is not a claim of model reasoning quality or speedup over
the real 350.524-second baseline.
