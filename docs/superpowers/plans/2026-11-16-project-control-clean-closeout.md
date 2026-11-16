# Clean Project-Control Closeout Implementation Plan

**Goal:** finish the pending control documents with a clean dev worktree and a
current graph, without recursive receipt commits.

**Architecture:** keep the standalone committed HTML snapshot; load an optional
fixed ignored live-state sidecar. Only --live writes the sidecar. The user approved
this design; ordinary execution needs no further design gate.

**Tech stack:** existing Python renderer, embedded browser JavaScript, standard
unittest and Node test runner; no dependency or application runtime change.

- [x] Add failing tests in tools/project_overview for immutable tracked HTML,
  escaped/atomic live data and browser fresh/stale/missing/malformed selection.
- [x] Add generated_at and --live in tools/render_project_overview.py; add the
  optional sidecar/bootstrap to tools/project_overview/template.html.
- [x] Add these focused tests to the existing macOS docs CI step. Preserve
  release/main classification and no Provider/full solver checks.
- [x] Consolidate the9 pending docs. Record ownership and acceptance, while final
  own receipts go to ignored runs. Verify links/symlink/diff/doctor and browser.
Integration contract: commit one reviewable scope; obtain separate explicit approval before one
  CI-triggering PR creation. After merge, preserve receipts, sync/retire branch,
  refresh with --live and prove both worktrees clean. Do not edit tracked files
  after that final merge merely to record its own outcome.

Local implementation evidence:2 Python and3 Node checks pass;271 governance
checks pass with3 skips in7.55seconds; doctor, links/symlink/diff checks pass.
The real --live invocation preserves tracked HTML bytes and Git status. Existing
Vivaldi tab verified missing-sidecar snapshot fallback and restored live mode.
Read-only independent review completed with no actionable defects. Exact future
CI/merge/cleanliness receipts belong to ignored runs/project-overview, not another
tracked edit of this completed implementation checklist.
