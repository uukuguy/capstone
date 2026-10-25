# Streamed thinking and task presentation

Local candidate verified; dev PR integration pending. This is an affected-scope
development check, not a release or professional-solver acceptance.

## Behavior

Every instruction shows initial thinking during submission/queueing. Actual
SDK displayable thinking deltas stream in a separate public attempt-bound channel.
Signatures, encrypted/replay metadata, diagnostics and answer text remain separate;
trajectory capture stays redacted. No extra model call or reasoning flag is forced.

Actual admitted task organization selects task steps whether or not resources are
uploaded. Direct tools without organization select the tool chain. Goal notes and
host lifecycle timing do not create task organization. Initial thinking folds
in place before the answer on takeover; its archive also remains in the execution reader.
Direct replies fold thinking on completion and permit reopening. Cancelled/failed
records retain their status; late thinking never resumes the old phase.

## Verification

- Backend176focused tests passed3.91s; actual pinned SDK SSE fixture passed0.14s.
  It verifies supplied reasoning_content, no forced reasoning_effort and redacted
  trajectory capture. Python types report zero errors/warnings.
- Frontend138focused checks passed6.43s. Subsequent targeted transition/replay
  checks passed17tests1.61s; TypeScript and diff checks pass. Counts overlap.
- Canonical local rebuild succeeded. API/threeworkers share imagec5eb1817e993;
  native imaged5c9e90243ca. Seventy-seven runtime-file comparisons against98c9dc58
  match all roles. Later changes are frontend/document-only and use the same
  verified backend image. Main App5173 serves the candidate, with its source
  identity exposed by the existing build receipt. Scoped cache cleanup passed.
- Real DeepSeek response attempt2698ed35c0f1aaaf completed6.079s and produced
  14public thinking deltas/823characters. They are not answer text or Authority
  evidence. Saved source/event/product receipts remain in ignored operator outputs.
- The user's report history was replayed without rerunning analysis: the exact
  visible record again shows5task steps,59tool calls and5m37s. Frozen data bindings
  helped diagnose the regression but do not determine the final presentation rule.
- A no-upload organized task and an unorganized direct tool chain are covered
  separately. No complete solver/professional suite was repeated.

## Limits

Models that return no displayable thinking retain an honest status indicator.
Legacy professional raw message updates remain diagnostic; Authority and evidence
contracts are unchanged. Cloud/demo/user-local deployments are not part of this
local change.

## Task-state isolation follow-up

The same-thread bare process-list request at Attempt450adcea still returned
historical zero-task claims after the policy-only c6e8a26b rebuild. It executed
no tools. This is a failed semantic acceptance, not a passing process scan.
Native saved-request inspection confirmed the new bare instruction and a unique
parent Attempt/task identity. No old report was resumed by the executor.

e5d863a2 now marks historical user/assistant text as historical data, preserves
current accepted input, and labels research summaries with an immutable
attempt/turn owner and research-bookkeeping scope. Compact recovery windows retain
the scope. An idle controller cannot prove zero live OS processes or zero tasks
in other attempts. Real Attempt372b929a retained the new scope disclaimer but still
interpreted the request as child-task status. It performed one native research
read, not an OS observation. Earlier operator notes missed this native event;
that was not a fabricated or lost tool call. This alone did not pass OS acceptance.

Focused checks: 34 Node research/context cases; 31 Python context/research cases
passed with one opt-in Docker case skipped. Cancellation/lease/terminal consumer
checks passed26 with11 PostgreSQL cases skipped in that test invocation. These
checks do not replace real local-ledger acceptance. App timing/call-trace checks
passed142 in6.81s, TypeScript clean. Historical Attempt958c browser replay now
shows both Thinking and total duration13.4s and a confirmed text-only response
as "未调用工具". Historical event truth is not rewritten.

4a28c993 changes the assembly boundary itself: cross-attempt messages are now a
single read-only reference packet retaining their source roles, statuses, IDs and
original content. They no longer become the new executor's own assistant
trajectory. Current-task SDK messages remain unchanged. Fourteen focused context
cases passed. Subsequent live checks and the final boundary are recorded below.

## Final implementation and acceptance boundary

- 8b58e9ff supplies host-owned current-native-task status separately from research
  bookkeeping. It includes capture time, task/parent Attempt IDs and explicit
  unknown scopes for other tasks and OS processes.80context/server checks passed
  (one Docker opt-in skipped); focused Python types are clean. Two local HTTP
  checks initially used the host proxy; they passed with localhost in NO_PROXY.
- 45b7b5a3 fixes unconditional retained-Work context injection. A positively idle,
  unstarted controller no longer adds old research state to ordinary instructions.
  On-demand reads, active-state injection, compaction and request guards remain.
  An idle-to-active change after preparation is rejected.35Node cases passed.
- 0dcbd466 separates retained research-record goals from current graph/progress
  goals. The old report is no longer labelled as this process task's goal.
 134App cases and TypeScript passed; actual browser replay shows the Linux-process
  goal, retained-record disclosure,1task step/10tools, Thinking before the answer.
- Same Thread5b and Workebe retained their report history. A new, ordinary current
  instruction to list Linux PID/name values in the isolated environment produced
  fresh Attempt9e33804c, executed native tools and delivered5observed processes.
  Work and current Attempt were observed running under that exact new ID, then
  completed/current-null. No old report task resumed. Scope is the native
  container, not the Mac host. Duration123seconds is correctness acceptance,
  not a performance pass; planning depth and missing-ps fallback remain efficiency
  work. Original process artifacts are retained in ignored operator outputs.
- Final canonical local rebuild: API/threeworkers6c6c8b956ebf, native11c0da509403.
 77task-owned source comparisons plus2shared native tool mirrors match0dcbd466;
  readiness and scoped cache maintenance015648-52956 passed. App5173 serves the
  candidate. No cloud/demo/user-local release is claimed.
- Independent bounded review found no Important/Critical blocker, including the
  final current-goal correction. Scoped macOS CI40218940390 passed atfcff367f;
  the final frontend/doc follow-up still requires its updated PR gate.

The bare phrase "active processes" remains semantically ambiguous in this report
conversation: the model often reports zero child tasks with an explicit scope
disclaimer and identifies its own native task as running. This is not acceptance
of an OS scan or universal intent resolution. The explicit Linux-process path
above is the observed execution/status acceptance. Tool truth comes from native
and public events, not counts asserted in answer prose.
