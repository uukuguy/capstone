# Domain Pack sample-specific content audit

Scope: task/answer closure source introduced at2473e48, subsequent repair branch
against devc857837, and the pandapower Pack policy/guides. Test fixtures and
validation samples are intentionally concrete; production rules must generalize.

## Confirmed corrections

1. The overview conclusion always included the generator N−1 gap. It originated
   at2473e48, not the latest repair. Remove it from both English and Chinese
   overview templates. Preserve the separate requested-contingency unsupported
   decision: a generic overview must not inherit an unrelated task's failure.
2. A whole-network selector with full scope was treated as an element query
   requiring a measure. Accept this already-public network scope for powerflow
   and compare, retain the original selector and selected revision, and preserve
   individual-element measure checks. No keyword routing or default metric.

## Supporting guide correction

The endpoint guide maps an unqualified line11 question to ieee39/index11.
Replace that execution default with selected-context and exact-selector rules.
This supports the framework repair; it cannot substitute for resolver, execution
or evidence verification. The user clarified that guide changes are permitted
when justified, but prompt-only fixes must not hide framework defects.
The later prompt audit removes the generator-specific registration reminder from
the model-facing schema rules. Capability availability remains a Pack resolver
decision. The recognition dependency instruction is expressed for all dependent
goals, without an outage/ranking-specific example. System policies and guides must
stay reusable; concrete incident instructions belong only in validation samples.
The network-elements reference had a second bare-label-to-index default and
matching example. Both are removed in favor of established namespaces, Authority
identity lookup and genuine ambiguity clarification.
The topology reference's duplicate mapping is also removed.

## Deployed overall recheck

On0e4deb3, the two standalone context/scope repair cases passed evidence review.
The complete8-case/10-turn run found another whole-network scope rejection in
the overview after endpoint query: the model correctly requested overview but
used the exact `network/all/*` selector. The Pack rejected that representation.
The overview now shares the exact whole-network predicate with powerflow, retains
the frozen selector, and still rejects individual objects, changes and measures.
Real Authority red tests reproduced the failure;49 Pack tests pass after repair.

The old overview mechanical screen also accepted a clarification. It now requires
the admitted information-completion diagnostic; semantic content review remains
separate. The context/scope update includes the continuous overview case, but its
repair verdict does not require a perfect unrelated endpoint answer. No prompt
change is used for this scope repair. The0e4deb3 overall receipt is failed at
semantic review and cannot establish a baseline.

## Retained general contract repairs

- Full published JSON Schema matches existing decoder limits and types. It
  validates proposals rather than adding fixture-specific business actions.
- Null direction is valid for non-ranking tasks; ranking still requires an
  explicit direction. No business choice is silently filled.
- Model metadata comes from registered `context.get`, is bound to revision and
  frozen for replay. Model counts are not copied from IEEE39 sample answers.
- Selector resolution preserves name/alias/index semantics, queries the bounded
  Authority dataset and verifies the unique asset. No line7 or bus31 shortcut.
- Existing-model constraint evaluation and load p/q scaling match registered
  execution contracts; no sample-specific threshold or factor was introduced.
- Unsupported non-branch contingency and exact changed-scenario evidence
  admission remain in the Pack. They are capability truth, not answer decoration.

## Limits and follow-up

The previous overall acceptance is withdrawn after the user's actual AC failure.
The overall corpus now has eight cases/ten turns, separate from upgrade-specific
criteria. The 95 focused checks passed before the additional non-convergence
repair; these checks do not establish deployed business acceptance.

The broader diff review found and corrected:

- Evidence-backed mixed goals could receive a full-coverage diagnostic despite
  unresolved, partial or unsupported goals. Aggregate completion now follows all
  goal statuses; evidence authenticity does not establish full completion.
- Limit and outage answers returned only violation counts. They now project
  verified object identities, values and limits from admitted Authority records.
  An incomplete bounded detail list is explicitly partial.
- Exact index/asset selectors scanned all rows before checking identity. They
  now use typed Authority filters and still verify the returned unique asset.
  Name/alias discovery retains its existing bounded lookup.
- Ordinary AC non-convergence was treated as absent proof with a request to run
  again. Matching verified AC diagnostics now yield a partial conclusion without
  invented operating values. Other contexts, changes and analysis types cannot
  substitute for the requested scenario.
- Contingency results could be certified after filtering out requested violation
  types, or after DC instead of AC execution. Two real Authority counterexamples
  reproduced this. The Authority now persists its actual violation-type filter
  in the aggregate artifact; the Pack requires full recorded type coverage and
  the AC solver operation. Public response fields and defaults are unchanged.
  Old artifacts without scope proof remain readable but cannot certify this task.

