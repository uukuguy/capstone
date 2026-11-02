# Parallel first-generation diagnostic checkpoint

## Evidence-based convergence candidate, 2026-10-20

Parent guidance now requests a question, sources, expected evidence and completion
criteria. Child guidance permits focused checks and related batched operations,
then returns findings when evidence is sufficient. Further work requires concrete
uncertainty, a discrepancy, missing evidence or an explicit user requirement.
This adds no numerical cutoff and does not accept unsupported findings.

Offline checks: 20 delegation/managed child/delivery checks and 48 runtime/actual
SDK checks passed. SDK fixtures now parse their own accepted questions separately
from sibling assignments, delimit the output path before source guidance, and
verify response timing events alongside child lifecycle events. Production
changes are limited to guidance. Canonical local rebuild is in progress at
`/tmp/review-convergence-rebuild.log`. Repeat the same seven inputs and exact
two-question prompt against the 140.313-second run before claiming improvement.

## Review scope repair candidate, 2026-10-20

Live checkpoint: the candidate is now locally deployed and scope-tested.
Backend API/workers 7e940415682745850ee0498669cbc1ae7b439ddaba17642590746f270bb3dff3;
native b91c572f8f041adebd1658d3349a71c667d31aeb99c46f418cf31a19275f413b.
Readiness and scoped cleanup passed (cache-maintenance-20261020-011232-69867.log).
Thread thr_931f232fb5a1ef94ff8d / attempt_cf7880b0162103c4 completed in
140.313 seconds. Price branch: 69.833 s, 20 tools, 15 responses, zero errors.
TOC branch: 88.238 s, 22 tools, 21 responses, three local script errors.
One parent delegation schema error (extra mode field) was corrected.
The branches stayed in their respective scopes. Results match an independent
CSV mean (251.82161626344086, 2976 rows) and HTML anchor check (8 links, no
missing target IDs). Browser scroll behavior was not verified by this check.

Performance is NOT accepted. Parent instructions expanded two small questions
into long procedural checklists; branches then checked alternative conventions,
made extra result files and repeated parsing. The next change should address
parent assignment verbosity and stopping after sufficient evidence, not larger
pools or more parallel children. Do not run the broad review again before that
change. Receipts and timing-summary.json are under
ROOT/outputs/research-round-efficiency/parallel-review-scope-check.

The saved completeness child result confirms duplicated work: besides checking
HTML structure it recomputed market, flow and renewable figures, including tables
2/4/6/7. Its 30 calls overlapped the metrics and claims assignments. Each child
previously received only its own task, with no view of sibling responsibilities.

The generic delegation adapter now passes immutable sibling IDs, titles, questions
and expected outputs to each child. It does not grant access to sibling private
workspaces or treat an assignment as a successful result. The managed prompt asks
children to stay within their assigned questions, return cross-scope concerns to
the parent, and report a local failure after an unsuccessful focused correction.
Necessary in-scope checks remain allowed. This is guidance, not a new hard limit
or a fixed number of review branches. Both ordinary and text-only review children
receive it; review prompt capacity reserves its exact text length.

The sibling-metadata regression failed before the fix and passed afterward.
32 delegation/runner/actual SDK checks and 18 review checks passed. Rebuild:
/tmp/branch-review-scope-rebuild.log. Candidate behavior and performance are not
yet live-verified. The next small visible review uses one price fact and HTML
anchor validity, so scope overlap is easy to observe before another broad review.

## Parallel review trial and live statistics, 2026-10-20

Timing deployment and short live test subsequently passed. Backend API/workers:
sha256:2c55498d8c656bbb45d155ad6cab2804ec8e048e9661ad72aaa613fd0d7de329.
Native: sha256:70f8955aa9a36054740436907ed8ece0b1b23c474d26f89da962fd99e10d02b2.
Scoped cleanup receipt: .capstone-agent/cache-maintenance-20261020-005954-50014.log.
Thread thr_d7602a61a693d3e002aa / attempt_f989622d5fbe71bd completed a
two-child row-count smoke in the user's Chrome session. Each child made one tool
call and two model responses. Public timing events recorded 1806 + 2403 ms for
spot-rows and 1004 + 1351 ms for renewable-rows. Events arrived before each child
finished. Source UI tests verify live parent totals and response deduplication.
One initial producer plan without product_paths was rejected and corrected;
no child errors occurred. This is timing verification, not research speed gain.
Receipts: ROOT/outputs/research-round-efficiency/branch-timing-smoke.
Additional checks: 80 API/executor tests, nine focused host-boundary checks and
the actual pinned SDK timing test passed.

