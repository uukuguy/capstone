# Local disk recovery — 2026-10-18

## Follow-up: retire unused local build state

The user clarified that infrequently used build outputs need not remain local, and that obsolete worktrees must be archived or removed.

- Removed another 146 ignored dependency directories across 17 idle worktrees, with 48.69 GiB of directory allocation. Git status before and after was identical for every affected worktree.
- Verified the current delivery ZIP's embedded archive against its SHA-256. Kept this one current ZIP. Removed the seven separate historical/duplicate installation archives and remaining old image tar staging files: 12.51 GiB. Source identities, checksums and verification records remain.
- Removed 124 historical Capstone Docker image IDs that no running or stopped container used. Retained current local image tags and current offline delivery images. Used no forced image removal and changed no volumes. The reported 323.52 GiB image size includes shared layers and is not a physical-space saving claim.
- Retired 20 worktrees after archive verification. `.worktrees` now contains only `model-decision`, `dev-macos-ci`, `demo-baseline` and `research-model`; the root checkout remains. Private archives are under `.capstone-agent/worktree-archives/20261018/`, with a recovery README and INDEX.json. Each archive has a verified file inventory, SHA-256, Git status, recovery ref and omitted-cache list. Uncommitted changes and non-cache local records remain recoverable. Existing branches and Git history remain. Recovery refs use `refs/archive/worktrees/20261018/<name>`.

Final check: project allocation is about 30 GiB, down from 185 GiB before emergency cleanup. Host free space is about 182 GiB. API readiness returned `ready`; App returned HTTP 200. Only four worktrees remain under `.worktrees`, plus the root checkout.

Local retention rule: keep active development/demo runtimes and the current delivery package. Keep source revisions, build manifests and validation records for historical builds; regenerate their large binaries when needed. Retire completed worktrees after preserving unresolved work. Do not accumulate a full dependency installation for every historical branch. User sessions, uploads, results and database volumes are not build cache.

## Initial emergency cleanup

The project used 185 GiB. Worktrees used 163 GiB. The dev-trial-deployment worktree used 64 GiB, mainly repeated offline image exports and extraction checks. Git metadata used 62 MiB.

Completed cleanup:

- Verified the SHA-256 of seven formal offline archives in `runs/user-local-offline`. Kept every archive, delivery ZIP, manifest, checksum and test record. Removed only the duplicate backend/app/PostgreSQL/object-store image tar files from their staging and extraction directories: 52.94 GiB.
- Removed ignored Python virtual environments from eight idle, clean worktrees: ci-portability, demo-n1-repair, dev-trial-deployment, github-issue-automation, issue-1-history, issue-operational-readiness, iteration-gates and stable-route-recovery. Their directory allocation was 31.57 GiB. Hard links mean this is not the physical space reclaimed. Source files and worktrees remain. Run the repository setup before using these environments again.
- Cleared regenerable uv cache (15.0 GiB reported) and unused Docker build cache (7.651 GB reported). Did not prune Docker volumes or release images.

The active implementation runtime, dev checkout, demo baseline, uncommitted code, database volumes, uploaded resources, task products and main-worktree `var/` data remain. Host free space reached about 77 GiB after cleanup. Exact deletion receipts are in ignored `runs/disk-cleanup-20261018.json` and `runs/inactive-runtime-cleanup-20261018.json`.

Project allocation fell from 185 GiB to 100 GiB. The full disk also left two zero-byte native resource `accepted.json` snapshots. They were preserved in the profile volume under `.disk-full-quarantine-1792302641`; the native service was restarted to verify the installed skill sources and recreate its snapshots. Recovery verified: API `/health/ready` returned `ready`; API, all three workers and general-pi reported healthy. `make doctor` passed in the active implementation worktree. No database or task receipt was removed.

The implementation worktree rebuild entry point now checks host free space before dependency installation or image builds. It defaults to a 20 GiB reserve, configurable through `CAPSTONE_LOCAL_MIN_FREE_GIB`. A low-space rejection reports available and required space and starts no build. Shell syntax, the forced-low-space rejection path and `git diff --check` passed. This check does not prune data or guarantee space inside a separately limited Docker VM.

Research work remains separate: the native worker now reads `CAPSTONE_THREAD_ATTEMPT_TIMEOUT_SECONDS`, supports an optional `CAPSTONE_ENTERPRISE_RESEARCH_TIMEOUT_SECONDS` override, and passes configured durations beyond one hour. Failure replies include the actual timeout and recognize artifact persistence failures. A bounded, acknowledged event window replaces the silent lifetime event cap. The real HTTP worker test delivered 300 progress events without loss for four timeout configurations. The focused suite passed 165 tests; 15 PostgreSQL cases were skipped. These source changes are not yet rebuilt or accepted in a fresh user research run.
