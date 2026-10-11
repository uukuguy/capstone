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
No recognition prompt or schema hint text is modified by this audit.

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
