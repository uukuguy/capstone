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

698e2a9 preserves readable public metadata and private modes/ownership. The187+61
rebuild checks, shell checks, host install/restart/repeat/data retention and source
identity checks passed. Nine real requests and independent replay completed, but
request completion is not proof that every business objective succeeded.

05581c8 added shared Markdown guides and safely failed installation at the checksum
list gate; retain that failed archive. 7c19766 fixed optional Markdown entries and
exact11/12-file checksum validation;47+3+8 checks and review passed. Its complete
host installation, restart/repeat/data retention, nine-request and replay checks
passed. The old package was handed over and then withdrawn as defective. Do not deliver
it. Evidence is retained at root
runs/user-local-offline/capstone-withdrawn-7c19766. Preserve the original archive,
README and SHA; do not overwrite this delivered package with later guide or code changes.

Source7c passed Linux/macOS CI38700786813, then PR #27 merged normally as
37529efa2f0b0e10f641a65706b330b1d94255af. Root dev remains1d0b280, without fast-forward
or canonical rebuild. Four deployments and the original19173 installation are unchanged.
Only Apple ARM host Docker AMD64 emulation was verified; VM/cloud checks were cancelled.

Business scope correction:7c regional runs never called operations.dispatch. README
instructions1–9 completed through OPENAI send_auto;10–12 were not run. Instruction12
still marks full generator N1 study/ranking as pending. Keep business failures and
unverified instructions explicit; do not call all samples passed.

The separate fix/user-local-network-view branch is atce47532. Graph/camera fix61a418d
is pushed with106 backend/109 App/type/browser checks passed, without PR or deployment.
Public Pi handoff schema fix28020aa passed16 contract and82 checks plus review; guide
revisionce47532 leads with IEEE39 and moves optional PyPSA grids to the end, with54+5
checks and review passed. The branch throughce47532 is now pushed, without PR or deployment; these changes
are absent from the original7c package and included in the updated e2 package.
The separate29375 AMD64 backend28020aa/App7c
candidate passed the original three-turn real OPENAI handoff/dispatch path: baseline
and growth objectives1300/1900, both optimal, and both AC validations converged.
Third-turn4 operations public projections were unavailable, and third-period AC flow
did not reflect the dispatch generation increment; consistency remains open. This
is not full PyPSA acceptance. The candidate is stopped with0 running containers and
data preserved. See [bounded verification](../../reviews/2026-10-15-pypsa-handoff-verification.md).


## Updated package: e2eaee2

The user requested an updated package with the fixes and no full retest. Frozen
source e2eaee2403cb6d780b3f7564da86e0d083890673 is built. Its runtime packages have
no diff from28020aa, so reuse the bounded real handoff/dispatch verification and
keep public projections and third-period AC consistency open. No new Provider calls.

Clean root directory: runs/user-local-offline/capstone-delivery-e2eaee2.
It contains the .tar.gz archive, matching .sha256 and the generated README.md.
Archive bytes:1368607944. SHA256:
9d7c3b215b9c45631bf3142aaad8f8066ba43831380b43b2ccf8146ee1eebfe7.
The12 internal SHA checks and source identity passed. The single fresh29377
installation and readiness passed; six roles are linux/amd64 and the API/dual-worker
image identity matches source e2. The instance stopped with return code0 and data
was preserved. This does not repeat or
expand the previous business acceptance. Preserve the withdrawn7c evidence; do not distribute it.

Minimal-check receipt: `.capstone-agent/offline-e2eaee2-minimal-check.json`.
No full test suite, Provider request or business sample was rerun for this package.

## Task 3: Acceptance and delivery

- [x] Run focused regression, doctor and diff checks; review changes.
- [x] Verify the exact7c archive installation, scripted checks, replay, restart,
  repeat installation and data retention; record AMD64 emulation explicitly.
- [x] Complete nine authorized real requests and independent replay; record that
  this does not imply regional dispatch or all business samples passed.
- [x] Preserve exact7c artifact/checksum/README as withdrawn evidence with original
  hashes. The package was handed over and then withdrawn; do not deliver it.
- [x] Merge PR #27 normally as37529ef after source7c Linux/macOS CI passed.
- [ ] Fast-forward root dev and rebuild its real local entry point with data preserved.
- [x] Verify the original three-turn handoff/dispatch path on the separate28020aa
  candidate; preserve receipts and data after stopping it.
- [ ] Resolve public projection availability and third-period AC/dispatch consistency
  as separate open findings; do not broaden this handoff acceptance.
- [ ] Complete remaining README business checks;10–12 were not run and full N1
  study/ranking is still pending. Keep withdrawn7c evidence unchanged; do not deliver it.
- [ ] Submit independent fixes through normal PR/CI and verify their actual runtime.
