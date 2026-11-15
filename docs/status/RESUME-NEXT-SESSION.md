# Live Session Checkpoint

Updated: 2026-11-15. Row-reference goal COMPLETE. PR113 implementation merged dc2aa71a; PR114 closeout merged51fc1cc1. Actual dev/origin/dev51fc1cc1. Approved CI43650887728 passed212seconds and docsCI43678586237 passed130seconds. No further CI approved or started.

Runtime remains accepted dc2aa71a, identical product code after docs-only PR114. API/three workers healthy on image636f0cb736dc97a3c957dc98d3600cfb4c8d20611b50da007f808ae0c103c358. App5173 restored reportv4/series5 and original tablee23e20be. Original projection unchanged; reportv4 resolves. Cloud/demo unchanged. Actual dev graph browser verified51fc1cc1 node distinct from deployed dc2aa71a.

New direction accepted by user: large-resource on-demand work. Current unit is design research only; planning backlog. Owner capstone-agent/capstone-app; research/resource-range-design-20261115 fromdev51fc1cc1, destination reviewed design todev. Written proposal: docs/superpowers/specs/2026-11-15-resource-range-read-design.md. Reuse existing upload/resume, GB transfer/scan, native tools and ResourceUploads.read. Do not reimplement uploads. Proposed first slice: bounded range reads and durable read receipts; full processing checkpoints and sharded indexes remain later requirements.

Next: request written design review, then writing-plans after approval. Do not start implementation or CI merely from the prior high-level direction/CI approval. New model-facing/internal resource protocol must retain frozen source ownership, exact bounds, no full-file staging for a small read, durable admission, scope isolation and accurate coverage. Follow current application/Kernel/Authority boundaries.

All row implementation/design/closeout branches closed. Detached recovery .worktrees/result-row-selection synchronized51fc1cc1. Stashes42b8f54f,0f46f231,554673f2 preserve previous drafts; older stashes and unrelated worktrees/data/auth remain. Do not delete root var/. Root runs/result-row-validation-20261115/ keeps real evidence; /tmp/rows-pr114-ci.log holds final docs CI. New design/control snapshots may remain task-owned drafts until accepted package integration; stage only exact owned paths.
