# Clean project-control closeout

User approved the live-state sidecar on2026-11-16. Owner: project-control tooling;
branch fix/project-control-clean-closeout-20261116, destination dev.

The committed PROJECT-OVERVIEW.html remains an offline acceptance snapshot.
The existing page may load a fixed, optional local sidecar from the already
ignored runs/project-overview/live-state.js. The sidecar contains only the same
canonical register/Git projections already rendered by the tool. A new --live
mode updates it atomically without writing tracked files or contacting Providers.

The page uses valid live data only when it is at least as new as its embedded
snapshot and is not dated in the future. Missing, stale or malformed data falls
back to the embedded snapshot. The header identifies live versus snapshot mode.
The control graph still shows real current dev HEAD and exact deployment sources.

Final CI/merge/self-commit receipts stay in ignored operator evidence. Final
branch lifecycle is derived from actual Git/PR state; no tracked file is updated
merely to record its own final merge or commit hash. Do not hide dirty state with
Git flags, delete evidence, change deployment state, or start unapproved CI.

Acceptance: static render works without a sidecar; live refresh changes no
tracked bytes; fresh/stale/malformed selection is tested; existing Vivaldi tab
shows actual HEAD and correct source edges; final dev and delivery worktree are
clean, accepted changes merged by PR, branch retired and exact receipts retained.
