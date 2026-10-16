---
name: pandapower
description: Structural preflight and base-case analysis through registered Capstone semantic tools.
---
# PowerSkills pandapower workflow adapter

Adapter: capstone-powerskills-pandapower/1. This is original Capstone guidance.
Workflow source: Power-Agent/PowerSkills, commit
05bda3a51d5f1ecad888d4d4663c28478c643a7e. The original scripts and text are
not execution permission. Use only the published tools in this session.

1. Use `model.list` and `context.open` to select the registered model. When
   the application supplies a context, keep that context. Never replace it
   with an upstream sample. Read bounded facts with `context.get` and
   `model.dataset.*`; use `model.element.get` for stable element references.
2. Describe `diagnostic.structural` with `analysis.operation.describe`. If
   availability is unavailable, report that condition. Do not claim a passed
   audit. If available, call `analysis.run` with the current `context_ref`,
   `operation: diagnostic.structural` and `options: {}`.
3. Use the returned `result_ref` with `result.dataset.describe` and bounded
   `result.dataset.query` on `result.res_structural_audit`. Findings identify
   severity, code, message, element kind/index and Authority-bound subject.
   Preserve the current revision and evidence references. An audit_status of
   error means that the audit ran and found errors. It is not a transport error.
4. Read the returned coverage and provenance. The PowerMCP structural audit
   checks bus service/voltage limits, line parameters/ratings, transformer
   ratings/impedance and unsupplied topology. It does not prove power-flow
   convergence, operating security or absence of every input defect.
5. When needed, run the base case with `analysis.powerflow.ac.run`. Inspect
   the persisted result before an outage study. Use `model.constraints.describe`
   and `analysis.result.violations.evaluate` for model-owned limits. Do not use
   an upstream global default as a registered model constraint.
6. For an N-1 study, select current stable branch references and use
   `analysis.contingency.n_minus_one.run` within its published bound. N-2 is
   unavailable through this adapter. Arbitrary import/export, source scripts,
   conversion, raw Python, native file access and mitigation playbooks are
   unavailable unless a separate published contract explicitly supports them.

Only current-run Authority-admitted results and evidence support model claims.
Guide access verifies this guidance was loaded; it does not create model facts.