Thread thr_d2134f3a133f2c990201 / attempt_e201b06f2b3a3c02 used a new
session with four original inputs plus the historical report.html,
key_metrics.csv and analyze.py. Hashes were checked on upload. Other historical
supporting files were not uploaded; missing-file findings apply to this selected
review package, not necessarily to the complete original delivery.

Three review children started within 18 ms. The completeness child completed in
144.263 seconds with 30 tool calls. Metrics and claims children made 26 and 36
calls and had two and four script errors respectively. Parent preparation had
six rejected calls, including unknown evidence references. The trial was stopped
at 299.763 seconds as review scope continued to expand. This proves concurrent
review execution, not a review speed improvement. Receipts and timing-summary.json:
ROOT/outputs/research-round-efficiency/parallel-review-capability.

User observed that parent statistics stayed at one tool call while branches ran.
The App now adds branch tool counts as events arrive. Parent model time is labelled
separately. New delegation_child_response events carry each observed response
number and elapsed milliseconds, through the existing checked host binding.
The App deduplicates by response number and shows branch response count and
cumulative model time. This sum is not parallel wall time. Missing old timing
remains unknown. No CSS or typography changed.

Checks: 31 runner/delegation tests; 89 Python bridge/step tests with one skipped;
20 App tests and TypeScript checks passed. Canonical rebuild is in progress in
/tmp/branch-response-timing-rebuild.log. Live acceptance of the new timing events
is still pending. Next research fix must narrow review scope and prevent repeated
full recomputation across reviewers, while preserving concrete findings and
unchecked scope. Do not add a fixed three-reviewer template or restart a long
full-report test before this is addressed.

## Three-child capability passed; parallel verification next

Attempt attempt_3a8a9aa5366c05b1 in thread thr_fa4e1fd1b223e1acebdb
completed the explicit three-child source-inspection test. All children finished:
spot-prices 25.970 seconds, interprovincial-flows 44.472 seconds, and
renewable-generation 37.478 seconds. Their execution intervals overlap; the
combined child interval is 44.481 seconds. There were no child errors. One parent
planning error was corrected. This proves batch execution and result return,
not autonomous branch selection or full-report quality and speed.

The user accepted applying the same mode to the previously slow verification
phase. Independent checks may run together against the same fixed report and
source versions. Dependent checks wait for their inputs. Branch selection must
follow the actual verification questions, not a fixed three-branch template.
Reviewers return findings and unchecked scope; the parent merges them and makes
limited repairs. A failed local check or repair is recorded rather than causing
an endless review cycle or discarding an otherwise usable draft. Compare review
wall time separately from first-generation report time. This is accepted work,
not yet a verified performance gain.

Branch elapsed time now comes from actual start/end events in the App source;
running branches update each second. Nineteen focused App tests and TypeScript
checks passed. No CSS or message typography changed.

## Confirmed causes and follow-up, 2026-10-20

User steering: keep debug pool capacities large enough for the test and defer
new queue scheduling. Do not switch the delivery mainline into a scheduler
project. The pending relay queue patch was removed before deployment. Follow-up:
separate active concurrency from waiting queue capacity, support cancellation and
the existing task deadline while waiting, and report actual queue overflow.
Current test capacity is 16 model requests per task and 64 globally, with shared
HTTP capacity 256, DNS workers 16 and write workers 32. Queue work is deferred,
not complete. The active objective remains a complete enterprise research report
from the uploaded files, with measured real parallel execution.

Further accepted requirement: autonomous subagent orchestration must combine
dependency readiness with a queue-capable execution pool. Only ready work enters
the queue; active concurrency does not determine how many jobs may be planned.
Actual completed/failed/partial results update dependent work and research plans.
Do not equate an explicitly requested three-child smoke test with autonomous
planning acceptance, and do not hardcode three business branches into the pack.

The next full-task candidate thr_a7751cec5886a7c88a3b /
attempt_d1d97c0da7a6f9bc demonstrated this planning/admission gap: the parent
identified three independent objectives, but the committed action selected only
price-analysis. Delegation of other accepted objectives was rejected because
questions had to match that single pending action. Only child-price started.
The run was cancelled at about 199 seconds; it is not a three-branch success.
First isolate explicit three-child execution capability with a small shared
inspection goal, then implement dependency-aware autonomous admission/queueing.

