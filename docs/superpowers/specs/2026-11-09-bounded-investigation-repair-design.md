# Bounded investigation repair proposal

Status: proposed; not implemented or accepted.

Review update: the four data-gateway acceptance corrections are incorporated.

## Observed case

Thread thr_4d2e08d5cbea2b23ac1f, attempt attempt_11d6740e12103ae4.
Task pi-62898a1ef64310d459472a6d945e7ec3bc7afc85e5d8b1410f8cb00e11f5ed7b.
Public events are retained in runs/local-chain-20261109/events.json.
218 tool completions comprise132 gateway calls,57 composition calls,28 shell
calls and one skill load. Eight errors comprise six gateway contract/policy
rejections, one invalid observation reference and one absent observation file.
No exactly repeated tool-name/input-excerpt pair was found. Excerpts are not
full arguments; this does not establish semantic uniqueness or duplicate absence.

The answer labels12 seven-day samples as annual coverage and suggests an empty
historical table from selected empty windows. Neither inference is established.
The runtime's completed status indicates execution termination, not independent
acceptance of the business result. UI goal-completion presentation is a separate
follow-up and is outside this patch's scope and acceptance gates.

## Code findings and limits

research-guidance.mjs lightweight mode installs guidance only before agent start
and returns before the result-sensitive context path. Existing task-turn guidance
is advisory and does not stop execution. This does not prove a scheduler loop bug.
The loaded explore-data skill describes comprehensive dataset profiling; it is
broader than finding one real record. Skill text must remain unchanged. Selecting
a method must not expand the current user instruction.
Invalid references were rejected. Those rejections are correct boundary behavior;
the observed caller mistakes do not justify weakening ownership checks.

## Options

1. Policy-only guidance: small change, no verified runtime reminder delivery.
2. Recommended: instruction-scoped guidance plus neutral, coalesced checkpoints.
3. Hard tool/time caps: mechanically simple, but can stop valid investigations
   and cannot establish that an empty result has the same business meaning.

## Proposed behavior

Keep semantic judgment with the model. Before exploratory work, the model states
its finite scope, intended evidence and stopping/reconsideration conditions.
Selected skills cannot expand that scope. Empty samples support only the exact
query scope; table-wide absence requires explicit source evidence. Units inferred
from convention remain hypotheses rather than verified source facts.

Reuse the current lightweight loop. The host may count admitted completed leaf
calls and inject bounded/coalesced scope-review advice at a configured checkpoint;
it must not classify arbitrary business payloads as empty or route by tool names.
Composite wrappers must not double-count leaves. A reminder must ask for a new
evidence-based justification before expansion, without forcing a service or tool,
creating user messages, cancelling execution or asserting goal attainment.
The model can continue when useful, or return the scoped gap without a false
global conclusion. Existing execution statuses remain unchanged in this patch.

These advisory checkpoints can improve convergence; they do not enforce a hard
call, time, token or cost budget. A model can continue after a reminder, and
in-flight calls can finish before it receives one. Any guaranteed budget requires
a separately designed host admission/reservation and cancellation contract.
No such budget guarantee is claimed or introduced here.

## Verification

First reproduce reminder delivery failure with a focused event-hook test. Check
leaf/wrapper counting, coalescing, per-task reset and unaffected normal answers.
Keep two independent live acceptance tracks; passing one cannot substitute for
the other:

1. Exact-reference retrieval: supply a source-verified record reference including
   device, metric, source and timestamp. Execute the admitted retrieval and compare
   the final saved reader-facing answer with the returned source record. It must
   contain ten timestamp/value pairs, with all ten numerical values matching the
   source and with explicit device identity, unit basis and time semantics. A
   completed attempt, successful fetch, product file or ten rows absent from the
   final answer is insufficient. Never supply the expected values to the model.
2. Discovery from zero samples: supply no known record key or date. Verify that
   exploration stays within its stated scope, revisits its rationale before
   expansion and distinguishes sampled absence from whole-source absence. If no
   real record is found, accept only a scoped gap with retained evidence; do not
   count this as positive retrieval acceptance. If a record is found, verify the
   same ten source values in the final answer. Keep a deterministic empty-source
   model test as a separate negative control, not a substitute for this live path.

Audit semantic repetition using full admitted arguments and exact task/call IDs,
joined with dispatch/source request IDs where available. Separate wrapper calls,
leaf calls, retries, pagination, polling and distinct time/source/version scopes.
Normalize only contract-defined equivalences; model judgment may identify broader
semantic overlap but must retain the compared calls and its rationale. Truncated
excerpts are navigation aids only. If complete arguments or correlation IDs are
unavailable, mark repetition unknown rather than declaring it absent.

Inspect actual scope, source claims and saved answers; do not rerun the218-call
case or claim a prompt guarantees semantic correctness. Record the outcome of
each track independently, including blocked or failed acceptance.
No CI, push, integration or deployment is authorized by this design proposal.
