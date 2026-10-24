# Session view retention and bounded memory cache — 2026-10-24

The shared workspace previously rebuilt a session whenever navigation selected it.
This discarded conversation and resource-pane reading state and repeated host
version negotiation and full store preparation.

The App now retains recently visited session views with React Activity. Hidden
views pause their effects and event subscriptions. A return resumes existing
state and normal host event catch-up. Retained DOM order stays fixed so report
iframes keep their browsing context. Preview URLs belong to the retained session
and are released when that view is actually removed.

“设置 → 最多同时保留会话” controls the memory maximum; the default is5 and supported
choices range from1 to20. Navigation records recency and evicts the least recently
visited inactive view. Reducing the limit applies immediately. The active view
counts toward it. Automatic eviction does not archive/delete the Thread, submit
a command, cancel server work or change Authority data.

Access-scoped browser disk snapshots contain only presentation values and scroll
offsets: active pane/product reference, answer folds, selected grid collection,
panel layout and reading positions. Reopening an evicted view uses current host
data and normal product resolution, then restores saved presentation state.
No file bytes or credentials are added to browser storage. Embedded opaque HTML/PDF
document internals remain preserved with memory-resident iframe DOM; the disk
snapshot does not extract them or relax the existing iframe sandbox.

Verification:
- Full App932/932 in82files; TypeScript and doctor pass. Production build and the
  final focused checks are recorded in the evidence logs.
- Integration covers A→B→A, A→new→A, distinct conversation/resource DOM and scroll,
  expanded layout, LRU release/reopen and zero command submissions. The old event
  stream signal is aborted when switching away. Cache unit checks cover limits,
  disk view isolation and preview-URL lifetime across hidden Activity.
- Real retained report check: conversation180px→180px; original main/report/frame
  markers retained; full snapshot requests on return0. A separate exact check
  preserves iframe scroll220px→220px. The629ms browser return sample includes the
  existing click delay and automation waits; it is not a general latency claim.
- Real limit1 check: old DOM is disconnected, exactly1session view remains, and
  reopening restores conversation165px and the same selected HTML report from the
  normal host reader. The first attempt exposed default autoscroll overriding a
  restored offset; reading restoration now suppresses it until explicit latest
  navigation or a new message.
- Canonical rebuild and runtime identity checks are saved separately. Backend
  c64fbe52c992/nativeada86461950c;118runtime source checks/readiness/App pass.
  No real model run, user-session mutation, cloud/demo deployment or Git merge.

Root evidence: outputs/orchestration-repair-20261020/workspace-reading-20261024/.
Source identity: workspace-reading-accepted-hashes.json and model-workspace-reading-accepted-deployment.json
in its parent. Browser/test/build/rebuild logs retain exact outcomes, including
the failed first disk-scroll check and the corrected result.

Final25October runtime receipt: backendc64fbe52c992/nativeada86461950c;
118source/readiness/App checks pass. Canonical cleanup receipt000145-64738 and
post-use scoped cleanup pass. Full932App checks took11.62seconds; production build
and122final reader checks pass. A further reconnect regression first failed:
empty successful catch-up left the retained store reconnecting. Catch-up now
restores the live connection state while retaining the existing snapshot.
Existing build chunk/import warnings and expected protocol-negotiation409s are
not new failures. Rebuild-time502s are kept in browser logs, not hidden.

Design: [session view cache](../superpowers/specs/2026-10-24-session-view-cache.md).
Implementation remains in fix/workspace-reading-type with accumulated cross-package
work; this local verification does not approve that full scope for integration.
