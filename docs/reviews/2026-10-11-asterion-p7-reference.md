# Asterion P7 reference for Capstone research

Date: 2026-10-11. Read-only reference review requested by the user.
Reference repository: sandbox/agentic-2026/asterion, inspected HEAD
4c519ffa468567db3e93f2cb063cade19f21ab91. Its working-tree status files were
modified before inspection and were not changed by this review.

## Evidence and scope

The committed public result file docs/results/arc-agi-3/p7-public-2026-10-07.json
records 25/25 public games, 183/183 levels, local and official score100, and6781
saved-route actions. Its protocol is iterative local research with persisted
experience followed by Competition Mode replay of certified saved routes.
It explicitly excludes cold-start and private/unseen-game claims. The recorded
wheel digest is88deab20a7c0f6da8fd8a091b759f32a3e366cea2627c683407934c061372d59.
This review read local records; it did not rerun the benchmark or query the
official scorecard. Current HEAD mechanisms and that earlier score are distinct.

## Mechanisms and Capstone mapping

| P7 source | Observed mechanism | Capstone experiment consequence |
| --- | --- | --- |
| src/asterion/applications/prime/p7/prompt.py, build_autonomous_prompt | Model selects when to observe, compute, experiment and update useful NOTES; groups actions with a short stated goal | Research nodes contain action groups and evidence-linked local outcomes; avoid mandatory microsteps or a fixed list of business paths |
| src/asterion/applications/prime/p7/research_chain.py | Model statements, computations and actual experiments have separate origins; submitted plans link real transitions | Distinguish proposed explanation, executed workflow and admitted numerical evidence; temporal order alone does not prove causality |
| src/asterion/agents/prime/research_record.py | Bounded passive relationship index; observed_after links; causal_support remains unknown | Keep dependency, chronological and evidential links semantically distinct; hash integrity does not establish truth |
| src/asterion/applications/prime/p7/research_runtime.py | Actual feedback and unknown-outcome state control action continuation | Known node failure can lead to diagnosis; unknown execution state cannot trigger blind retry |
| docs/architecture/prime-p7-world-model-simulator.md | Proposed models are checked against observed history; stale certificates lose planner eligibility | Reusable methods and historical knowledge require current-context applicability checks before use |
| docs/reviews/2026-10-09-p7-bp35-task29-evaluation.md | Actual history supports selected research behaviors, while zero deaths and higher elapsed time coexist | Measure business completion, evidence quality, recovery, cost and time independently; a passed protocol test is not an autonomy-quality score |

## Boundary adaptations

P7's persistent IPython supports game research. Capstone professional sessions
remain restricted to published semantic tools and current-run Authority evidence.
The experiment adopts research organization, not an unrestricted code route to
the grid model. Any future general research computation requires an explicit
isolated executor and typed data/evidence handoff; it cannot silently produce
simulator facts.

P7's passive research index can record omissions without changing accepted
actions. Capstone's required answer/evidence persistence remains fatal. Optional
presentation indexes may differ, but cannot replace the mandatory research
receipt or hide missing evidence.

Freeform research memory and a model-driven planner are required for the eventual
autonomous evaluation. The current controlled corpus strategy is a replaceable
protocol test double. Successful real grid calculations demonstrate the base and
evidence path only. They do not establish that a model discovered the path.

## Immediate experimental scope

Use the user's IEEE39 corpus. Instantiate versioned knowledge/method descriptors,
composable semantic workflows and independent conclusion validation. Each
research node has a goal, typed inputs, dependencies and a local completion
criterion; a hypothesis is optional for observation or information nodes.
Record grouped actual tool calls and evidence-dependent successor selection.
Preserve unresolved identity, balance and constraint coverage as real outcomes.
Use the same corpus and evidence interfaces for a later model-driven comparison.

## Programming and WorldMap: mechanism choice under consideration

The user highlighted Prime's Pi plus persistent IPython foundation: the model
turns hypotheses into programs and progressively builds a WorldMap. This is more
expressive than selecting a stored workflow. For Capstone, the existing Authority
already owns the physical grid model and solver. A research WorldMap should bind
business objects, scenarios, assumptions, constraints, proposed explanations,
experiments, refutations and outstanding questions; it must not silently replace
the Authority model with a generated solver or an unverified surrogate.

| Candidate | Value | Limit |
| --- | --- | --- |
| Direct semantic tool composition | Small change, clear execution and evidence contracts | Many procedural tool interactions; generated representations and search are difficult |
| Single persistent programming surface | Flexible hypotheses, experiment generation, data analysis and search; closest to Prime mechanism | Requires a separate research execution environment, typed data grants, durable code/output and result interpretation |
| Programming research plus registered experiment execution | Combines expressive planning with existing numerical evidence boundary | Requires explicit handoff between research programs, experiment plans and Authority receipts |

The third option is the current recommendation, not an implemented mechanism or
a user-approved change to professional-session access. Use an application-owned
isolated research executor; programs receive authorized bounded read-only data
projections and evidence references, not raw networks, credentials or Authority
handles. A generated typed experiment plan crosses the existing Domain Pack
admission path; numerical results return as verified projections. Programs can
search, compare and propose, while their derived outputs retain code/input/version
lineage and do not become simulator results implicitly. Professional Domain Pack
sessions continue to forbid arbitrary code execution.

Compare candidates with the same IEEE39 corpus, source revision, solver settings
and finite budgets. Measure actual goal coverage, evidence validity, response to
counterexamples, reused verified results, unknown-outcome handling, tool/model
calls and elapsed time. Program text or extra graph nodes alone are not evidence
of stronger reasoning. The current controlled strategy is a reference execution
and protocol check for this comparison, not its autonomous treatment arm.
