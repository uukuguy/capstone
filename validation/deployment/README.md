# Deployment sample acceptance

Maintain two separate sets. The long-lived overall corpus
[ieee39.json](ieee39.json) uses real failures observed during agent conversation
development. Each case preserves its instruction, incident source, failed
behavior and semantic acceptance requirements. The initial five cases/six turns
cover generation N-1, line outage, load growth, model overview and a continuous
clarification-to-overview conversation. Add newly confirmed failures to this
corpus; keep resolved cases for regression rather than removing them.

## Business coverage

The JSON corpus is the executable source. This table explains its cases without
adding product prompts or changing capability behavior.

| Case | Purpose | Business acceptance |
| --- | --- | --- |
| `generation-n1` | Original generation-outage request | Explain the actual capability boundary; never substitute branch outages or invent generator severity. |
| `line-outage` | Original ambiguous line label | Resolve the intended identity or explain a real ambiguity; any numerical answer uses that outage scenario. |
| `load-scaling` | Changed-load limit assessment | Resolve actual loads, apply the exact factor, calculate and evaluate the changed scenario, with identified violations. |
| `model-overview` | Basic model and available analysis | Answer both parts from selected-model facts and registered capabilities; no unrelated task text or unsolicited simulation. |
| `clarification-to-overview` | Two-turn target transition | Resolve or clarify the endpoint request, then answer the new overview goal and retain history. |
| `selected-model-ac` | Simplest AC execution | Use the selected model and current-run calculation evidence; no unnecessary element/measure clarification. |
| `explicit-index-outage` | Unambiguous outage execution | Execute the exact outage; identify overloads from verified results or report actual non-convergence without invented values. |
| `flow-to-overview` | Two-turn calculation-to-information transition | Calculate with current-run evidence, then answer the new informational goal without old-task contamination. |

The first six cases retain observed conversation failures. The last two are
explicitly labeled audit-derived coverage gaps. A legitimate capability boundary
can satisfy a boundary case; it cannot satisfy a required calculation case.
These are business acceptance cases, not exact wording or perfect-answer targets.

Upgrade manifests reuse case IDs rather than copying instructions. The
task-answer update checks prefix/contract/metadata repairs; the derived-context
update checks executable derived contexts and exact scenario admission; the
context-scope update checks unrelated overview text, whole-network AC scope and
the overview after an object-query turn. It selects three cases/four turns; only
the relevant overview/scope repair is required from the continuous case.
An unrelated defect is recorded separately from the update's repair verdict.

An upgrade-specific manifest selects relevant cases from that corpus and adds
its focused checks. [task-answer-update.json](task-answer-update.json) selects
three cases/four turns for this repair: generation clarification, model overview
and clarification-to-overview. It records the prefix, proposal-schema and frozen
metadata changes. No duplicate instructions are maintained in the update file.
Future upgrades use their own selection. Tests do not grant production capabilities.

Update acceptance checks the defects addressed by that upgrade. Selecting a case
does not inherit every overall semantic requirement as an update gate. Record
each repair criterion, observed evidence and pass/fail/pending result separately.
For example, prefix removal passes when the formal answer contains no leaked
process or application prefix; it does not require that the same answer also
complete an unrelated calculation. Record other answer defects separately.
They block update acceptance only when they prevent verification of the repair
or are regressions caused by the change. Evidence contracts still apply.
Overall baseline acceptance retains its own requirements.

[derived-context-update.json](derived-context-update.json) is the catalog repair
专项: one load-scaling case with two criteria, valid derived-context execution
and exact frozen-scenario evidence admission. Display quality and unrelated
answer defects are recorded separately.

Run the overall corpus when freezing a baseline, validating broad integration or
preparing a release. Ordinary iteration uses the selected update set and affected
regressions. For this baseline repair, the overall corpus is required before human
handoff because the earlier technical receipt missed real business failures.

[scenario-result-update.json](scenario-result-update.json) selects the explicit
index outage. It checks that a verified converged scenario can be ranked without
an incorrect integrity failure or another calculation, while tampered artifacts
remain rejected. Final evidence admission is checked separately from answer style.

[input-gap-update.json](input-gap-update.json) checks preacceptance consistency
review of proposed missing inputs. A complete load-change request must execute;
real object ambiguity remains a clarification. The review shares the original
two-call/deadline budget with schema correction. Neither a populated payload nor
a passing review alone proves numerical results; normal Pack and evidence
admission still apply.

