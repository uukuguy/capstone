# Live Session Checkpoint

> Updated: 2026-11-03 10:07. **Session remains active — not a final handoff.**

- User requested a tag and merge into main. Tag milestone-managed-resources-20261103-771259a7 is pushed at771259a7.
- Main PR87: https://github.com/uukuguy/capstone/pull/87, head release/managed-resources-20261103 at771259a7. Not merged.
- User approved one macOS/Linux release CI. Run41563425683 failed on both platforms during governance: stale workflow tests selected the milestone job instead of scoped job; PR branch filter missing. Full release tests not reached.
- Local fix9a3f75db on dev selects the correct scripts/matrix and restores PR target filters.129 focused tests pass in1.27s. Not pushed. New CI requires new explicit approval before updating PR head.
- Local doctor and whitespace checks pass. Control register/index updated; graph refresh in progress.
- Local runtime6b28807a and intranet70c42dab unchanged. Do not connect to offline research server or deploy implicitly.
- Full model install-and-use conversation remains unverified. Preserve all installation scope limits in docs/reports/2026-11-03-managed-resource-installation.md.
- Preserve unrelated untracked docs/reports/2026-11-01-summer-session-audit.md and all user data.

Next action: obtain approval for one new PR87 macOS/Linux full release CI, then update its head to include9a3f75db; merge only after successful checks. Preserve tag identity.
