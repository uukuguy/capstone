# Live Session Checkpoint

> Updated: 2026-10-15 11:09 CST. User-local delivery verified; user trial is next.

## Verified delivery

- PR #23 merged normally at dev b7e68dd83a580a713b09fa6d0c4aac0186252a84. PR checks38628243417 and merged-source checks38670347925 passed on Linux/macOS. Full local checks, validate, doctor, App24/type and installer7 checks passed.
- Public immutable releases: user-local-b7e68dd and managed recovery user-local-7832134. The latter preserves original runtime files/images and records deployment tools from b7e68dd; its frozen App retains the original label. USER-LOCAL-VERSIONS.tsv owns installer URLs/checksums; newest verified runtime first.
- Exact final images passed ARM64 native Linux containers and AMD64 Linux containers through emulation on ARM Mac: anonymous pull, source/image identity, three cases/nine turns, report/evidence replay, restart, browser, existing-data upgrade and separately verified rollback. Private configuration, original receipt and volumes were preserved. Zero Provider calls; user LLM/business and Windows/WSL2 remain unverified.
- PR #24 merged normally at87beeed726f33dac48e29b7affd3b8e26fc8ad83 after exact-head Linux/macOS checks38674162257. Public fixed installer download/checksum/startup/status/stop passed in an isolated directory on30573. The live no-argument latest entry also passed actual install/start and retained-data stop; invalid arguments listed both supported versions. Catalog bytes and installer source were checked against the published records. Installation selects latest published or a7–40-character Git revision; bad/ambiguous arguments list available versions.
- Root local-dev API/two workers/App run exact b7e68dd, clean App source, canonical rebuild passed (image6069a80647ae). Local-demo/cloud-demo remainfaa6af9; cloud-dev24d9a32. Real ~/capstone on19173 remains untouched at the original7832134 until the user selects upgrade.

## User entry

Set DEEPSEEK_API_KEY in the startup environment, then:

```sh
curl -fsSL https://raw.githubusercontent.com/uukuguy/capstone/dev/deploy/dev-trial/install.sh | sh
```

Default~/capstone and App19173. Use .env CAPSTONE_APP_PORT to avoid conflicts. capstone.sh provides versions/start/use/install/status/logs/stop. Versions in one installation share data and a stable project; compatibility/configuration checks precede service changes. Preserve the full directory, private state and volumes.

## Recovery and remaining acceptance

- User LLM and business trial is next. Existing autonomous scientific/interaction gaps remain in the canonical worklist; no cloud/demo/main promotion follows from this delivery.
- Operational receipts remain in the task worktree .capstone-agent/: user-local-final-acceptance.json, user-local-publication-receipt.json, public-managed-final-receipt.json, user-local-root-rebuild-receipt.json and final platform case/runtime/browser logs. Public acceptance.json is attached to each release. Do not rerun publisher scripts or move tags.
- Preserve real ~/capstone, root var, unrelated worktrees, authentication state and all data volumes. Root control backups remain in .capstone-agent/user-local-doc-control-{precopy,live}; copies were safely restored before final integration.
- Product and delivery branches fix/dev-trial-user-feedback and docs/user-local-release-state were closed locally/remotely after verified merge. Root dev and preserved task worktree were clean; user-local-final-closeout.json records the live public selector, runtime source and cleanup. This final checkpoint maintenance changes no runtime or deployment. Do not rebuild runtime from an ordinary documentation commit or relabel its exact source.
