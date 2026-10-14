# Live Session Checkpoint

> Updated: 2026-10-14. Active implementation and validation; no final handoff.

## Current delivery

- User approved source-free temporary dev trial: four image classes, linux/amd64 and linux/arm64, default public registry registry.cn-beijing.aliyuncs.com/uukuguy. Docker/Compose only on the user host. DeepSeek/deepseek-flash default; OpenAI alternative from the Provider registry. Keys come from startup environment and reach only workers/config-check. No paid Provider calls authorized here.
- Implementation worktree `.worktrees/dev-trial-deployment`, branch `feat/dev-trial-deployment`, code1c0c60eb35b0078ac41355864774f6ec10d6d2ab. Draft PR22 targetsdev: https://github.com/uukuguy/capstone/pull/22.72 focused Python tests,15 App identity tests and App type checks pass. Independent inline Codex review has no critical/important code findings; override Provider and model together.
- Source/model context builder, bounded runtime, same-origin static App, private per-instance state, platform/source checks and final two-platform acceptance gate are implemented. Final public package not released. Long-term pip/npm CAPSTONE CLI is still separate design work.
- Plan: docs/superpowers/plans/2026-10-14-capstone-dev-trial-deployment.md. Canonical worklist routes currentdev-trial before remainingautonomous scientific/interaction gaps.

## Actual validation

- First source6f29b29 ARM64 candidate passed three registered cases/nine turns, report and evidence replay without Provider. Latest1c0c60e backend/App images built for both Linux platforms. Latest ARM64 stack23573 ready and cases running; latest AMD64 stack22573 starting. AMD64 runs through Docker emulation on this ARM64 Mac; Windows/WSL2 not verified.
- Latest bundles: `.capstone-agent/dev-trial-{arm64,amd64}-1c0c60e-bundle`; private state nested bycapstone-user-check-arm64 / capstone-user-check-amd64. Original6f candidate21573 and its flat private directory remain. Stop owned stacks after verification; never delete volumes or these recovery directories.
- Logs/receipts are in the feature worktree `.capstone-agent/`. Fullmake check-pr retry running: first attempt had906 passes plus a document-only legacy-path wording failure, now fixed; focused repository-boundary tests pass. Required Linux/macOS PR checks run in Actions38584836807.
- Root control graph fixed after user found the new branch missing. The root canonical HTML now receives updates, not only the implementation copy. Nine nodes have real ancestor paths, one focus, four unchanged deployment references; both density ends pass overlap/source/arrow/card/crossing checks.

## Registry and recovery

- User set all four Aliyun repositories public. Separate empty Docker configuration successfully pulled initial App, backend, PostgreSQL and RustFS anonymously. Repeat against final immutable manifests before publication.
- Successful initial pushes: Appdev-trial-candidate-6f29b29-arm64 sha256:252e4f63d9b33988857b9bdcccb470ca9916ae5196c38cdb2f94c6e6ee8b6d22; backend same tag sha256:23e35b0d12a181d59a3abb686f9d0a37b2a6ed933fd039e8ca6ca8d4d8c820e0; PostgreSQLtrial-postgres17-arm64-initial sha256:ba0eda80aab03b51f238853ff304f128b7ff2d9bfbf482d8bde1edc616a3cb11; RustFStrial-rustfs-arm64-initial sha256:95e6a3ddfcb2fe76f32aefed30b4bdd6043b2a4816bcc4808606ffccce3df52d. These are initial single-platform candidates, not final release acceptance.
- Push audit: today_used=4 successful Docker pushes; generic hook reference /3 is recorded, but no task-specific daily push budget or benchmark score was set. Account quota is not verified. Do not invent a release gate from that hook.
- ACR rejects OCI empty-config attestation manifests. Mirror the actual amd64/arm64 images and assemble compatible manifests; preserve child image/config identities. Buildx final registry outputs need provenance=false and Docker media types. regclient0.11.6 installed; use private logs, never print authentication URLs/accounts or credentials. Some regctl auth requests had transient EOF; Docker push works. Stock amd64 images were pulled into separate capstone-trial-* tags, without replacing root stock tags.
- Root model library `.grid-agent/runtime/pypsa-models` has six verified assets. Pass it explicitly tobuild_dev_trial.py --model-library. Never copy ignored authentication into fresh worktrees.

## Integration next

1. Finish latest source cases, persistence/config-switch and browser checks on both platforms. Keep scripted verification Provider-free. Capture actual image IDs, architectures, source markers, runtime receipts and data replay.
2. Complete local/full and required PR gates, then normally merge PR22 intodev. No force/admin bypass. Freeze the resulting dev merge SHA for final artifacts.
3. Rootdev is3adaf5a with task-owned control/design edits copied in for the user view. Original files are preserved under `.capstone-agent/dev-trial-control-sync`. Before fast-forward, preserve current task diffs, restore only task-owned old tracked files and move the task-created untracked plan into an ignored backup; then fast-forward and verify accepted files return. Preserve all unrelated work.
4. Canonically rebuild real rootlocal-dev withmake capstone-local-rebuild and align its actual App process/source. Existing root App is a frozenFAA archive, so do not call the docs head its source. Preserve user data. local-demo/cloud-demo remainFAA; protected cloud-dev24d9a32 has user traffic and must not change.
5. Rebuild/publish exact final dev source, verify both platform manifests and anonymous pulls, complete final source-free candidate acceptance, then emit the final bundle through matching acceptance receipts. Publish source-free archive/thin install entry and record final URLs/source in owning design/control docs through PR; return rootdev to clean Git state.
6. Preserve feature verification runtime/private directories even when closing the merged branch. They are recovery data, not disposable worktree content. Do not delete main-worktreevar data or other recovery branches/stash.
