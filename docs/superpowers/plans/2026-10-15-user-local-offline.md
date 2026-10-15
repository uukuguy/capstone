# User-local Offline Implementation Plan

> Execute with subagent-driven-development, with focused tests and review.

**Goal:** Install user-local on Linux AMD64 without public network access.

**Architecture:** Reuse frozen Compose packages and the version manager. Add
an image export/import transport with explicit local image identity validation.
Keep OpenAI-compatible endpoint configuration in the existing backend path.

## Global constraints

- Default `PROVIDER=openai`; prefer `OPENAI_BASE_URL`, `OPENAI_MODEL`, `OPENAI_API_KEY`.
- User delivery is `linux/amd64`; current verification uses host Docker on Apple ARM with AMD64 emulation.
- The user cancelled local Ubuntu VM and cloud-dev validation. Preserve the VM failure receipt; do not resume those lanes.
- No secrets in packages, command arguments, logs or browser variables.
- Preserve data and compatibility gates; do not modify cloud/demo deployments.
- No actual Provider call without separate user authorization.

## Task 1: OpenAI-compatible configuration

- [x] Add failing configuration/Compose tests for Provider aliases, model and URL.
- [x] Wire aliases and endpoint through the local trial profile to both workers.
- [x] Verify existing explicit CAPSTONE settings and cloud profiles remain valid.

Files: `deploy/dev-trial/compose.yaml`, `deploy/launch_host_runtime.py`,
`configs/runtime/host-runtime-dev-trial-v1.json`, relevant tools tests.

## Task 2: Offline transport

- [x] Add failing export/import tests: checksums, exact IDs/platforms, no network,
  incomplete inputs, existing data and repeat installation.
- [x] Add operator bundle exporter and user offline installer.
- [x] Adapt the manager only where needed to validate imported image identities.
- [x] Retain compatibility and configuration preflight before stopping services.

Task 1: 172 focused/adjacent checks and native Pi selection passed at40b338d.
Task 2: 67 focused checks passed at6b74397. The catalog preservation correction
7930c07 passed19 checks and independent review. No real Provider requests.
Actual AMD64 acceptance remains separate from these code checks.

927f08b adds explicit Chat Completions for local-trial custom OpenAI addresses
and fixes Pi environment-key interpolation. The expanded focused regression
passed129 checks, including four real-Pi loopback protocol tests. The separately
authorized DeepSeek `OPENAI_*` text/tool probe passed; real business samples
and the final accepted-source archive remain pending.

Files: new offline exporter/installer under `deploy/`, lifecycle templates and
`tools/tests/test_user_local_offline.py`.

916271f adds cross-daemon config/manifest identity binding and private runtime
projection, complete layer checks, and the frozen user-facing sample guide.
The combined gate passed160 checks and independent review. Source39 VM install
safely rejected the old single-ID assumption. At916271f, host Docker installation,
nine scripted turns, restart, repeat installation, replay and data preservation passed.
That host is Apple ARM running Linux AMD64 containers with emulation; it is not native
AMD64 acceptance. The916271f Ubuntu VM metadata-permission failure remains recorded.

698e2a9 preserves readable public metadata, retains private file modes and ownership,
and adds the task-duration ordering and storage/backup instructions. After inherited
LLM overrides were cleared, the two test-local-rebuild groups passed187 and61 checks;
shell checks passed. The698e2a9 archive passed checksum validation and imported all
four images; all six roles are healthy. Nine scripted turns and report/evidence replay
passed. Missing Key/URL checks reject configuration and preserve services. Restart,
repeat installation and corrected real OPENAI_* business
samples and PR #27 checks for the latest head remain pending. Local Ubuntu VM and
cloud-dev verification were cancelled by the user; no cloud service was changed.

## Task 3: Acceptance and delivery

- [x] Run focused regression, doctor and diff checks; review changes.
- [ ] Build the latest exact-source AMD64 images and verify fresh host Docker
  installation, registered scripted cases, replay, restart and repeat installation
  without public downloads; record the Apple ARM emulation boundary.
- [ ] Rerun the authorized real OPENAI_* business samples after their corrections;
  keep Provider-backed and scripted evidence separate.
- [ ] Record receipts, usage instructions and source identity; align project
  control and recovery files. Integrate through the normal dev PR gates.
- [ ] Deliver the offline artifact and its checksum with tested scope and limits.
  Do not claim cancelled native VM or cloud-dev verification.
