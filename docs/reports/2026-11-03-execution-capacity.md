# Execution recovery and native session capacity

Implementation candidate: `b7dd440c2c72171d20819a7d257f50366e2decb0` on
`feat/execution-capacity-20261103`, based on dev `f7d40163`.
Not merged, not pushed, no CI run, no main or remote deployment change.
User approved the [design](../superpowers/specs/2026-11-03-execution-reliability-and-session-capacity-design.md).

## Changes

- Oversized observation reads return an exact issued reference, pointer and a
  measured safe page. A single oversized item instead directs bounded inspection.
  Recovery does not re-query upstream data or infer business semantics.
- Native worker slots are configurable through
  `CAPSTONE_NATIVE_MAX_CONCURRENT_ATTEMPTS`; compatibility default1, local candidate2.
  Existing leases, per-thread admission and task isolation remain authoritative.
  No unbounded preclaimed queue, new scheduler service or global result cache.
- Unleased waiting tasks cancel immediately in both ledger adapters. Running
  tasks retain their original cancellation/cleanup path. Claims lock the thread
  first and skip busy thread rows to avoid a cancellation/claim lock inversion.
- The process card now says queued while the reply says waiting. Previously the
  card incorrectly said executing/preparing despite an accepted-only attempt.
- Add a bounded `session-capacity` development CI route. Compose and native-image
  allowances accept only the exact setting/COPY additions; other changes fall
  back to their normal gates. Main/release verification remains unchanged.

Existing batch preflight, successful readonly reuse, table validation and report
check-only already worked and were retained. Gateway timeout fixes and automatic
business-window splitting are not claimed. The new recovery is a mechanical
improvement, not a measured overall business speedup.

## Local verification

- Final selected Python gate:411 passed/32 platform skips in41.17s, with an
  isolated real PostgreSQL ledger. Includes claims, cancellation, HTTP, native
  execution, observation composition, report and image contracts.
- App direct consumers:216 passed in6.97s; TypeScript check passed.
- Focused Python types:0 errors. CI/governance contracts:131 passed.
- Actual scope selector returns session-capacity; Markdown links, symlink and
  whitespace checked locally. No GitHub Actions was started.
- Independent Codex CLI review of origin/dev..b7dd440c found no clear actionable
  regression by code inspection; reviewer did not run tests. Built-in reviewer
  spawning was unavailable. Receipt:/tmp/capstone-capacity-independent-review.log.

The dedicated PostgreSQL container capstone-capacity-test-pg used tmpfs and
loopback trust authentication. It was stopped and removed after validation.
No application database was used for unit/integration test fixtures.

## Real task evidence

Workspace:capacity-acceptance-20261103, through the real /api/v1 Thread path.

- A:thr_c0b73d9304a97c8a8986; first attempt3253bd79 completes55.15s.
- B:thr_5eee86184b8be6eb1276; first attemptd1843c01 completes53.82s.
- Their running intervals overlap53.82s; each deliberately includes45s waiting.
  This proves simultaneous execution, not business latency improvement.
- Followups20c8b2e1/8c346d7f complete47.36s/46.08s and read the original CSVs.
- Original and followup downloads contain exactly15 supplied bytes per file.
  A SHA256:3394c5b60086755a0bbf3d549efcfbfc9cd53b91e5669ce864e7ca81a3188f64.
  B and all four download hashes are in download-receipts.json.
- Waiting taskthr_1918434cbe41e1527980 cancels immediately, with no
  attempt_started event. Both other sessions remain running after cancellation.
- A separate running-task cancellation completes through the existing cleanup
  path. PostgreSQL tests also verify competing claims and locked-thread skipping.
- A/B each complete another read-only continuation during the UI trial. Do not
  treat later interrupted trials as successful continuations.

Evidence:root checkout runs/execution-capacity-20261103/, including supplied
CSV downloads, event receipts, queued-before-cancel and queued-cancel-final.
The queued browser screenshot before the label fix exposed the contradictory
process card. The new label is covered by the component regression.

## Local deployment and limits

Canonical rebuild from b7dd440c passes readiness and API/worker image equality:
421ce00d8fd821c7b3ca0157fccbf44127dc8fe8fad73c6f0cb92969114b86c8.
Native image:dc430bffe525e9a028041976ac424818f141319bb2e5bbab02e99a32c73213ff.
App build identity reports b7dd440c, local-dev, dirty=false at verification.
This is a temporary local-dev feature candidate; actual dev remainsf7d40163.
Original named volumes, protected configuration and business data are retained.

Two setup errors were corrected: the first image omitted the new helper COPY,
and a test override selected an empty gateway mount. The final build includes
the helper and reuses the original absolute auth directory from root local.env.
No credentials were copied to this worktree. Scoped cache maintenance applied;
last receipt:.capstone-agent/cache-maintenance-20261103-141803-13648.log in worktree.

Mac sleep interrupted the first real trial and the final long UI trial. Wake
timestamps match lease interruption; expired writers remain fenced. These
trials are retained as failures and excluded from successful timing evidence.
The final GUI check also returned macOS Accessibility permission_denied. Therefore
The GUI became accessible again at19:02. One bounded final check then passed:
the corrected card and reply both show waiting, refresh retains that state,
and queued cancellation immediately clears the attempt. The two other running
test tasks were then cancelled and their slots released. Saved screenshots:
runs/execution-capacity-20261103/queued-after-refresh.png and queued-cancelled-ui.png.
The earlier sleep-interrupted trials remain failures, not acceptance evidence.

Research server remains disconnected and unprobed. Intranet25c71f85, main0b68c607,
cloud and demo retain their prior sources. The user explicitly approved one
macOS focused CI and dev integration after page verification. No full release acceptance is claimed.
