# Workspace navigation and session management — 2026-10-24

## Interrupted-session recovery and final checks

Recovery found that the archive API supported pagination but the navigation had no next-page action. Added “读取更多归档会话”, with its loading guard and retained earlier rows. An older archive request can no longer replace a newer list after closing and reopening the archive. Two regression cases failed before the fixes and pass after them. Returning to the active list retains its saved scroll position.

Fresh App verification: 81 files / 927 tests pass in 10.77 seconds; TypeScript, doctor and diff checks pass. Two existing report-selection tests first failed because the shared test cleanup retained local panel preferences; clearing local storage between tests restores isolation and preserves the original assertions. Existing jsdom modified-link navigation and empty-image-source warnings remain.

Real browser verification uses the existing archived-session API with only its read page size changed to 2. Loading the next page retains 4 distinct session links. Desktop1280px and narrow375px screenshots confirm the existing layout and narrow navigation overlay. No user session or Provider task was changed.

Canonical local rebuild passes with backend c64fbe52c992 / native ada86461950c. All 118 runtime source checks, readiness and App HTTP pass. Root evidence: outputs/orchestration-repair-20261020/model-workspace-resume-deployment.json and workspace-resume-hashes.json. Browser images: implementation worktree output/playwright/workspace-resume-{archive,mobile}.png. Logs: /tmp/workspace-resume-{app-tests,rebuild,doctor}.log.

Git integration remains pending: the implementation worktree contains 219 changed tracked files and 418 new files across several runtime and UI packages. This recovery does not approve that full accumulated scope for merge. Independent reviewer startup failed because its configured model was unavailable; no independent approval is claimed. Dev control records this local verification separately from merge and deployment.

## Implemented

The shared desktop frame permits simultaneous session navigation, conversation and resource columns. Either sidebar can close independently. Navigation defaults to224px; the remaining conversation/resource space defaults to60:40. The left divider and the existing right divider support pointer and keyboard resizing. Width/preferences persist in local storage; a narrow viewport uses overlays instead of forcing three cramped columns.

Ordinary session links use same-document history, preserving modified-click/open-new-tab behavior. Protocol recovery retains the previous usable workspace while selecting the target adapter. An access-scoped catalog cache keeps existing rows visible while new data loads, and retains previously loaded pages. The temporary generic current-session row has been removed. The selected real item gets a persistent background/edge mark distinct from hover, and its scroll container restores the saved position and brings the current item into view without scrolling the page.

New session remains above the independently scrolling list. Pinned/recent groups and an archived-session entry share the same navigation component. Pins are browser-local preferences scoped to the existing access namespace. Both protocol adapters expose previous/next session controls in displayed pin-aware order. Grid refresh and resource visibility controls now use the shared upper-right toolbar.

Rows expose a small close/archival button on hover/focus, context menus via right click or Shift+F10, and a menu trigger on coarse pointers. Double-click supports inline rename (Enter saves; Escape cancels). A short pointer-click delay distinguishes double-click from navigation; keyboard navigation is immediate. Rename uses the existing revision/idempotency contract. Close archives; archived sessions can be read and restored.

Delete is separate and confirmed. The private DELETE endpoint locks the catalog row, refuses active task/case work and deletes the thread-owned ledger rows through existing foreign-key cascades. It neither cancels active work nor deletes external Authority objects. Stored blob bytes follow their storage retention; the dialog states that deletion is not a storage purge. DELETE is permitted in the existing CORS response. Both protocol adapters handle version negotiation for list management, including empty204 responses.

Folded legacy process records have compact2px/4px margins; the existing detail layout and folding persistence remain unchanged.

## Verification

-169 related App/transport checks and TypeScript pass. After the final compact-gap/focus-trap change, targeted navigation/process checks and TypeScript pass again.
-55 backend management/HTTP/title checks pass;2PostgreSQL-fixture checks skip without CAPSTONE_TEST_DATABASE_URL. These skips are not reported as executed.
-Real local PostgreSQL-backed API: two new disposable general-chat sessions were created, renamed, archived/restored, then deleted. Real browser inline rename, pin+reload, hover-close, archived lookup/restore, deletion cancellation and confirmed removal passed. Direct reads after deletion returned404. Only these disposable sessions were changed.
-Desktop1280px: all three columns visible (navigation224px, conversation630px, resource412px including divider layout). Real pointer drag changed navigation to274px; resource preference58% persisted. Pin, title and width survived reload.
-A real enterprise-to-grid switch retained at least128 session links across83 animation-frame samples, without an empty-list frame or inserted current-session placeholder. Grid toolbar actions were present; the resource toggle was additionally restored after discovering its old hide flag.
-New-session button y-position remained fixed while the list scrolled. Folded legacy rows were measured38px high; the initial19px gap was further reduced to approximately11px.

Evidence: ROOT outputs/orchestration-repair-20261020/workspace-navigation-20261024-093711. Runtime identity receipt: model-workspace-navigation-deployment.json. Canonical rebuild and scoped cleanup are recorded separately. No provider task/report benchmark was started. Current338s/59-tool baseline remains unchanged.

No Git merge, cloud or demo deployment is claimed.
