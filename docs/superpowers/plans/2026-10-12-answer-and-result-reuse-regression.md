# Restore existing answer presentation and result reuse

User direction: continue the repair of existing behavior. This implements the
approved shared intent/goal-answer design; it does not introduce a new research
framework, question-specific prompts or relaxed evidence admission.

## 1. Keep coverage checks separate from reader text

- Add controlled admission regressions in `test_task_resolution.py`: all supported
  professional goals preserve a complete model final response and all verified
  current-attempt references; partial/blocked goals retain trusted conclusions;
  empty model responses use trusted fallback. Keep mixed general isolation.
- In `kernel_pi_session.py`, evaluate Pack conclusions first. Preserve model
  final prose only after goal coverage and existing Pack admission pass.
  Coverage records remain explicit; they do not certify every prose sentence.
  Do not change final-message-only RPC collection or reference verification.

## 2. Express and execute existing-result requests

- Add bounded optional `result_mode` and `row_limit` to the Pack requirement
  contract. Legacy requirements keep current defaults. Ranking objects must be
  structurally present before goal acceptance, enabling existing bounded repair.
- Update neutral published-field validation to honor declared required and
  optional fields while rejecting unknown fields. No keyword interpretation.
- Existing-mode execution exposes only the Pack's published read capabilities.
  Restore the existing prior-result retrieval path; read/admit evidence in this
  Attempt and verify model/scenario. Do not calculate a replacement result.
- Before persistence, Application hands bounded same-Pack prior candidates to
  the optional Pack reuse extension. Pack verifies scope/scenario and freezes
  result/evidence references. Mixed goals may calculate for another requested
  goal, but cannot substitute its new result for the frozen reuse source.
  Optional extensions do not change the required third-party Provider SPI.
- Pack ranking coverage retains the full input set but displays the explicit
  requested count. No new Authority calculation or business scope is published.
- Test old contracts, unknown fields, invalid counts, empty objects, exact ranking,
  actual reused lineage, absent/mismatched prior results and restricted tools.

## Verification and delivery

- Restore the existing guide's unknown-namespace lookup path through a typed
  `user_label` selector. The Pack checks registered Authority names and aliases,
  freezes a unique asset identity, and clarifies missing or ambiguous matches.
  Numeric labels never fall back to indexes. Explicit namespaces keep their
  semantics. Verify compiler delivery with the original load-change request;
  do not bypass missing requirements or alter system prompts for a sample.
- Publish the existing branch-only operating-measure ranking restriction to
  pre-acceptance validation. Reject complete network/bus/generator proposals for
  these measures so bounded compiler correction runs before a mistaken capability
  boundary is frozen. Preserve network violation-risk ranking and incomplete
  user-input proposals; no branch inference or semantic keyword rules.

- Run focused admission/recognition/Pack/runtime tests, types and boundaries.
  Review the code before a canonical local-dev rebuild.
- Verify exact API/worker/App source. Run actual AC then the original reuse
  follow-up, including tool audit proving no second calculation and three lines.
- Run the strengthened overall corpus with phase timing and independent semantic
  review. Preserve old failures. Standard AC must retain useful computed results,
  not only converge/loss coverage text. Do not use answer length as quality proof.
- Update owning design, canonical worklist, register/control graph and Issues.
  No new baseline or Research R1 acceptance until business regression closes.
