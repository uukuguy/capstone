# Autonomous computational research: first experiment

Status: experimental implementation authorized by the user on 2026-10-11 after
agreement on the research-loop architecture. This is a bounded first experiment,
not acceptance of a complete autonomous research product.

## Goal and ownership

Test whether a persistent, falsifiable research loop can compose published
Authority actions, revise its next experiment from observed evidence, and replay
the conclusion without calling a model or recomputing a network.

Application owns the experimental runner, strategy interface and budget.
Domain Pack owns the grid study, permitted actions, numerical interpretation and
evidence admission. Kernel remains unchanged. Authority owns every calculation,
model revision and stored result. Default hosted behavior remains unchanged.

## Two-layer scope confirmed by the user

This branch implements a thin end-to-end slice of both layers. The lower layer
must concretely contain a versioned Domain knowledge/method descriptor, composable
workflow representation and independent conclusion verification. Reusing existing
Authority execution alone is insufficient. The upper layer consumes these to
propose hypotheses and adapt experimental paths from observations.

The knowledge descriptor records source paths/digests, version, applicability,
assumptions and evaluation criterion. Workflow steps describe published semantic
actions, typed inputs/outputs, prerequisites and dependencies; each accepted
proposal materializes its execution path. A prewritten recipe is reusable input,
not the set of all permitted paths. The first controlled strategy proves the
interface and evidence mechanism, not autonomous LLM research quality.

These are experimental artifacts for one study. They do not imply the complete
knowledge management, arbitrary workflow synthesis or all-domain validator is
implemented. Generic organization remains separate from grid policy.

## First study

The user selected IEEE-39 and four exact business questions. These replace the
initial illustrative proportional-loss study as the business acceptance corpus:

1. 能否帮我做全部发电设备的N-1校核?按照严重程度列出影响最大的几个机组
2. 如果line7跳闸，帮我分析一下哪些线路会重载
3. 如果母线31下面的负荷变成当前负荷的1.3倍，会不会发生越界等问题?
4. 帮我介绍一下当前电网的基本情况，以及你能做哪些分析

The first case must enumerate actual in-service generating equipment, declare
gen/ext_grid scope and power balance assumptions, preserve the baseline, record
each independent outage and distinguish success, nonconvergence, islanding or
unsupported execution. Never replace generation outages with branch outages.
Severity needs a declared criterion and current-scenario constraints/evidence;
failed calculations are separate unresolved cases, not zero severity or a
fabricated worst rank. A full-check claim requires the full requested population.

The second resolves the actual identity of line7 before deriving the outage.
Report lines and their loading/limit from the outage result, not baseline loading.
The third resolves bus31 and all attached load records; declare whether p/q scale
together and preserve other loads. Check actual available limits and disclose
missing constraint coverage. If the bus has no load, report that fact rather than
create a load or change a generator silently.

The fourth uses model facts and the published capability catalog for a concise
ordinary answer. It must not force a research loop or create simulation evidence
without calculation. Capability availability distinguishes registered dedicated
workflows from potentially composable primitives.

First run controlled proposals with real registered Authority calculations and
evidence replay. Then evaluate a model-driven strategy with the same contracts
and corpus after Provider use is authorized. Controlled proposals do not prove
LLM autonomy; corpus text is test input, never production keyword routing.

## Research protocol

Reference: [Asterion P7 mechanism review](../../reviews/2026-10-11-asterion-p7-reference.md).
Its current autonomous research path lets the model organize useful notes,
computations and grouped experiments. Do not impose a fixed hypothesis ritual
on every observation or ordinary-information node. Capture declared research
decisions and actual evidence, and distinguish chronological adjacency from
causal or evidential support. A later model-driven strategy must own path
selection; the controlled strategy remains only a test double.

The unit of research is an explicit node, not a tool call. Each node carries a
stable id, local objective/hypothesis, typed input references, dependencies and
completion criterion. Its execution contains a group of semantic tool calls and
produces an admitted local verdict with evidence. The strategy chooses subsequent
nodes, branches or revised hypotheses from these outcomes. Record parent edges
and revisions; a finished tool call does not imply a finished node or study.
Separate independent user goals in the corpus. A classified failed scenario may
lead to diagnosis or leave one goal incomplete while other goals continue; an
unknown transport outcome must not be blindly repeated.

Persist goal, hypothesis, criterion, strategy identity, source/environment
identity, experiment proposal, decision rationale summary, exact input, context
and result references, admitted evidence, observation, verdict and next decision.
The record is an append-only hash-linked sequence with a final receipt digest.
Hash chaining detects edits against the recorded receipt; it is not an external
signature or a defense against wholesale replacement of both record and receipt.

Each proposal names a supported study action with bounded typed parameters.
The runner accepts strategy-produced proposals; it does not branch on business
keywords. The Pack rejects invalid or unsupported actions before execution.
Steps are bounded; budget exhaustion is an incomplete outcome.
Failed/nonconverged calculations never become supporting evidence.
Journal/persistence failure is fatal. No automatic replay of an uncertain
in-flight calculation. Saved completed experiments can be read after restart.

## Replay and limits

Replay validates event structure/order, hashes, node dependencies, proposal/result
association, current-workspace Authority artifacts and hypothesis verdicts. Small
model dataset replies are not durable Authority artifacts in the current protocol;
their scope is rechecked through registered read-only queries on the frozen,
verified model context. This is evidence replay with immutable-model readback,
not a claim that all verification is byte-only and fully offline. No solver runs
during replay. It rejects altered
observations and missing evidence, even if the event chain is recomputed.
Saved evidence supports the sampled points only; no claim over an unsampled
continuous domain. Reports expose refutations and unresolved scope.
Re-running the computation is a separate operation with numerical tolerances.

The first slice does not establish open-ended LLM planning, general-purpose
scientific discovery, unattended long-duration operation or all-domain support.
It prepares the interface and evidence necessary to evaluate those separately.

## Acceptance

- Meaningful tests cover falsification, data-dependent next proposals, exhausted
  budgets, invalid proposals, corrupted records and corrupted/missing evidence.
- Real IEEE-39 runs record baseline, line outage and bus-load-change evidence;
  generation outage coverage is counted against the discovered population.
- Each of the four business goals has its own completion/limitation result;
  infrastructure tests cannot substitute for business completion.
- A fresh process replays the saved evidence and produces the same verdict.
- A modified observation with a rebuilt event chain fails evidence verification.
- No raw model, arbitrary Python or host shell becomes an Agent-facing action.
- Report and exact revision are recorded on the experimental branch; no deployment.

## Accepted evolution: Research Model

The user accepted a Capstone-owned Research Model as the basis for autonomous
research. It binds objects, applicable methods, hypotheses, evidence-backed
judgments and unresolved gaps. It persists per research task across turns, with
explicit revisions, scenario branches and invalidation when conditions change.
Ordinary informational questions need not create a full model. Conversation,
research state and actual execution records remain distinct. Authority retains
the physical system model and numerical truth. Historical evidence requires
explicit admission before reuse in a new run.

The controlled prototype verifies grouped execution and evidence; it does not
implement this complete model or prove model-driven autonomy. Persistent coding
and Asterion WorldMap are not mandatory design dependencies. See the accepted
[evolution plan](../plans/2026-10-11-research-model-evolution.md) for R0–R5,
dependencies and acceptance criteria.