## Required records

Record the exact commit, API/worker image identity, App source, sample-set version,
model revision, Provider/model identity, each Thread/Attempt, terminal state,
public final answer and current-run result/evidence references. Save bounded
receipts under ignored `runs/`; never include credentials or raw model objects.

An overall sample must finish without a system failure and answer all requested
goals, or state an actual ambiguity/capability boundary. An ambiguity must concern
the user's intended object or business rule; the user must not confirm tool
registration. Model overview must describe the selected network as well as the
available capabilities. Generic capability prose alone does not pass.

Calculation claims need admitted evidence from that Attempt. Unsupported
generation N-1 must not substitute branch N-1 or invent a generator ranking.
Answers follow the requested language; process narration and application labels
such as `Clarify:` must not enter Chinese formal answers. Historical successful
answers must survive a subsequent failed Attempt.

The update set also exercises malformed model proposals before acceptance,
mixed goals, process/final isolation and the running/completed window states.
Run focused regression tests offline, then the same business instructions through
the actual deployed Thread API with the selected Provider, then browser checks.
Scripted transport is a separate receipt and cannot stand in for Provider runs.

Select the scope explicitly after Provider authorization:

```sh
python -m validation.deployment.run --allow-provider --samples validation/deployment/task-answer-update.json
python -m validation.deployment.run --allow-provider --samples validation/deployment/ieee39.json
```

Receipts record the suite identity, scope and hashes of both the selected manifest
and referenced corpus. A successful update run does not imply overall acceptance.
Non-Provider and browser checks listed in each manifest require separate receipts;
the API runner does not execute or mark them passed.

It requires protected `CAPSTONE_SAMPLE_API_ORIGIN` and
`CAPSTONE_SAMPLE_OPERATOR_TOKEN` environment variables. Do not put tokens in
arguments. The authorization switch is required before any network call.
Its receipt is automated API screening only. Fixture-specific checks may compare
exact facts with registered Authority projections and frozen task contracts.
Known process prefixes are regression checks, not intent classification. Word
presence must not establish that a business goal was answered. Semantic review
uses the original instruction, frozen task and admitted facts; an LLM may assist
that review without replacing Authority truth or the product's LLM recognition.
Mechanical answer checks and current-attempt
projection checks cannot prove that the requested scenario, measure and scope
were actually answered. Record and review the frozen task, admitted conclusions
and Authority results against each sample's expected scenario. Read back the
actual Provider/model execution identity; a scripted deployment cannot pass as
a Provider run. Positive screening stays pending until that independent review
passes. Source/image identity, focused update regressions and browser checks
remain required separate receipts.

## Acceptance status

Use separate states: source verified, infrastructure ready, business samples
passed, and human accepted. Any required failure within the selected acceptance
scope blocks that scope's handoff. A skipped or
unauthorized Provider run stays pending. No passing tag or successful deployment
claim may imply that pending business samples passed. Existing technical baseline
tags remain immutable; append a correction to the acceptance record.

The API runner records answer screening observations for the selected cases.
Its aggregate status is not a repair-specific verdict. Review those observations
against the update's repair criteria before deciding update acceptance; do not
turn an unrelated overall-answer failure into a failed repair criterion.

The previous local-dev2473e48 fails this set: the recorded clarification includes an
application English prefix, and overview Attempt28ed976b fails while resolving
a payload without `direction`. Its prior registered-case receipt proves only
the narrower scripted checks. New baseline acceptance remains blocked.

The selected-model AC failure and code-diff audit extend the overall corpus to
eight cases/ten turns. The added cases cover selected-model AC execution,
an explicit index outage, and calculation-to-overview continuity. Calculation
cases require execution and admitted evidence; a clarification cannot pass them.
Audit-derived cases are labeled separately from observed conversation failures.
[context-scope-update.json](context-scope-update.json) selects overview,
AC execution and endpoint-to-overview continuity. Passing criteria concern the
overview text and scope repairs; an unrelated endpoint answer need not be perfect.

The earlier six-turn overall acceptance is withdrawn. It missed the simplest
AC instruction and allowed clarification where calculation was required. Prior
receipts remain historical evidence for their actual scope, not baseline acceptance.
