# Progressive context for continuous work

A Thread carries evolving task state across instructions. The model starts each
instruction with the current intent, unresolved decisions and references needed
to continue. The instruction determines how much work to do. Saved results,
evidence and artifacts remain available through their existing authorized
readers.

## Load context in stages

1. Keep invariant instructions, mandatory policy and a small set of discovery
   tools in stable order. Do not make a tool or business service a required
   first action. Keep the selected capability visible across adjacent requests
   while its contract, scope and grant remain valid.
2. Add the current instruction, relevant task state and recent conversation.
   Retain exact references for open work, results and artifacts. Prefer the
   existing projection and saved task state over reloading a complete replay.
3. Use explicit reads for detailed guides, tool schemas, full observations and
   older conversation. Apply size bounds to the model view. Keep complete
   authority results available for formal delivery. A follow-up that only
   formats an existing result should reuse that result.
4. Invalidate a loaded contract on a change in connection identity,
   authorization or revision. Validate grants before presenting or using any
   restored reference. A loaded guide does not grant access.

PPT guidance remains an independently discoverable resource. Apply the same
loading rules to capacity, gateway and other execution guides. Use the existing
adapter and managed-resource entry points.

## Size requests and retain cache inputs

Resolve the window and output allowance from the selected model profile.
Measure the assembled request, including tool schemas and serialization
overhead. Treat estimates as estimates and calibrate them against reported
usage. Set a bounded input budget that leaves room for the expected output
and for continuation. When a request approaches the limit, reduce optional
projections, then compact eligible history. Record a diagnostic if the
required inputs alone exceed the budget. Preserve saved state for recovery.
Apply the budget to summary requests as well as ordinary execution.

Use a deterministic prefix within an authorized execution scope. Keep changing
task state, clocks and observations outside that prefix where the provider
protocol permits. Do not depend on a cache hit for correctness. Do not
prewarm the model by submitting an extra request. Measure input, cached input,
cache writes, and time to first content per actual provider dispatch. Use
provider prefill measurements where reported. Report time to first content
separately because it includes processing outside prefill. Omit provider
metrics that the provider does not return.

## Compact history and continue

Use Pi compaction with the active profile and record its trigger and outcome.
The compacted history carries narrative continuity. Persist pending work,
admitted references and continuation state through existing task storage.
Keep the latest user instruction intact. Respect the lifecycle of submitted
tool calls. An unknown result remains unknown until it can be checked through
the original receipt. Do not replay a business operation to rebuild context.
Verify that continuation after compaction or restart can load the same
authorized references under current policy.

## Acceptance

Use the current dev behavior as the control. First compare the full context
lifecycle with the control. Then isolate prefix, tool activation or compaction
changes if the request records show a regression. Run repeated matched cases
with provider and profile held fixed. Record observed cache state. Separate
initial requests from warm follow-ups.

- Exercise a first query, a short follow-up, formal result formatting, report
  delivery, and a user instruction that changes direction in the same Thread.
- Include an authorized gateway call in local-dev and reuse an existing result
  without a second business dispatch. Use downloaded diagnostic bundles for
  off-host repair. Keep production gateway access on the controlled host.
- Force a small-window run through ordinary automatic compaction. Resume
  after compaction and after a restart. Check evidence, references and pending
  operation state. Exercise compaction failure and a task that cannot fit its
  required input.
- Compare both end-to-end latency and calls per instruction, with input,
  cache, first-content timing and compaction calls attributed per request.
  Include full reports, evidence and artifact checks. Use request traces to
  explain regressions before changing defaults. Keep per-model rollback.

### Quality by instruction type

Classify cases for evaluation. The runtime selects context from the current
instruction, task state and tool environment. Do not route by keywords.

| Instruction | Expected request context | Expected execution result |
| --- | --- | --- |
| Short follow-up or explanation | Relevant prior conclusion, exact result reference and the evidence needed for the question | Answer at the requested depth. Preserve units and qualifiers. Reuse the saved result when it supports the answer. |
| Change one parameter | New value, original operation contract and confirmed parameters that still apply | Use the new value. Preserve other confirmed choices. Check any affected result coverage before reuse. |
| Reformat a result or generate a report | Saved result, schema, units, provenance and requested output format | Deliver a usable artifact. Match saved values and coverage. Retain evidence references. |
| New query or change of direction | Current intent, applicable constraints and relevant task state | Follow the new direction. Select an authorized source when needed. Preserve unrelated work state. |
| Plan or evaluate an option | Task state, unresolved choices and applicable capability descriptions or contracts | Explain feasible choices and missing information. Dispatch only work requested by the user. |
| Resume after compaction or an uncertain operation | Current instruction, durable state, admitted references and original call receipt | Restore the correct point of continuation. Check the original receipt when available. Preserve uncertainty and avoid duplicate dispatch. |

