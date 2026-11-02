# Parallel outcome planning — 2026-10-24

## Accepted refinement

The organization engine prefers separate ready tasks for independently useful requested outcomes. Shared read-only inputs or a common discovery result do not require merging. Genuine coupled interpretation or substantial duplicate computation may justify a cohesive task. The engine submits all currently justified independent outcomes in one batch after discovery, keeps real dependencies explicit, and plans later work incrementally. There is no fixed branch count, application-specific topic list, extra quality gate or model call. Internal read/code/run/check phases remain one execution intent.

Generated scripts begin with a short plain-language action comment, without a label prefix. The process trace displays that leading comment when present, otherwise the actual command after a simple leading workspace change. Full operations remain available; an intent is not an execution result.

## Prior completed comparisons

| Run | Elapsed | Model calls | Plan |
| --- | ---: | ---: | --- |
| Sequential 055859 |544.609189s|68|Discovery, three analyses, report|
| Parallel 063235 |412.363329s|62|Discovery, price plus combined outflow/renewables, report|

The first parallel run is132.245860s (24.3%) shorter than the sequential reference. Two analysis starts differ by0.2474s. The combined branch lasts111.222s, price48.628s. There are no task-return tool errors; two parent protocol errors and seven child bash errors remain recorded. The report node takes139.111s. Planning and admission fixes differ, so the entire reduction cannot be attributed to concurrency. The historical145.914727s baseline is archived, not a current acceptance gate.

## Verification

The new SDK prompt regression failed before the change and passed after it (28 SDK tests). The action-comment regression failed before implementation;45 related App tests and TypeScript checks pass. The canonical local rebuild uses existing verified local PyPSA model assets; its first preflight correctly stopped on an absent worktree-local asset directory before building. No model task was running at rebuild. Exact runtime source verification and one full original parallel request follow the rebuild.

The completion-control design is recorded separately. Product retention/advisory behavior is deployed; a configurable validator registry and completion hook are not yet integrated.

## Three-branch full run 065314

Thread `thr_5b5621f93b94fb538c66`, Attempt `attempt_112c16ed8ea80677`: completed in336.512660s,59 recorded tool calls (58 start records; one malformed return has only an error end record) and59 model responses (14 parent,45 child). Original request/four resources unchanged, concurrency3. This is38.2% below the544.609189s sequential reference and18.4% below the preceding412.363329s two-branch run; neither comparison isolates concurrency from model planning/output variation. Historical145.914727s is archived, not a current acceptance gate.

| Task | Wall | Model requests |
| --- | ---: | ---: |
| Source inventory |56.374s|8|
| Price |64.628s|8|
| Negative-price exports |69.578s|8|
| Renewable consumption |63.739s|10|
| Report synthesis |83.355s|11|

The three analyses were planned in one batch after source inventory and started within0.606155s. All three completed before report synthesis. This verifies actual concurrent execution, not a front-end grouping guess. Seven CSV/HTML/Markdown products were downloaded and hash-checked; the primary HTML is1,797,427bytes with9 embedded images. Numerical/content acceptance remains the user's judgment.

Seven recorded tool errors: one producer return was malformed (missing required outputs), two source-path assumptions, two report bash errors and two parent graph/coverage parameter errors. These were local corrections; no full-node quality rejection/rerun occurred. The malformed tool submission remains a protocol error, not a claim that retries guarantee quality.

## Startup and finalization diagnosis

Measured from server events: startup12.266689s, including one10.856777s parent model request. Tail62.347899s after the final child ends, including5 parent model requests totaling33.563650s: record, goal review (first invalid result references), corrected goal review, finish, final text. The16.652178s gap between record completion and the next model start is not attributed to provider time; its cause remains unverified. Whole-model/time sums overlap concurrent task execution and are not wall time.

Presentation now includes two special lifecycle nodes, Task startup and Task finalization, outside business task numbering and outside the scheduler. They reuse the shared foldable process record, preserve manual fold state, expose actual main calls and live request time, and include attempt-wide startup/terminal timestamps. They do not add model calls or modify the semantic task graph.

Runtime projection previously truncated shell operations to180 characters before the UI could remove a long working directory. The source now extracts a leading action comment (without a label) or removes a simple leading workspace change before bounding the preview. The underlying tool execution stays unchanged.

## Simple requests

An actual contradiction was reproduced: policy allowed a direct answer, but an idle graph controller returned an initialization continuation after that answer, forcing another planning turn. Regression now proves idle/no accepted work returns no continuation, including goal-driven advisory mode; accepted graphs still require explicit delivery settlement. The first model turn chooses direct answer, one cohesive operation or incremental task organization. No classifier request is added.

The isolated enterprise organization route still keeps native tool execution in explicit task contexts. A simple operation uses one scoped executor, not a speculative discovery/analysis/check chain. A separate graph-free native-tool execution shortcut has not been implemented; it must preserve source grants, isolation, persistence and product return. No claim of a universally zero-overhead tool path is made.

## Final local verification

153 SDK/runtime tests,293 App/projection tests, TypeScript, doctor and diff checks pass. The idle-graph regression failed before the continuation fix. A real enterprise request “2加3等于多少？只需直接回答。” completed in4.182780s with one model response, zero tools and zero graph events (`direct-answer-20261024-071945`). No classification model request or placeholder task chain was added.

Final local source candidate: backendef748ad9dbeb/nativeada86461950c,116 exact source checks plus ready/App pass. The source adds only process display, bounded operation summaries and idle direct-answer completion after the full336.5s run; the full report has not been repeated on this final display/direct-answer candidate. Canonical scoped cache maintenance receipt20261024-073112-6672 passed. No cloud/demo, Git merge or release claim.

The remaining16.6s pre-request gap and multi-round record/review/finish overhead are diagnosed timing targets, not fixed claims. A graph-free isolated tool shortcut remains future work; current simple operations should use one task with only necessary scope.

## User-confirmed current baselines

| Execution | Elapsed | Tool calls |
| --- | ---: | ---: |
| Three parallel branches |338s|59|
| Two parallel branches |412.4s|56|
| Sequential |544.6s|67|

These supersede the old146s result for current optimization and acceptance comparisons. Three-branch338s/59 is the current reference. Raw server elapsed336.512660s remains preserved, separately from the accepted338s label.
