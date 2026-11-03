# Live Session Checkpoint

> Updated: 2026-11-03 12:45. **Session remains active; one focused CI is approved.**

## Active local follow-up

The user said continue after deployment closeout. The bounded follow-up fixes the
four offline-installer test failures. No remote-server calls or CI were made.

- Root cause: macOS ls renders a valid0600 file as -rw-------@.
- d599331f uses lstat, regular-file, exact0600 and owner checks. Installer behavior unchanged.
- 01732906 includes the offline tests in the existing focused milestone gate.
- Local branch milestone/offline-selection-mode-20261103 at01732906, not pushed.
- Four reproduced failures now pass; full offline file51 pass8.52s.
- Isolated milestone gate212 pass/3skip9.67s; workflow contracts21 pass0.65s.
- Doctor, links, symlink and whitespace checks pass. No full suite was rerun.
- Actual checkout remains dev ef6effcb and matches origin/dev.

The user approved one new macOS focused CI (212 resource/runtime/offline
tests, estimated1–3min) and PR integration to dev. Publish the candidate,
run that exact gate, merge on success and
refresh actual dev control state. No deployment or main update is part of this fix.

## Existing accepted deployment

- Main PR88 merged0b68c607 under explicit user-approved scoped exception.
- Dev PR89 merged ef6effcb; prior approvals are consumed.
- Intranet25c71f85 deployment and two real tasks/CSV SHA/browser refresh passed.
- Tags: milestone-managed-resources-20261103-771259a7 and intranet-20261103-1206-25c71f85.
- User confirms research server disconnected: do not probe it.
- No full release acceptance, historical summer replay or full model install-and-use claim.
- Deployment receipt: docs/reports/2026-11-03-intranet-release.md.
- Local fixture repair is not yet part of dev/main or the deployed source.

## Ownership and recovery

Keep task-owned final/control snapshots uncommitted pending integration:
docs/status/{VERSION-CONTROL,PROJECT-OVERVIEW,INDEX,JOURNAL,KNOWN-ISSUES,RESUME-NEXT-SESSION}.md
(the overview uses .html), plus the deployment report's final offline note.
The fixture and gate changes are safely committed on the local candidate branch.
Preserve unrelated docs/reports/2026-11-01-summer-session-audit.md.
Do not choose new roadmap work or start more CI without explicit authorization.
