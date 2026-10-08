# Thread opened models and instruction grouping: local verification

Date: 2026-10-08. Scope: CONV-06 and the user's instruction timestamp/spacing corrections. Local implementation verified; independent review and cloud acceptance remain pending.

## Result

- A Thread retains a nonempty opened-model collection and one current entry. A new Thread starts with IEEE-39 and an Authority-backed baseline diagram. The composer control shows the current model, opened entries, independent close buttons and the registered directory.
- Open, activate and close are immediate application controls. They do not create an analysis Attempt or call a Provider. Global calculation-tool preferences do not block them. Closing the current entry selects the most recently used remaining entry atomically; closing the final entry is rejected.
- Stable entry identity includes family, model ID and revision. Activation creates a fresh execution Context. Active Attempts, pending changes, Case locks and archived Threads block mutation. Failed preparation leaves the Context, collection and cursor unchanged.
- Closing retains messages and admitted diagrams/layers. Historical replay selects the exact Context and optional Attempt, including after live-cursor compaction. Reopening a historical model requires its original revision; unavailable versions are rejected without loading a different version. Reading history does not activate a model.
- Model membership persists separately from snapshot/1. The new bounded models resource preserves existing snapshot clients. Old servers without this resource retain the prior model-directory path. Immediate and legacy model controls enforce the 64-entry limit.
- Instructions display their committed event time. Today's time uses hours/minutes; older instructions include a date. The full timestamp and timezone are available on hover. Small text sits next to the instruction, with a larger gap before each new instruction and a smaller gap before its own answer.

## Evidence

| Check | Result |
| --- | --- |
| `make doctor check-package-boundaries` | Passed |
| `make test` | Passed across all targets |
| `make test-e2e` | Passed: 39 grid cases and 3 registered-worker tests |
| `make validate` | Offline and scripted suites passed; capability matrix 24/24 |
| Final `make test-capstone-agent` | 560 passed; database cases also ran separately below |
| Isolated PostgreSQL workspace and persistence tests | 32 passed, including concurrent idempotency and exact historical Attempt layers after close/compaction |
| Final App tests/build | 322 tests passed; build passed |
| Registered baseline adapters | pandapower 2 and PyPSA 2 tests passed without Provider credentials |
| Final local rebuild | Ready; API and both workers use `sha256:d6092354b2ce7acfddff8a3530ca2515f2e650e3db63beb79da865d1f74df19e` |

The final capacity check initially queried the old catalog unnecessarily. The existing preparation-failure/rollback test caught this. Workspace synchronization now reuses an existing entry before resolving missing metadata; the final backend suite passed after this repair.

Client tests cover a workspace cursor ahead of the snapshot and a lost model-control receipt. Retrying keeps the original identity and produces one activation. The model-directory checks also caught an initial effect that could dismiss a just-opened menu and Escape propagation in the embedded catalog. Both were repaired; keyboard dismissal returns focus to the composer control.

Background headless browser receipts and screenshots are stored under ignored `output/playwright/`:

- `instruction-grouping-20261008/acceptance.log`: desktop 1200×900, phone 375×812 and landscape 812×375. Gap before the instruction: 32px; gap after its metadata: 4px; timestamp inset: 3px and font: 10px. Four consecutive bulk actions per size moved the instruction by at most 0.094px; the draft survived.
- `instruction-grouping-20261008/individual.log`: individual collapse/expand retained the same button focus and showed the whole instruction at answer start/middle/end. The final reply retained its position. This check does not claim that the sticky button keeps the same screen coordinate when a previously hidden instruction is brought into view.
- `opened-models-20261008/api.json`: real API checks covered IEEE-39's 39-node baseline, PyPSA's six-node baseline, opening/activation, inactive/current close, idempotent retries, unavailable revision rejection, final-model protection and closed case57's retained 57-node history. No analysis Attempt was created.
- `opened-models-20261008/acceptance.log`: real App controls worked with both tool groups disabled. Open/activate/close/exact reopen survived receipt catch-up and refresh; closing while reading history kept that view. After refresh, selecting the history page restored its own diagram. Drafts survived. Menus stayed inside all three viewports; phone/landscape close targets were 44×44px; Escape restored control focus.
- `opened-models-20261008/escape.log`: Escape from the registered model search closes the combined menu and restores focus to its trigger.

## Bounds

This is local acceptance. No cloud deployment, acceptance tag, Provider request or user Chrome session was used. Ordinary AI analysis across the new model controls has not been revalidated through a billed Provider. Existing admission/worker tests and the compound-control client test verify the subsequent command's model Context and cursor.

Historical replay requires retained admitted events. It does not reconstruct records deleted before this change. Baseline diagrams have no calculation overlay or result evidence. The complete unified model/conversion system and CONV-04/05 remain separate work.

Task-owned validation Threads are archived after acceptance. User sessions, ignored authentication and existing `var/` data are preserved.
