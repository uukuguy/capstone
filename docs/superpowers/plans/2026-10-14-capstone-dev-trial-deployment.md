# Capstone Dev Trial Deployment Implementation Plan

## Current checkpoint — 2026-10-15

Tasks 1–6 shipped through PR #22 at dev7832134. Both image platforms passed
anonymous pull, source/readiness, three cases/nine turns, reports/evidence replay,
restart and browser checks. The public dev-trial-20261015-7832134 release was
installed by the user in ~/capstone. Older unchecked steps below describe the
original implementation sequence, not pending delivery.

Task 7 implementation merged through PR #23 at dev b7e68dd; exact-source dual-platform publication and public installer validation passed. Existing user data is preserved.
The revised artifacts are public; the existing user installation stays usable
until the user selects an upgrade.

## Task 7: user-local management and shared-data compatibility

- [x] Record user-local naming, Git selection, default latest, shared user data,
  capstone.sh commands and compatibility as development/release responsibility.
- [x] Verify production/developer App label separation: 24 tests and type check.
- [x] Implement fixed installer that preserves existing config/receipts, stores
  frozen versions, pulls four images with progress and calls the manager; seven
  isolated installer tests pass.
- [x] Complete manager with one stable data project, exact cached-version
  selection, pre-stop compatibility/config checks and compatible restoration.
- [x] Generate source-bound data declarations; require old-data upgrade, reads,
  replay and separately verified rollback receipts before publishing.
- [x] Review and run focused checks, full required integration gates and PR CI;
  merge normally into dev before freezing revised runtime images.
- [x] Verify revised images and actual shared-data upgrade/revert in isolated
  installations on both supported image platforms; keep real ~/capstone intact.
- [x] Publish immutable user-local-SHA assets, checksum catalog and latest entry;
  update installable Git icons and browser-check the canonical control graph.
- [x] Prepare the control/catalog integration through a normal dev documentation
  PR; real dev entry and public fixed installer pass. The merge closeout verifies
  the public selector, fast-forwards dev and closes only merged task branches.

> Execute inline, task by task, with test-driven development and an independent code review before integration. Preserve other worktrees and all existing service data.

**Goal:** Ship a fixed dev revision as four public image classes plus a source-free Compose bundle, defaulting to Aliyun Beijing, for linux/amd64 and linux/arm64.

**Architecture:** API and both family workers share one backend image. A static App image proxies the same-origin API. PostgreSQL and RustFS retain their existing roles and persistent volumes. Human deployment commands are Application operations; no deployment tool enters the model-facing catalog.

**Tech Stack:** Python 3.12, existing hosted runtime and Provider registry, Vite/Caddy, POSIX shell, Docker Compose and Buildx.

## Global constraints

