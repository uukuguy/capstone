# Action contract context repair

## Observed failure

Original-input trial030015 completed in241.765832seconds, with19parent responses,
zero child responses and ten tool errors. The parent performed downstream analysis
under the source-profile action. Output registration lacked admitted artifacts;
assessment labels did not match the committed checks. Limited HTML/CSV delivery
was saved, while declared analysis and report nodes remained pending.

## Source diagnosis and bounded change

`enterprise-graph-runtime.mjs` projects tool replies and continuations through
`graphReferences`. That projection retained IDs, phases and bindings, but removed
purpose, questions, output slots and check labels. The full definitions survived
only behind an explicit overview read. This is an observed context omission;
it does not prove that context alone causes every planning failure.

The repair keeps a compact `action_contracts` list for ready/executing parent
actions and executed/recorded/assessing work. Each entry copies the exact current
step ID, purpose, questions, expected outputs, declared slots and check labels.
Future definitions, long methods, private file grants and output bodies stay out
of that list. The existing graph/public byte limit still applies. The scheduler,
graph revision rules, evidence admission and model judgment stay unchanged.

This adapter belongs to the application execution layer. It contains no business
stage, domain term, fixed branch count, metric or report recipe. Future execution
adapters can reuse the contract principle without depending on research state.

## Verification

- Added a regression before implementation. It failed because action_contracts
  was absent. It now checks ready, executing and assessment context, exact labels,
  excluded future definitions and excluded private handles.
-141 related JavaScript checks passed in1.32seconds.
-9 actual SDK/host execution-chain scenarios passed in6.41seconds.
- Local rebuild exited0. API/workers3eb83a3c, isolated executor87ea8921;
  55runtime source checks/readiness/App HTTP passed. Scoped cleanup033820-42495.
- Original-input trial033928 completed169.879439seconds:19parent responses,
  zero children,892422tokens and four errors. Both declared nodes succeeded;
  HTML and metrics CSV were admitted as completed primary products and hash
  checked. Source discovery stayed separate from analysis. Independent report
  content quality remains unaccepted. Errors remain before initial planning,
  in the first plan payload and in a revision of an already started definition.
- This is71.886393seconds shorter than030015, but23.964712seconds slower
  than the145.914727second baseline. A single new run does not establish causal
  or stable acceleration. The model still chose a parent-only analysis task.

The repair has not established faster execution or successful parallel delivery.