For each case, establish required, useful and irrelevant inputs before the run.
Compare them with the actual provider payload for each dispatch. Record missing
facts, stale or conflicting state, redundant content, and the additional calls
caused by missing inputs. When a field or schema is loaded later, check whether
it arrived before the decision that needed it. Keep sensitive content in the
authorized environment and export only permitted diagnostic fields.

Score the result independently against saved authority results, tool receipts
and artifact checks. Check instruction fit, correctness, scope, evidence
consistency and usable delivery. A missing fact that changes the result, an
unauthorized reference or an incorrect duplicate operation fails the case
regardless of token savings. For failures, trace the sequence from selected
context through tool decisions to the final result. Mark attribution uncertain
when the trace does not support a cause. Report by instruction type and
execution stage, alongside calls, tokens, cache and latency. Keep requirement
checks separate from performance observations so an aggregate cannot hide a
regression in short follow-ups or recovery.

## Per-dispatch construction

The application owns the current instruction and versioned Thread state. The
Pi adapter assembles each provider request at the last context projection
before dispatch. A retry of the same dispatch uses the same selected inputs
unless an explicit recovery step creates a new request. Keep the original
selection available for diagnostics.

| Stage | Inputs and decision | Output |
| --- | --- | --- |
| Establish scope | Resolve workspace, Thread, current instruction, model profile and current grants | Eligible resources and input allowance |
| Identify dependencies | Follow explicit references from the instruction, current task state, pending calls and current tool decision | Required facts, contract revisions and unresolved references |
| Select supporting material | Prefer direct provenance and current matching parameters. For ambiguous references present bounded candidates. Allow the model to request further evidence | Relevant result slices, context excerpts or handles |
| Assemble | Order stable policy and schemas deterministically. Carry current intent, confirmed constraints and active dependencies. Preserve provider-required tool-call/result pairs | Provider-valid request with a bounded working set |
| Observe and continue | Record actual dispatch identity, outcome, admitted results and changed task state. Rebuild the next request from the updated state | Reproducible decision record |

Use deterministic checks for authorization, parameter coverage, revision and
scope. Use explicit references and the model's existing tool decisions for
semantic selection. Avoid an extra planning call on every instruction. An
ambiguous business meaning can require clarification. Recency breaks ties
between equally applicable records. A later result for another province or
time window cannot supersede an earlier result for the requested parameters.

## Capacity and failure decisions

Resolve the effective input ceiling from the selected context window less
reserved output and encoding allowance. Count system instructions, messages,
active schemas and tool results together. Use provider-compatible counting
when available. Record the estimation method otherwise. Keep the compaction
trigger distinct from the hard dispatch ceiling. Evaluate again after schema
activation and after tool completion because each can enlarge the next request.

If over budget, drop duplicate and weakly related optional material first,
replace large saved values with scoped projections and retain their handles.
Compact eligible narrative only when still needed. Reassemble and measure.
If required input still cannot fit, return the exact limiting component and
preserve work. Cap recovery attempts per dispatch. A compression failure must
leave the last valid task state and original receipts readable.

## Cache, timing and diagnostics

Reuse the existing provider request observer and request identity. Compare
stable prefix fingerprints within the same model, scope and policy revision.
A matching fingerprint indicates an opportunity for cache reuse. Count a hit
only from provider usage. Record queue, dispatch, first content and completion
timestamps where observable. Label provider prefill separately and mark missing
measurements unavailable. Include compaction calls in total instruction cost.

Extend the existing authorized diagnostic snapshot with the request identity,
selected resource revision, projection size, selection reason, omission reason
and budget decision. Persist bounded metadata. Reuse current evidence export
rules for content. A developer should be able to follow an instruction from its
task-state revision to each dispatch and final product using the downloaded
bundle, including gaps when the deployment withheld content.

## Integration and rollout

Start at the general Pi server admission boundary, managed session request
projection and model context observer. Reuse model_context_policy.py for the
effective profile and existing Pi settings for compaction. Keep Thread state
and authority evidence with their current owners. Verify the actual provider
dispatch, including retry and summary paths, before claiming coverage.
Run the instruction matrix with the deployed default and candidate on matched
profiles. Record repeated observations, missing measurements and per-type
regressions. Promote a profile only after correctness and continuity pass and
material regressions have an explained and accepted disposition. Retain the
existing rollout switch for rollback.
