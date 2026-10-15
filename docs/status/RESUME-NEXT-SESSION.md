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

- Source916 host Docker acceptance passed install,9 scripted turns, replay,
  restart/repeat and data/config retention. VM failed public metadata permissions;
  fix preserves original mode/owner and passed independent review.
- User cancelled local Ubuntu VM and cloud-dev verification. Neither is a
  remaining delivery gate. Existing VM/cloud data and failed evidence are retained.
- Corrected-source local gate passed187 deployment/offline/Provider checks plus
 61 entrypoint checks and shell rebuild checks. Inherited LLM overrides must be
  removed before running tests; original unsanitized failure is retained.
- README preview is generated from actual exporter; data storage/backup guidance
  and explicit short-to-long sample ordering are included.

## Next actions

1. Commit/push mode fix and README, rebuild corrected AMD64 candidate.
2. Rerun authorized real OPENAI_* samples on corrected installed AMD64 backend,
   including previously failed regional dispatch. Preserve original failures.
3. Wait required Linux/macOS checks, normal PR merge, root dev fast-forward,
   canonical make capstone-local-rebuild. No bypass.
4. Build delivery from exact accepted dev merge; verify extracted package,
   readiness, scripted cases, replay, restart/repeat, data retention and browser.
5. Update verification/plan/worklist/control graph with actual scope and receipts;
   normal docs PR. Show final README. Do not update demo/main/cloud.

## Operator evidence

All operator scripts/logs live in this worktree's ignored .capstone-agent/.
Root runs/user-local-offline/ holds candidate archives and user-readable preview;
source927 and39 packages are not accepted final deliveries.
Final artifact names include the source SHA. Credentials never enter archives,
arguments, logs, public projections or committed state. No real Provider calls
are needed for packaging or deterministic acceptance.
