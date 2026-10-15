# Live Session Checkpoint

> Updated: 2026-10-15. Session remains active — not a final handoff.

## Current task

Deliver a Linux AMD64 offline user-local package. Default PROVIDER=openai;
users supply OPENAI_BASE_URL, OPENAI_MODEL and OPENAI_API_KEY. User authorized
existing DeepSeek credentials for real OpenAI-compatible tests and business samples.

Worktree: .worktrees/dev-trial-deployment, branch feat/user-local-offline.
Latest code: 916271fe639eaf04ce87dc5fdeed817c53640602. PR #27 targets dev.
Root dev remains1d0b280; local-dev b7e68dd, local-demo/cloud-demo faa6af9,
cloud-dev24d9a32. Existing user installation/data and cloud services are unchanged.

## Verified and pending

- 927f08b fixed Pi custom-endpoint protocol and environment-key interpolation.
  129 focused checks, four real-Pi loopback SSE text/tool tests, and authorized
  DeepSeek OPENAI_* text/tool requests passed. Old-source IEEE39 and AC/DC real
  samples passed admission/tool-source replay. Regional dispatch failed before
  the solver because emulated AMD64 lacks AVX/AVX2. Failed receipts are retained.
- 39b1658 pins same-version Polars rtcompat on Linux x86_64. Six locks only add
  that runtime; five dispatch checks, six lock checks and independent review pass.
  Isolated AMD64 registered dispatch also passed with the network disconnected.
- 39 package then failed real VM installation safely: Docker29 containerd uses
  manifest digest as .Id, while the source daemon uses config digest.
- 916271f fixes tagged archives with exact dual identities, complete layer checks,
  private runtime-ID projection before version registration, immutable matching,
  static data-contract preservation and no-pull startup. Combined160 checks,
  doctor, independent review and19 extra layer checks pass. New VM install pending.
- README now uses formal project instructions in user groups: simple/short first,
  calculations next, scenario changes and advanced exploration last. Frozen
  guide is deploy/dev-trial/offline-validation-samples.txt. Both package and
  installed-directory README include it. User preview is root runs/user-local-offline/README-preview.txt.

## Active operations

- Host .capstone-agent/build_offline_final.py 916271f... is building the candidate;
  log offline-portable-candidate-build.log. Completion writes offline-final-build.json
  with source916, archive/checksum and extracted path. Earlier source39 metadata
  is stale until that write. Final delivery must still use the accepted dev merge SHA.
- Agent offline_provider prepares/runs the916 VM installer checks in existing
  ubuntu-fusion-control. It is x86_64 emulated on Apple ARM, Docker29.1.3/Compose2.40.3,
  separate daemon. New owned /var/tmp directory; /tmp is tmpfs. Port29374, synthetic
  Key only. Preserve39 blocked evidence under root runs/user-local-offline/vm-39b1658/.
- Source39 CI38687130563: macOS passed, Ubuntu running at last check. Push source916
  plus pending owned control docs once, then require both fresh platform gates.
- User requires cloud validation to follow README installation. Railway does not
  support Compose/DinD. Resource queries succeeded via proxy127.0.0.1:7897; each
  cloud-dev service limit8vCPU/8GiB and current use is low. No cloud writes occurred.
  Temporary native-image-job proposal is paused. Async request for an existing
  SSH-accessible Linux AMD64 cloud host remains unanswered. User permits temporary
  shutdown of old cloud-dev services if necessary; preserve all data and restore.

## Next actions

1. Finish control-doc commit/push; wait fresh Linux/macOS gates. No bypass.
2. Run candidate VM and host installation checks; no more real Provider use in
   local emulation just to duplicate cloud samples. Report actual failures.
3. Normal PR merge, root dev fast-forward, canonical make capstone-local-rebuild.
4. Rebuild final images/archive from exact accepted dev merge; verify the actual
   extracted archive, readiness, registered cases, replay, restart and data retention.
5. Cloud README installation requires the missing cloud Linux host. Do not replace
   it with an image-only Railway test or claim it passed.
6. Update verification report, plans, canonical worklist, VERSION-CONTROL/INDEX and
   regenerated browser-checked graph; normal docs PR. Preserve all ignored receipts,
   worktree recovery data, original installs and volumes. Do not update demo/main.

## Operator evidence

All operator scripts/logs live in this worktree's ignored .capstone-agent/.
Root runs/user-local-offline/ holds candidate archives and user-readable preview;
source927 and39 packages are not accepted final deliveries.
Final artifact names include the source SHA. Credentials never enter archives,
arguments, logs, public projections or committed state. No real Provider calls
are needed for packaging or deterministic acceptance.