The diagnostic build passed readiness (backend 17626c7082c7321d2873999a626da31676e23d70d4301be22faace8a208259a1,
native ca9606161dc2d9702d635191d125f0709ca9ada2c695c2da75ca4f06491025ba).
Its scoped cache cleanup completed. The next visible trial was
thr_f27f719302738155fcf4 / attempt_2ae80b3a358da64d.
Three children started at 16:00:30 UTC. One failed with the actual diagnostic
503 relay_capacity_reached. Other children searched the wrong directory for
inputs. Cancellation completed at 16:00:59 UTC, about 96 seconds after start.
Receipts: ROOT/outputs/research-round-efficiency/parallel-generation-diagnostics.

Confirmed implementation defects:

- ProviderRelay still allowed only two simultaneous requests per task, while
  application delegation admitted three branches. This limit bypassed the
  capacity registry and debug interruption.
- Child sessions omitted the host's staged source manifest. Uploaded sources
  live outside the writable parent directory, so that directory was not a
  sufficient source reference. Children now receive the verified source
  metadata without parent workflow or conversation history.
- Further audit found fixed shared HTTP pools, a fixed native HTTP connection
  cap with silent socket close, a fixed RPC frame queue, delegation history
  pruning and reply shortening, and duplicated MCP limits in Python and JS.

The source candidate moves these operational capacities into the shared
registry. Debug overflow carries a typed failure; the relay cancels the task
and revokes sibling requests. Normal history/reply trimming remains a soft
policy. Ordinary queue waiting is retained; debug reports a full queue before
continuing. MCP errors retain capacity details across its private bridge.
This candidate is not yet deployed or live-verified.

The audit is NOT complete. Remaining findings include native task admission
and record caps with generic errors, context/catalog count caps, intent input
caps, business dependency document limits, and presentation-only excerpts.
Some old MAX constants are unused compatibility exports. Check call sites
before treating each match as an active execution cap. Diagnostic SSE excerpts
and shutdown polling are distinct from task deadlines. Keep all findings in
the same audit rather than declaring all limits unified.

## Comparison

The historical first-generation reference is attempt_d4c5e19802c068ac:
263.895887 seconds, 31 parent model responses, no children. It produced a
limited usable report. The later 11-minute review is a different task and is
not the comparison baseline. Runtime changes prevent a strict same-version
A/B claim against this historical reference.

## Cancelled parallel trial

Thread thr_db065428650f1a985ce9, attempt_9b37fad113823a33 used the same four
uploaded source files and original request, with one extra instruction to use
subagents for independent analysis. The application upload API checked all
four file hashes. The session was opened in the user's Chrome browser.

The task started at 2026-10-19 15:34:08 UTC. Price, flow and renewable branches
started together at 15:35:20 UTC. Renewable analysis failed after about three
seconds. Repeated child bash failures followed. The task was cancelled at
15:37:19 UTC, after 191 seconds. This proves overlapping child starts only.
It does not prove successful parallel analysis or a performance gain.

Receipts are in ROOT/outputs/research-round-efficiency/parallel-generation-api.
The original failure cause is unknown: the runtime discarded child tool result
text and replaced the model diagnostic with model_transport. No claim of an
upstream outage, missing dependency or timeout is supported by this record.

## Diagnostic repair

The private child runner and delegation channel now retain tool arguments and
results until the host boundary. The host validates the committed parent and
child identity, applies the existing tool-activity redactor, and removes raw
frames before public transport. The worker passes that projection onward.
Actual model failure text reaches the same host boundary and is redacted.

The App now accepts the host's start/end activity names as well as legacy
tool_execution_start/tool_execution_end names. Child failure causes and tool
result excerpts use existing disclosure elements. No typography or CSS changed.

Focused checks: 30 JavaScript runner/delegation checks, 48 Python bridge checks
(one skipped), 19 App checks, and TypeScript validation passed. The added App
projection case also passed. These are source checks, not live acceptance.
The canonical local rebuild is running in /tmp/child-diagnostics-rebuild.log.
After readiness, repeat the same uploaded task and stop promptly if systematic
failures recur. Preserve the concrete diagnostic before choosing a repair.
