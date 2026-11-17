# Session sidebar stability — local verification

Owner capstone-app. Branch fix/session-sidebar-stability-20261117 targets dev.
Rootdev baseline7531bc1f. Product source399f90f3, reviewed head4ff09235.
PR128 is merged into actualdev f818d2e9. macOS CI43941305783 passed.

## Reproduction and cause

In the existing localhost:5173 tab, selecting another session temporarily reduced
the visible pinned section from10 rows to3, before the older rows returned.
The original screenshot confirms this visual collapse. PostgreSQL retained all
10 pin IDs. SessionNavigation held older-session descriptors in component state;
cold navigation/preparation remounted it before history could refill the rows.

The scoped presentation catalog now owns these resolved descriptors. Navigation
reads them synchronously and refreshes them in the background. A complete history
response retains all current pin descriptors, not only those missing from one
view's recent page. Archive/delete/restore invalidates earlier reads. Cached
metadata remains separate from durable pin authority and task data.

## Checks

Cold-remount row/order/scroll and stale removed-row regressions failed before
the fix. A concurrent-view test then reproduced partial metadata overwriting a
shared cache. Latest focused session-navigation gate passes125 App checks across
10 direct consumers and TypeScript;145 direct scope/governance checks pass.
The new macOS gate excludes solver, release and unrelated application suites.

Canonical candidate rebuild source399f90f3 passed readiness, API/three-worker
identity at image731d93bf07ddcd054b3b704bb5a3adb6bcedb2ac0142429d8226723a331826e8,
and scoped cache maintenance. Existing candidate5174 tab was reused. Five real
cold/warm switches covered DR, lightweight research, Word material analysis and
the data-gateway demonstration. All settled views retained10 pin links in the
same order and showed the selected session heading. Intermediate screenshots
were inspected and kept all10 visible rows. Existing conversations and saved
reports were reused; no new task or model execution was submitted.

Accessibility snapshots can temporarily omit rows while the visible page remains
intact. The preliminary501c90fd AX count9 had10 rows in its screenshot, and one
empty AX subtree also had10 visible rows. These are not visual collapse failures.
The concurrent-cache defect is proved by its independent red/green test. Failed
and corrected diagnostic observations are retained, not relabelled as passes.

Root ignored evidence: runs/session-sidebar-stability-20261117, including original
before/after AX, candidate2-verified-results.json, per-switch snapshots/screenshots
and operation pointers. Scope remains the existing App navigation and shared
read-only catalog. Backend pin persistence, business authorities, credentials,
other worktrees and user data are unchanged.

Independent review dispatch failed Unknown model gpt-6.1-luna. Direct source
review checked namespace ownership, mutation invalidation and retained-view
updates; no independent review pass is claimed.

## Actual dev acceptance

Canonical rebuild from actualdev f818d2e9 completed0. API and all three workers
run imagefaf6c85ab950ee516c33754d367516d773f6799f6d1274297b67eea4912b738e;
readiness and scoped cache maintenance passed. Existing localhost5173 serves the
fix. Repeated switches preserve10 pinned records, order, scroll position and
the correct selected conversation. Saved conversations/products remain usable.
Original10 exact pin IDs still match the durable baseline. Browser snapshots,
screenshots and final identity receipts remain in the ignored evidence directory.
The final control-only PR records this acceptance; its own merge/HEAD receipts
stay ignored to avoid a self-referencing documentation commit cycle.