Open completion gaps remain: free-text obligations are frozen but are not a typed
output-coverage contract; answer scale can bound displayed ranking entries;
model-proposed missing requirements can preempt Pack resolution; fixed capability
prose does not reflect every possible selected binding subset. These must not be
hidden by a passing mechanical screen or an unconditional completion claim.

The overview's capability prose is still a fixed description of this Pack's
published operations. Making it reflect arbitrary application-selected subsets
requires a registered capability projection; this audit does not invent one or
weaken coverage. Other documented model IDs and aliases are discovery examples,
not execution defaults. The specific endpoint default above was different
because it instructed execution for an unqualified user question.

Do not modify numerical capability coverage, thresholds, defaults or Authority
results to make a deployment sample pass. Repair criteria must cite the owning
contract, preserve unrelated business semantics and verify affected boundaries.

## Follow-up deployment failures

The full Provider run on0e4deb3 exposed a continuous overview whose exact
whole-network selector was rejected.986fc20 shares the whole-network predicate
between overview and calculation and requires verified informational completion.
No system prompt was changed for this repair.

The next full8-case/10-turn run on986fc20 failed explicit-index-outage Attempt
e0cae6bd29f3d372. Recognition, target resolution and Authority calculation
succeeded. The branch-ranking reader rejected a hash-valid, converged contingency
scenario because it accepted ordinary AC results only. It returned
result_integrity_failed, which correctly triggered the Kernel's fatal admission
rule. d7ac7d9 reads the verified scenario's embedded powerflow with matching
context/revision and validated rows; it preserves the original result reference.
The Kernel rule is unchanged.12 related tests, tamper rejection and readback of
the actual failed-run artifact pass. Deployment acceptance still needs the new
candidate's Provider and browser receipts. The prior failed receipt is retained
as provider-overall/provider-9b58a248ae8d4282.json under ignored runs storage.

The10-turn Provider run on d7ac7d9 verifies the repaired outage ranking and final
evidence admission, but fails load-scaling with required_calculation_missing
(receipt provider-62974bed639c41d3). The recognizer proposed complete load-change
parameters and also a missing-input question; the application froze that question
as clarification. A provisional bypass was rejected in review and removed: a
populated payload cannot prove a real user choice is resolved. The next repair
adds one bounded semantic review before acceptance, sharing the two-call/deadline
budget with structural correction. It preserves unresolved gaps and the original
resolution barrier.80 focused checks pass; actual Provider validation is pending.

The760ac0a deployed overall receipt provider-959f4103093540c9 passes all8 cases/
10 turns and independent business review. However, replaying the original missing
p/q-choice proposal through one real Provider review retains that extra question
(captured-gap-review-760ac0a.json). The overall pass does not prove this intermittent
defect is repaired, so input-gap专项 and baseline acceptance remain pending.

The published task contract required concrete power fields but did not define
proportional whole-load semantics. The next Pack repair explicitly accepts
`fields=[]` for whole-load scaling and freezes both power components at the same
factor; explicit component selections remain unchanged. This adds an owned,
reusable business meaning rather than a question-specific prompt or Authority
default.52 Pack checks pass, including the prior failing empty-fields case and
active-only/reactive-only preservation. Source review approves; Provider replay
and exact deployed Thread verification remain separate required receipts.
The schema-override diagnostic replay passes all three real Provider reviews:
the captured redundant gap is removed, the unknown multiplier stays unresolved,
and the explicit undecided component choice stays unresolved. An earlier probe
returned a malformed review and was rejected before execution; that failed probe
is retained. These isolated replay results are not deployed Thread receipts.

On the exact deployed f0d9b41, the redundant-gap and undecided-component probes
pass. The unknown-multiplier review correctly preserves its gap and omits the
factor, but Application schema validation rejects that pending proposal. This
is a second framework mismatch, not a numerical execution failure. Pending
goals now may omit nested required inputs while all supplied values and the
outer shape remain checked. Missing-input resolution still stops before Pack
calls. Without a gap, full validation remains required. The red test reproduces
the mismatch;84 recognition/understanding/resolution tests pass and independent
review approves. The pending/executable distinction is recorded in the owning
framework contract. Exact deployment verification remains outstanding.

The f0d9b41 overall receipt provider-9854b24ca74343f5 fails the explicit-index
outage answer. Recognition and execution are correct: the Authority calculates
the outage with line_overload/non_convergence filtering and reports line11 at
103.329% against100%. The Pack discards that intact aggregate because it lacks
full four-category coverage. This wrongly loses valid evidence; the correct
conclusion is partial, with actual overload details and the missing retained
categories, never a full certificate. The repair retains per-outage coverage,
prefers complete candidates, does not combine filtered results into full coverage
and keeps DC rejection and child/evidence integrity checks. The original failed
artifact now returns partial with the original references, without recalculation.
54 Pack checks plus the independent filtered-union negative pass; source review
approves. Exact-source deployment and Thread acceptance are still required.