- User-approved design: [CLI installation and local trial](../specs/2026-09-29-agent-interaction-discussion.md#2026-10-14capstone-cli-安装与用户本地-dev-试用).
- Default public registry: registry.cn-beijing.aliyuncs.com/uukuguy. GHCR is optional, not a prerequisite.
- User runs containers and supplied deployment files; no Git, Python, Node, source checkout or build step on their machine.
- Default DeepSeek/deepseek-flash; commented OpenAI model comes from configs/llm-providers.json. Startup environment wins over file defaults. No key in arguments, images, default files or receipts.
- Existing host-runtime-v1 cloud contract remains pinned. A separate local-only trial profile admits the two configured API-key Providers.
- Fixed dev source and exact image identities; no floating latest. Candidate validation precedes PR integration; final trial images use the accepted dev merge source.
- No cloud-dev/demo deployment, no changes to their protected variables, no Provider requests without separate authorization, no volume deletion.
- Browser label local-dev, same-origin /api/v1, loopback binding by default. Docker selects the published Linux platform; Windows coverage is WSL2, not native Windows containers.

## Task 1: bounded trial runtime profile

**Files:** configs/runtime/host-runtime-dev-trial-v1.json; deploy/launch_host_runtime.py; tools/tests/test_host_runtime_contract.py.

- [ ] Add failing tests for DeepSeek defaults and explicit OpenAI, all three roles, required selected key, unknown Provider/model syntax, local-only stage and unchanged legacy drift rejection.
- [ ] Run `UV_PYTHON=3.12 uv run --project packages/grid-agent python -m pytest tools/tests/test_host_runtime_contract.py -q`; new tests must fail at the unknown trial profile.
- [ ] Map the two known profile IDs to fixed config paths. A trial provider_selection declares default deepseek and allowed deepseek/openai; defaults read the Provider registry. Model must be a bounded non-empty identifier; actual availability is a Provider-time check, not an automatic paid preflight.
- [ ] Keep all other shared fields/roles strict and API credential-free. Workers validate the selected registry credential variable. Compute the receipt contract hash from the selected profile file, not the legacy literal path.
- [ ] Run focused tests and commit the profile with its tests and a journal entry.

Required behavioral test:

```python
settings = environment('pandapower') | {
    'CAPSTONE_RUNTIME_PROFILE': 'capstone-dev-trial-v1',
    'CAPSTONE_PUBLIC_PROVIDER': 'openai', 'OPENAI_API_KEY': 'test-never-log',
}
selected = RUNTIME.select_runtime(ROOT, settings, 'worker')[3]
assert selected['CAPSTONE_PUBLIC_MODEL'] == registry['providers']['openai']['default_model']
```

## Task 2: local static App identity and same-origin proxy

**Files:** deploy/prepare_app_source.py; packages/capstone-app/vite.config.ts; packages/capstone-app/src/buildEnvironment.test.ts; tools/tests/test_prepare_app_source.py; deploy/dev-trial/App.Dockerfile; deploy/dev-trial/Caddyfile.

- [ ] Add failing tests for production local-dev receipt with an empty API origin; reject local external origins, cloud receipt drift and development-mode receipt reuse.
- [ ] Run the helper tests and `npm test --prefix packages/capstone-app -- --run src/buildEnvironment.test.ts`; observe the new cases fail.
- [ ] Extend the existing secret-free App source helper only for explicit local-dev plus empty origin. Cloud HTTPS/source receipt validation remains unchanged.
- [ ] Bind the production App header to local-dev and the exact source. Build the existing App with its empty/same-origin API selection.
- [ ] Use a separate trial Caddy file: static /health, proxy /api/* and /health/ready to api:8766, and SPA fallback. The Compose-selected local App origin is forwarded to the API; no cloud address is baked into this image.
- [ ] Run helper and App identity tests, App type checks, then commit.

## Task 3: source-free Compose and lifecycle entry

**Files:** deploy/dev-trial/compose.yaml; deploy/dev-trial/start.sh; deploy/dev-trial/env.example; deploy/dev_trial_runtime.py; tools/tests/test_dev_trial_deployment.py; Dockerfile.

- [ ] Test a generated private environment is mode0600, stable on repeated init and rejects symlink targets; existing files and data are preserved.
- [ ] Test startup selects the configured Provider, rejects missing keys without their values, and status contains source/role/profile without credential fields.
- [ ] Use backend-contained Python for protected local internal-credential initialization. User needs only Docker and shell; never source or eval .env in the shell.
- [ ] Compose uses exactly four image variables, no build sections, and a separate project name. Backend image serves API/workers/object initialization; add static App service. Persistent PG/object/run volumes stay intact on stop/recreate.
- [ ] Pass credentials only to workers/config-check. Shell environment overrides .env through Compose interpolation. Generate .env defaults plus commented OpenAI; do not emit blank credential assignments.
- [ ] Implement `./start.sh up|status|logs|stop`. Init config, bounded config-check, compose up --wait, then secret-free acceptance status. Stop never uses down -v. Reject another installed source unless upgrade is explicitly selected.
- [ ] Capture Compose/runtime diagnostic output privately and redact values before public errors. No config --environment output or expanded secret arguments.
- [ ] Copy the small runtime helper into the backend image; preserve the existing developer rebuild behavior.
- [ ] Run focused tests with fake Docker to cover command boundaries, then real Compose config with synthetic keys and no stdout secret values.

## Task 4: exact-source builder and bundle manifest

**Files:** deploy/build_dev_trial.py; tools/tests/test_build_dev_trial.py; deploy/dev-trial/README.md.

- [ ] Test exact commit validation, new ignored output paths, symlink rejection, safe git archive extraction and exclusion of authentication state, user data, run storage and environment files.
- [ ] Prepare backend from exact git archive and stage the six verified official model assets; prepare App using Task2 helper. Require a clean accepted source, not a dirty tree.
- [ ] Build images for linux/amd64 and linux/arm64 with Buildx, recording source labels. Default registry and repository names come from the accepted design. Tag each candidate with its full source identity; never overwrite an existing differing tag.
- [ ] A publish operation must be explicitly selected; only verified source/platforms can become user bundle references. Inspect registry manifests and record both Linux platforms and exact digest per image class, copying the existing PG/RustFS dependency identity without rebuild.
- [ ] Emit bundle-only files: compose.yaml, .env, release.env, manifest.json, start.sh and README. No application source or credential material. Image references are digest-pinned; all roles use the same backend source.
- [ ] Bundle fields: schema, channel dev-trial, source_revision, image mapping, platforms and validation receipts. Validate the downloaded identity before lifecycle operations; never silently switch to GHCR or a newer trial.
- [ ] Run unit tests for archive/bundle/schema failures before real image builds.

## Task 5: candidate verification and dev integration

- [ ] Canonical-rebuild local-dev from the implementation checkout only after setup/install-pi/doctor, preserving its data and verified model cache. Do not replace local-demo or cloud stages.
- [ ] Build ARM64 candidate images first. Start an isolated trial Compose project on port21573 with synthetic credential values; run readiness, registered three cases/nine turns, reports/evidence replay with zero Provider calls, browser header/Composer/diagram and restart persistence.
- [ ] Build/run AMD64 images in a separate isolated project on port22573. Repeat the relevant same contract/provider-free acceptance. Record emulation/native identity, image digests and actual status; failed or absent checks cannot be presented as dual-platform support.
- [ ] Test OpenAI selection and shell-over-file precedence without calling OpenAI. Missing-key/model-format errors stay secret-free.
- [ ] Run affected suites, make check-pr and required two-platform PR checks. Request an independent review covering credentials, source identities, shell/file boundaries and data retention; fix material findings.
- [ ] Update README/README.zh-CN and RUNBOOK for the actual delivered entry. Update VERSION-CONTROL/PROJECT-OVERVIEW with implemented/verified/merged/published states, ui-ux-pro-max layout and browser edges/crossings checks.
- [ ] Merge accepted work normally to dev, fast-forward root dev, verify the real entry and preserve recovery references. No administrator bypass or force push.

## Task 6: final public trial artifacts

- [ ] Freeze the resulting accepted dev merge SHA; rebuild/publish that exact source, retaining equivalent-tree candidate evidence where applicable.
- [ ] Create or verify the two public Aliyun repositories and the PG/object mirrors with approved visibility; verify anonymous access using separate empty Docker authentication state, never relying on the operator login as evidence.
- [ ] Verify platform manifests, image/source identities, package checksums and fresh source-free bundle startup. Publish the package only with real image references and verified paths.
- [ ] Store a dev-trial publication receipt and known limits, not a stable/demo/cloud-dev acceptance tag. Record distribution URLs and final source in owning design, canonical plan and control view.
- [ ] Finish documentation through PR and return root dev to a clean state; preserve unrelated worktrees, volumes, local auth and data.

## Progress

Tasks1/2 implemented in2e299a8:56 Python profile/source-helper checks and15 App identity checks pass, including legacy cloud guards; App type checks pass. Task3 lifecycle implementation and source-manifest guard pass66 Python checks with existing runtime/helper suites. Task4 exact-source contexts and source-free bundles implemented through6f29b29; combined69 Python checks pass. Candidate validation requires explicit operator opt-in and does not claim both platforms verified. ARM64/AMD64 App images built; backend builds and full PR gate run in background. Root control graph now displays nine connected important nodes, current trial focus and four unchanged deployment sources; both spacing limits pass uniformity, overlap, source, arrow and independent-crossing checks. No public trial artifacts or actual Docker acceptance yet. Existing local backend baseline is ARM64 and approximately2.93GiB expanded; official model cache approximately39MiB. These observations are not new multi-platform image or registry acceptance.
