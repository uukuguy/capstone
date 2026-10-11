# Pre-closure rollback and actual local regression

## Decision and exact scope

The user withdrew task/answer closure recovery after original requests regressed.
Product30a3ecb restores packages/configs from c3b78bc, except a standalone,
tool-free LLM ordinary/professional router, separate recognition Provider config
and route-failure diagnostics. Task compilation, goal coverage, answer rewriting,
enhanced prior-result freezing and model prewarm are removed. This is a rollback,
not a new business completion framework or a claim of universal correctness.

Old candidate42a647b is preserved in archive/answer-recovery-before-rollback-20261012.
The unfinished regression patch is saved under ignored runs/. No data, auth,
main/dev history, local-demo or cloud deployment was reset.

## Source and offline checks

- Canonical make capstone-local-rebuild completed from recovery worktree.
- 506 package/config/schema source files match commit30a3ecb in API and both workers.
- All three roles use image sha256:7409a0296765881855cbfc1bc930b47de5a215cea0a6124b796330fbc2b353fe.
- App5173 reports clean30a3ecbb0ded5046402882d54421a2627a6db4ff, local-dev; API8767 is ready.
- 585 framework,105 Pack,379 App tests passed. Focused route/worker/Harness57,
  types, boundaries, doctor and diff checks passed. These are not business acceptance.

## Actual overall regression

The corpus is [stable-execution-regression.json](../../validation/deployment/stable-execution-regression.json).
Original requests use the deployed production Thread API and real Provider.
Seven turns completed or failed with retained raw results, events and tool calls.
The initial9177d5f45be9424b run during service replacement failed transport and is
retained; it cannot count as verification. The ready-source run2e107b34738b4b20
is the actual business record. Its original screening verdict remains failed.

| Request | Actual result | Client time |
| --- | --- | --- |
| Current model and analyses | Full sourced model/capability answer; no solver call |28.335s |
| line7 outage | Calculation returns line11 loading103.33%; old English process prefix remains |40.474s |
| Bus31 load ×1.3 | Fails answer admission after derived-scene tool failures; not accepted |73.084s |
| AC flow | Full result returned; reviewer found violation-row index incorrectly used as bus identity |31.685s |
| Reuse flow, top3 lines | Same flow result;3 read-only calls; zero recalculation; table returned |13.171s |
| Line11 endpoints | Source-backed topology answer returned |9.460s |
| Overview after endpoint | Full current-model answer returned; no solver call |34.223s |

The first new mechanical checker incorrectly treated metadata/topology references
as simulations and required a calculated result for endpoint facts. These are
verification defects, not product repairs; correct expectations are committed.
Do not change the raw receipt or hide actual business failures. Independent review
must inspect original text, result rows, asset identities, tool calls and evidence.

Overall business acceptance is **failed**, despite rollback/source verification.
The user asked for rollback, so these observations do not authorize resuming the
withdrawn closure implementation or adding sample-specific system instructions.
The English prefix and original scene/answer correctness gaps stay explicit.
Complex work duration alone is not a failure; timing is retained without a
universal deadline or claimed routing speed. An overview taking28–34s is still
an optimization observation, not silent task-compilation overhead.

Receipts (ignored operator storage): runs/task-answer-closure/source-rollback-30a3ecb.json,
provider-rollback-ready/provider-2e107b34738b4b20.json and semantic-facts/tool-latency,
independent-review.md, rollback-control-verification.log, rollback-app-verification.log.
Control/browser checks distinguish visible successful answers and visible load
failure. No new accepted baseline, merge, demo/cloud update or research start.

Publication: [PR13 withdrawn](https://github.com/uukuguy/capstone/pull/13),
[PR14 rollback draft](https://github.com/uukuguy/capstone/pull/14), target dev.
Issues2/3 remain open with bot updates; unresolved business defects are not closed.
