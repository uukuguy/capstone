# Deployment sample acceptance

Every selected deployment candidate needs both an overall sample set and the
sample set for its changed behavior. The IEEE-39 set preserves the user's four
business instructions and a continuous conversation from object clarification
to model overview. Tests and fixtures do not grant production capabilities.

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

The actual-API runner is `python -m validation.deployment.run --allow-provider`.
It requires protected `CAPSTONE_SAMPLE_API_ORIGIN` and
`CAPSTONE_SAMPLE_OPERATOR_TOKEN` environment variables. Do not put tokens in
arguments. The authorization switch is required before any network call.
Its receipt is automated API screening only. Text screening and current-attempt
projection checks cannot prove that the requested scenario, measure and scope
were actually answered. Record and review the frozen task, admitted conclusions
and Authority results against each sample's expected scenario. Read back the
actual Provider/model execution identity; a scripted deployment cannot pass as
a Provider run. Positive screening stays pending until that independent review
passes. Source/image identity, focused update regressions and browser checks
remain required separate receipts.

## Acceptance status

Use separate states: source verified, infrastructure ready, business samples
passed, and human accepted. Any required failure blocks handoff. A skipped or
unauthorized Provider run stays pending. No passing tag or successful deployment
claim may imply that pending business samples passed. Existing technical baseline
tags remain immutable; append a correction to the acceptance record.

Current local-dev2473e48 fails this set: the recorded clarification includes an
application English prefix, and overview Attempt28ed976b fails while resolving
a payload without `direction`. Its prior registered-case receipt proves only
the narrower scripted checks. New baseline acceptance remains blocked.
