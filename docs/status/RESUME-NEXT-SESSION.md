# Live Session Checkpoint

User approved the execution reliability/session capacity design on 2026-11-03.
Implementation branch: feat/execution-capacity-20261103 in .worktrees/execution-capacity.
Root dev and origin/dev remain f7d40163. Main remains0b68c607. No CI is approved.

## Delivered candidates

- f0e8728e: accepted design and plan.
- e7d7fbc2: actionable observation read-budget recovery with exact refs and safe pages.
- 692fa36e: bounded native slots, compatibility default1, local candidate2; waiting cancellation is immediately terminal.
- fcad0a76: ship helper in native image and update queued-cancel consumer assertions.
- Existing plan/reuse/table/report mechanisms retained, no business routing or automatic retries.
-132 ledger/worker tests including real isolated PostgreSQL pass;161 HTTP/native consumers pass/32 platform skips.
-83 App projection/thinking checks and131 CI contract checks pass. Focused types zero errors.
- Independent reviewer spawn failed twice due unavailable configured model; self-review is not independent review.

## Active operations and exact environment

Canonical local rebuild from fcad0a76 passed with API/worker image95190175.
First rebuild omitted helper COPY and failed readiness; fixed. Second override
mounted empty gateway folder. Corrected by removing that override and reusing
the absolute protected directory from the original root deploy/local.env.
Current rebuild log: /tmp/capstone-capacity-rebuild-configured.log; poll its exec
session94387 if still active. Do not mark real acceptance passed yet.
Original auth files remain in root and were not copied into this worktree.
Use COMPOSE_PROJECT_NAME=capstone, DOCKER_CONTEXT=orbstack and root local.env,
root verified PyPSA assets, root resource-policy directory. Set native slots2.
Do NOT override CAPSTONE_DATA_GATEWAY_CONFIG_DIR: local.env already sets its exact absolute path.

## Next actions

1. Finish canonical readiness and scoped cleanup.
2. Real three-session test via runs/execution-capacity-20261103/acceptance.py in
   root checkout. The first submission was rejected409 because the wrong mount
   made gateway registry unavailable; three empty test threads remain in workspace
   capacity-acceptance-20261103. No model calls occurred in that attempt.
3. Verify two active native tasks and third queued, UI queue after refresh,
   cancel queued task, keep unrelated tasks running, download product hashes,
   continue and refresh. Existing Vivaldi local tab42 is reusable; leave intranet tab38 alone.
4. Complete focused CI route session-capacity. Uncommitted workflow/ci_scope/new
   route tests pass131. No push/PR/workflow run until separate user approval.
5. Update canonical worklist and actual dev control graph; preserve root snapshots.
6. Prepare reviewed scoped PR, ask for one macOS CI only after local result is concrete.

## Preservation

A temporary isolated PostgreSQL container capstone-capacity-test-pg on orbstack
uses trust auth bound127.0.0.1:32768 and tmpfs, no user data. Stop/remove only that
test container after use. Test DSN is postgresql://postgres@127.0.0.1:32768/postgres.
Evidence and helper script: root runs/execution-capacity-20261103/.
Tests/logs: /tmp/capstone-capacity-*.log.
Root has task-owned six final control snapshots and the proposed design/plan
copies; preserve unrelated docs/reports/2026-11-01-summer-session-audit.md.

Research server is disconnected. Do not probe or deploy.
Prior intranet source25c71f85 and tagintranet-20261103-1206-25c71f85 remain historical verified sources.
No full release, historical summer replay, or measured speedup is claimed.
