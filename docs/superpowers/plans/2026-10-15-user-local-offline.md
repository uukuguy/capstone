# User-local Offline Implementation Plan

> Execute with subagent-driven-development, with focused tests and review.

**Goal:** Install user-local on Linux AMD64 without public network access.

**Architecture:** Reuse frozen Compose packages and the version manager. Add
an image export/import transport with explicit local image identity validation.
Keep OpenAI-compatible endpoint configuration in the existing backend path.

## Global constraints

- Default `PROVIDER=openai`; prefer `OPENAI_BASE_URL`, `OPENAI_MODEL`, `OPENAI_API_KEY`.
- User delivery is `linux/amd64`; ARM64 is optional local validation.
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

Files: new offline exporter/installer under `deploy/`, lifecycle templates and
`tools/tests/test_user_local_offline.py`.

## Task 3: Acceptance and delivery

- [ ] Run focused regression, doctor and diff checks; review changes.
- [ ] Build exact-source AMD64 images and validate a fresh offline installation,
  registered cases, replay and restart without public downloads.
- [ ] Record receipts, usage instructions and source identity; align project
  control and recovery files. Integrate through the normal dev PR gates.
- [ ] Deliver the offline artifact and its checksum with tested scope and limits.
