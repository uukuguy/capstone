# Left navigation verification — 2026-10-25

Implementation: .worktrees/model-decision, fix/workspace-reading-type, dirty
candidate at15980389. No merge or cloud/demo deployment.

Two new pin regressions failed before the fix: reveal a hidden React Activity
after a pin change; change the navigation storage namespace. Both now pass.
The pin hook reads saved preferences on effect activation and handles storage
events from other tabs. A frame test checks three collapse/reopen cycles.

Rename Escape previously reached the window capture listener before the input.
The frame listener now uses bubbling and respects editable targets; the input
cancels the draft and stops Escape propagation. Browser measured13px type and
30px input height, with navigation still expanded and no rename submitted.
Pinned row remained visible after sidebar collapse/reopen.

Validation:942App tests/82files passed in11.61seconds; production build, doctor
and scoped diff check passed. Canonical local rebuild passed readiness and role
image checks; backend image e18d8e7d33f2a3decfd77efd3aadc9c8c100916e2a64aaf7c9fa2dd91ca7b78c.
Scoped cache maintenance receipt:
.capstone-agent/cache-maintenance-20261025-012759-74125.log.
Logs: /tmp/sidebar-regressions-red.log, /tmp/sidebar-regressions-green.log,
/tmp/sidebar-app-tests-final.log, /tmp/sidebar-app-build.log,
/tmp/sidebar-local-rebuild.log. Browser image: /tmp/sidebar-verified.png.

Named URL workspaces and the refined missing-session/home design remain pending.
