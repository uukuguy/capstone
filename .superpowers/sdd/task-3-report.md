# Task 3 Report: Reproducible Tamper-Evident Pi Runtime Patch Install

## Scope

Implemented the installer/lock distribution slice only:

- Upgraded `configs/runtime/pi-runtime.lock.json` to schema version 2.
- Recorded exact `pi_ai_version` (`0.80.6`) and the required patch declaration.
- Added lock-time patch path and byte validation.
- Added deterministic ordered patch identity digest.
- Applied verified patches after detached checkout and before `npm ci`.
- Recorded patch digest identity in the active marker and `PiRuntimeIdentity`.
- Added retry safety for failed installs by resetting and cleaning the managed source before patching.

No `var/` data was modified or migrated.

## Digests

- Patch: `configs/runtime/patches/pi-0.80.6-before-model-request.patch`
- Patch SHA-256: `458794796163d70c71846a4f38a543bf2ed495547c5fd216b2f1e0d684e1da0e`
- Lock SHA-256 after schema v2 update: `42ac45d642541df1e89d7840dc91399b64a981adca752de581f977f3dafca8b7`
- Ordered patch identity SHA-256: `f5127db4b2bd3856a9f12adc7e8499f5c2d6780419e85705c550f2e1244370ad`

## RED Evidence

Initial focused runtime suite after writing schema v2/patch tests:

```text
uv run --project packages/grid-agent pytest packages/grid-agent/tests/runtime/test_installer.py packages/grid-agent/tests/runtime/test_locator.py -q
11 failed, 10 passed in 0.42s
```

Representative failures:

- `PiRuntimeLock` had no `pi_ai_version`, `patches`, or `patches_sha256`.
- Schema v2 temp locks were rejected as unsupported schema version.
- Installer never invoked `git apply`.
- Failed patch application did not raise because patching was absent.
- Locator identity lacked `pi_ai_version` and `patches_sha256`.

Retry/idempotency RED checks added after real install failure:

```text
uv run --project packages/grid-agent pytest packages/grid-agent/tests/runtime/test_installer.py::test_installer_uses_detached_pinned_commit -q
1 failed
```

Failures confirmed missing `git reset --hard <commit>` first, then missing `git clean -fd` after a second RED run. These were needed because a failed Pi build left patched tracked files and an untracked patch-created test file in `.grid-agent/runtime/pi/source`.

## GREEN Evidence

Focused runtime tests:

```text
uv run --project packages/grid-agent pytest packages/grid-agent/tests/runtime/test_installer.py packages/grid-agent/tests/runtime/test_locator.py -q
21 passed in 0.04s
```

Full grid-agent tests:

```text
uv run --project packages/grid-agent pytest packages/grid-agent/tests -q
529 passed, 1 warning in 78.26s
```

Repository Makefile test gate:

```text
make test
529 passed, 1 warning in 74.67s
87 passed, 18 warnings in 36.95s
node --test: 25 pass, 0 fail
```

Additional checks:

```text
uv run --project packages/grid-agent python -m compileall -q packages/grid-agent/src/grid_agent/runtime packages/grid-agent/tests/runtime
exit 0

git diff --check
exit 0
```

No LSP diagnostics tool was exposed in this session. Compile checks and the full Makefile test gate were used as the available diagnostics/type-safety substitute.

## Install / Doctor Evidence

`make install-pi` verified the installer path through clone/fetch/checkout/reset/clean/patch/`npm ci`, then failed in upstream Pi's build step while fetching `https://models.dev/api.json` from Node:

```text
PiRuntimeInstallerError: Pi runtime command failed (npm run build)
Failed to load models.dev data: TypeError: fetch failed
ConnectTimeoutError: Connect Timeout Error (attempted addresses: 199.59.149.237:443, 2001::a88f:abbd:443, timeout: 10000ms)
```

This was reproduced after the reset/clean fix. `curl -I --connect-timeout 10 --max-time 20 https://models.dev` returned HTTP 200 through the shell proxy, but Node v23.11.0 built-in `fetch()` ignored the proxy environment and timed out. `NODE_USE_ENV_PROXY=1` did not change Node's behavior, and `node --help` exposed no proxy flag.

Active marker safety held:

```text
active missing
```

`make doctor` after the failed install completed:

```text
uv run --project packages/grid-agent grid-agent doctor --json
{"gridctl": ".../packages/grid-simulator/.venv/bin/gridctl", "live_probe": false}
```

## Files Changed

- `configs/runtime/pi-runtime.lock.json`
- `packages/grid-agent/src/grid_agent/runtime/lock.py`
- `packages/grid-agent/src/grid_agent/runtime/installer.py`
- `packages/grid-agent/src/grid_agent/runtime/locator.py`
- `packages/grid-agent/tests/runtime/test_installer.py`
- `packages/grid-agent/tests/runtime/test_locator.py`

## Notes

- Existing dirty files outside this task were left untouched: `.superpowers/sdd/task-1-report.md`, `.superpowers/sdd/task-2-report.md`, and `docs/status/JOURNAL.md`.
- The managed runtime source under `.grid-agent/` is ignored runtime state. It remains without an active marker because the upstream Pi build did not complete.

## Security Review Fix: Active Marker Binding

### Finding

Security review found a HIGH binding failure: `PiRuntimeLocator.resolve()` treated an existing managed CLI as usable without validating the `active` marker written only after a completed install. A partial/failed install could therefore leave residual CLI output and be resolved as a managed runtime.

### Change

- `PiRuntimeLocator.resolve()` now treats managed runtime as available only when the CLI exists and the `active` marker is valid.
- The marker must bind the managed source path, pinned commit, lock SHA-256, and combined patch SHA-256 to the current `PiRuntimeLock`.
- Missing marker means no managed runtime and allows normal PATH fallback.
- Present but malformed/mismatched marker is a hard `PiRuntimeLocatorError`; it does not silently fall back to PATH.
- Managed OAuth helper resolution also requires the same active marker.
- `PiRuntimeInstaller.install()` removes any stale `active` marker before patch verification/source mutation.
- Installer cleanup changed from `git clean -fd` to `git clean -fdx` under `.grid-agent/runtime/pi/source` so ignored build output such as `dist` cannot survive failed retries.

### RED Evidence

Focused runtime tests after adding the security-review cases and before implementation:

```text
uv run --project packages/grid-agent pytest packages/grid-agent/tests/runtime/test_installer.py packages/grid-agent/tests/runtime/test_locator.py -q
6 failed, 20 passed in 0.39s
```

Failures proved:

- Installer still used `git clean -fd`, not ignored-output cleanup.
- Failed build left a stale `active` marker.
- Managed executable without marker still resolved instead of falling back to PATH.
- Malformed, wrong-source, and wrong-digest markers did not raise.

### GREEN Evidence

Focused runtime tests:

```text
uv run --project packages/grid-agent pytest packages/grid-agent/tests/runtime/test_installer.py packages/grid-agent/tests/runtime/test_locator.py -q
26 passed in 0.08s
```

Full grid-agent tests:

```text
uv run --project packages/grid-agent pytest packages/grid-agent/tests -q
534 passed, 1 warning in 73.97s
```

Additional checks:

```text
uv run --project packages/grid-agent python -m compileall -q packages/grid-agent/src/grid_agent/runtime packages/grid-agent/tests/runtime
exit 0

git diff --check
exit 0

rg "breakpoint\\(|pdb\\.set_trace|TODO DEBUG|print\\(" packages/grid-agent/src/grid_agent/runtime packages/grid-agent/tests/runtime/test_installer.py packages/grid-agent/tests/runtime/test_locator.py -n
exit 1, no matches
```

### Residual

The pre-existing Pi 0.80.6 dependency-audit finding was not addressed in this task. Pins remain unchanged by scope.

## Re-review Fix: Cleanup Containment

### Finding

Re-review found a MEDIUM cleanup-containment failure: the installer could invoke runner-backed git commands, especially `git clean -fdx`, before proving `.grid-agent/runtime/pi/source` was a safe managed directory. A symlinked or escaped source path could make cleanup unsafe.

### Change

- Added source preparation/validation before active marker removal, patch verification, mkdir-sensitive mutation, or any runner command.
- Validation rejects a symlinked `source` path.
- Validation creates normal missing source directories, then confirms the path is a directory.
- Validation checks resolved `source` remains inside the resolved `.grid-agent/runtime/pi` root.
- `git clean -fdx` remains confined to the verified managed source directory.
- On invalid source state, `PiRuntimeInstallerError` is raised, the runner is not called, stale marker content is left untouched, and no outside directory is removed.

### RED Evidence

New containment tests before implementation:

```text
uv run --project packages/grid-agent pytest packages/grid-agent/tests/runtime/test_installer.py::test_installer_rejects_symlink_source_before_runner_or_marker_mutation packages/grid-agent/tests/runtime/test_installer.py::test_installer_normal_managed_source_proceeds_after_validation -q
1 failed, 1 passed in 0.18s
```

Failure proved symlinked `source` was accepted and install proceeded instead of raising before runner/marker mutation.

### GREEN Evidence

New tests:

```text
uv run --project packages/grid-agent pytest packages/grid-agent/tests/runtime/test_installer.py::test_installer_rejects_symlink_source_before_runner_or_marker_mutation packages/grid-agent/tests/runtime/test_installer.py::test_installer_normal_managed_source_proceeds_after_validation -q
2 passed in 0.37s
```

Focused runtime tests:

```text
uv run --project packages/grid-agent pytest packages/grid-agent/tests/runtime/test_installer.py packages/grid-agent/tests/runtime/test_locator.py -q
28 passed in 0.32s
```

Full grid-agent tests:

```text
uv run --project packages/grid-agent pytest packages/grid-agent/tests -q
536 passed, 1 warning in 74.69s
```

Additional checks:

```text
uv run --project packages/grid-agent python -m compileall -q packages/grid-agent/src/grid_agent/runtime packages/grid-agent/tests/runtime
exit 0

git diff --check
exit 0

rg "breakpoint\\(|pdb\\.set_trace|TODO DEBUG|print\\(" packages/grid-agent/src/grid_agent/runtime packages/grid-agent/tests/runtime/test_installer.py packages/grid-agent/tests/runtime/test_locator.py -n
exit 1, no matches
```

### Residual

The pinned Pi 0.80.6 dependency-audit finding remains out of scope and was not changed.

## 2026-10-09 Task 3: Shared General Pi Delegation and Direct Execution

### Delivered behavior

- Hosted pandapower and PyPSA applications discover only an explicitly configured
  general executor. The health request has a two-second total limit and does not
  call a Provider. Private origins and control tokens stay outside task resources.
- The semantic catalog contains Domain Pack profiles and the actual general Pi
  executor operation and native-tool description. External lookup can select
  `general-pi` without naming the child's retrieval source. Business execution
  cannot select that executor.
- Direct `pi_reference` execution bypasses recognition and Domain Pack preparation.
  Direct and delegated execution use the same injected general executor. Missing
  host configuration does not activate the restricted ordinary-session fallback.
- Accepted resources freeze the executor identity, capability, timeout, original
  parent Attempt, instruction, and shared history. General tasks receive reader
  text and no prior Authority resource collection or internal model projection.
- The scheduler executes source-bound goals in dependency order. A failed goal
  blocks its dependants while independent work can finish. Business preparation
  receives only that goal's requested profiles, referenced history, and typed
  `PiTaskResult` external observations. Observation input creates no Authority
  reference and does not apply an automatic model change.
- A single general answer is returned directly. Mixed output identifies business
  results and general observations. Professional admission remains required for
  every completed business goal; a limited answer cannot forge professional
  success. Typed partial admission applies only when business work never started.
- General tool observations, child lifecycle, source receipts, artifact receipts,
  and usage are diagnostic Thread events. Assistant text uses the public text
  event contract. Metadata receipts are bounded and retain the full metadata hash.
  Required receipt or professional admission failures remain fatal.
- Parent heartbeat, cancellation, lease checks, and deadlines reach child control.
  Stable task identities use the frozen original parent and accepted goal identity.
  The host replay test proves a repeated task request does not repeat its action.
- Memory and PostgreSQL now save an immutable accepted decision separately from
  input. Retry copies both snapshots, rebinds only current Attempt/message identity,
  and does not call recognition again. Existing custom planners keep their
  three-argument contract through an explicit optional planner feature flag.
  Retry acceptance mode is verified through the existing central event helpers.

### Red and green evidence

- Initial new delegation tests: five failures for the absent executor API.
- Follow-up red checks covered mixed source excerpts, failed general assurance,
  discovery, typed observations, business dependencies, child receipts, large
  source metadata, and configuration changes before execution.
- Decision persistence tests first failed for absent memory/PostgreSQL methods.
  The changing-recognizer regression then proved one recognition call and
  identical child request documents across retry.
- Final delegation suite: **31 passed**.
- Final focused runtime, admission, worker, history, and decision persistence
  suite: **123 passed, 2 skipped** in 11.20 seconds.
- Actual PostgreSQL 17 checks: decision persistence, PostgreSQL Thread, and
  conversation context suites: **29 passed** in 1.88 seconds. These used a
  temporary localhost Docker database. The container was removed. The live
  Capstone database was not used.
- Broad Capstone suite excluding registered-worker integration: **866 passed,
  49 skipped**, one existing Starlette deprecation warning, in 45.69 seconds.
  The final focused suite also checked the admission-persistence guards.
- Hosted application checks: pandapower **2 passed**; PyPSA **5 passed**.
- Pyright over all changed source files: **0 errors, 0 warnings**.
- `git diff --check`: passed.

### Delivery limits

No paid Provider call, deployment, or local image rebuild was performed by this
task. The parent owns the rebuild, full repository gates, and final review.
External observations do not implement automatic unit/location/time mapping or
model-input authorization. Source and artifact receipts do not imply that the
browser has a public download endpoint. Real general Pi task quality and cost
remain separate authorized acceptance work.

## Workstream B Task 3 Second Review Fix: Boundary Hardening and Compatibility

### RED Evidence

The review regressions were added before the implementation changes:

```text
PYTHONPATH=packages/capability-agent-kernel/src:packages/grid-agent/src \
  uv run --project packages/grid-agent pytest \
  packages/capability-agent-kernel/tests/trajectory/test_artifacts.py::test_registry_rejects_custom_policy_escape_before_creating_outside_file \
  packages/capability-agent-kernel/tests/trajectory/test_artifacts.py::test_registry_rejects_non_plain_layout_components_before_writing \
  packages/capability-agent-kernel/tests/trajectory/test_events.py::test_event_source_schema_exposes_only_the_neutral_default \
  packages/capability-agent-kernel/tests/trajectory/test_events.py::test_inventory_observation_claim_category_is_recordable \
  packages/grid-agent/tests/trajectory/test_events.py::test_grid_build_event_preserves_legacy_direct_hash_while_kernel_stays_neutral \
  packages/grid-agent/tests/trajectory/test_answers.py::test_grid_answer_models_are_exact_kernel_aliases \
  packages/grid-agent/tests/trajectory/test_answers.py -q
10 failed, 1 passed
```

The failures demonstrated that a custom policy could pass a component traversal
to the descriptor opener, the kernel still rejected an opaque inventory
category, the model schema exposed the legacy producer default, direct grid
event construction was still the kernel function, and the grid claim model was
still a subclass.

### Change

- Added component-level layout and candidate validation before any open or
  pointer construction. Invalid absolute, empty, dot, dot-dot, non-plain, and
  escaping paths fail closed; resolved containment and the existing descriptor
  no-follow checks both remain enforced.
- Added custom-policy and unsafe-layout regressions proving that an attempted
  escape does not create an outside file.
- Changed kernel claim categories to bounded opaque strings. The grid answer
  policy retains the grid category taxonomy and historical validation messages.
- Removed the legacy producer override from `EventSource` schema metadata and
  regenerated the checked-in schema with the neutral producer default.
- Restored exact kernel aliases for grid `AnswerClaim` and `AnswerSubmission`.
  The grid validation function remains an explicit compatibility wrapper using
  `GridAnswerReferencePolicy` by default.
- Added a grid-owned `build_event` wrapper that injects the legacy producer for
  direct compatibility calls. Event model classes remain identity-preserving,
  while the wrapper's hash and producer match an explicit legacy-source build.

### GREEN Evidence

```text
PYTHONPATH=packages/capability-agent-kernel/src:packages/grid-agent/src \
  uv run --project packages/grid-agent pytest \
  packages/capability-agent-kernel/tests/trajectory \
  packages/grid-agent/tests/trajectory -q
360 passed, 1 warning

PYTHONPATH=packages/capability-agent-kernel/src:packages/grid-agent/src \
  uv run --project packages/grid-agent pytest \
  packages/capability-agent-kernel/tests/test_boundaries.py -q
2 passed

uv run --project packages/grid-agent ruff check <trajectory source and test paths>
All checks passed!

PYTHONPATH=packages/capability-agent-kernel/src:packages/grid-agent/src \
  pyright <trajectory source paths>
0 errors, 0 warnings, 0 informations

make check-package-boundaries
package-boundaries: ok

git diff --check 4e1003c -- <trajectory, schema, and Task 3 report paths>
exit 0
```

Provider validation was not run. JOURNAL and concurrent Task 6 changes remain
uncommitted and untouched.

### Commit

The second-review fix commit hash is reported in the handoff because this
report is included in the commit.

### Risks

- Direct construction of a grid `AnswerClaim` now performs neutral structural
  validation only; grid taxonomy and lineage checks intentionally require the
  grid policy or the grid compatibility validation wrapper.
- The grid `build_event` function is intentionally not an identity alias, but
  all event model classes remain identity-preserving and the wrapper preserves
  historical direct-call hashes.

## Workstream B Task 3: Neutral Trajectory Lifecycle Extraction

### Scope

Extracted the proven, domain-neutral trajectory lifecycle into
`capability-agent-kernel` under `capability_agent.trajectory`:

- canonical JSON and SHA-256 helpers;
- typed event models and hash-chain event construction;
- immutable artifact registration and verification;
- answer-reference validation;
- fail-closed event reading;
- durable event recording;
- native/imported replay interfaces.

The seven `grid_agent.trajectory` modules are compatibility exports for the
neutral lifecycle types. Grid-specific path and answer policies remain owned by
the application, while capture, projections, context bridge, materialization,
API, service, and legacy import modules remain application-owned.

### RED Evidence

After copying the behavioral lifecycle tests and changing only their imports to
`capability_agent.trajectory`, the required direct suite failed during
collection because the new package namespace was absent:

```text
uv run --project packages/grid-agent pytest packages/capability-agent-kernel/tests/trajectory -q
5 collection errors: ModuleNotFoundError: No module named 'capability_agent.trajectory'
```

### GREEN Evidence

```text
uv run --project packages/grid-agent pytest packages/capability-agent-kernel/tests/trajectory -q
107 passed in 0.20s

uv run --project packages/grid-agent pytest packages/grid-agent/tests/trajectory -q
242 passed, 1 warning in 1.24s

make check-package-boundaries
package-boundaries: ok

ruff check <Task 3 source and test paths>
All checks passed!

PYTHONPATH=packages/capability-agent-kernel/src:packages/grid-agent/src \
  pyright <Task 3 source paths>
0 errors, 0 warnings, 0 informations

uv run --project packages/grid-agent python -m compileall -q <Task 3 paths>
exit 0

git diff --check
exit 0
```

An identity smoke check confirmed the legacy and kernel `RunEvent`, artifact
registry, answer submission, reader, recorder, and imported replay classes are
the same objects.

### Commit

`refactor: extract neutral trajectory lifecycle` (final hash is reported in the
handoff because updating this report changes the hash itself).

### Risks and Residuals

- Grid path layouts and answer validation remain unchanged through explicit
  application-owned policies; the kernel's default artifact layouts and answer
  categories are domain-neutral.
- `EventSource` is neutral by default and the grid application explicitly
  injects its producer. Persisted schema identifiers remain named legacy
  compatibility constants, and the boundary test AST-decodes their values.
- The package remains intentionally lifecycle-only; application/grid-specific
  trajectory modules are not yet extracted.
- Pyright requires both source roots in `PYTHONPATH` for this checkout because
  the package is supplied through the local editable workspace dependency.
- Provider validation was not run.

## Workstream B Task 3 Review Fix: Explicit Domain Policies

### RED Evidence

The review regressions were added before the implementation changes:

```text
uv run --project packages/capability-agent-kernel pytest \
  packages/capability-agent-kernel/tests/test_boundaries.py::test_kernel_source_has_no_grid_owned_semantic_literals -q
5 decoded escaped grid literals reported by the AST boundary scan

uv run --project packages/capability-agent-kernel pytest \
  packages/capability-agent-kernel/tests/trajectory/test_artifacts.py::test_neutral_inventory_policy_can_be_injected_without_domain_layouts \
  packages/capability-agent-kernel/tests/trajectory/test_answers.py::test_neutral_reference_policy_accepts_inventory_claims_and_references -q
collection failed because ArtifactLayout and NeutralAnswerReferencePolicy were absent
```

### GREEN Evidence

- Added injected `NeutralArtifactPathPolicy`/`ArtifactLayout`; grid result and
  evidence paths now live in `GridArtifactPathPolicy` and are supplied by grid
  production callers and tests.
- Added injected `NeutralAnswerReferencePolicy`; grid taxonomy, reference
  prefixes, and historical error messages remain in the grid compatibility
  policy.
- Removed all source escape-based workarounds. Native and imported schema strings are
  named legacy constants with narrow AST allowlisting and reasons; event
  producer defaults are neutral and the grid app supplies its producer.
- Corrected the three new blank-line-at-EOF diagnostics and verified the real
  baseline range with `git diff --check 4e1003c -- .`.

```text
uv run --project packages/grid-agent pytest \
  packages/capability-agent-kernel/tests/trajectory \
  packages/grid-agent/tests/trajectory -q
349 passed, 1 warning

uv run --project packages/capability-agent-kernel pytest \
  packages/capability-agent-kernel/tests/test_boundaries.py -q
2 passed

ruff check <review-fix source and test paths>
All checks passed!

PYTHONPATH=packages/capability-agent-kernel/src:packages/grid-agent/src \
  pyright <review-fix source paths>
0 errors, 0 warnings, 0 informations

git diff --check 4e1003c -- .
exit 0
```

### Commit

The review-fix commit hash is reported in the handoff because this report is
included in the commit.

### Risks

- `AnswerClaim` in the grid compatibility module is a validating specialization
  rather than the neutral kernel class; `AnswerSubmission` and the other
  lifecycle types retain their kernel identities.
- Provider validation was not run.

## Third Review Fix: Runtime Root Containment

### Finding

Third review found a remaining MEDIUM containment gap: the installer validated containment against `self.pi_runtime_dir.resolve()`, so a symlinked `.grid-agent/runtime/pi` root could redirect the managed runtime root to an outside directory and still become the accepted containment base.

### Change

- Added managed runtime root validation before source validation, marker removal, patch verification, or any runner command.
- Rejects symlinked `.grid-agent/runtime/pi` roots.
- Creates a normal missing runtime root, then verifies it is a non-symlink directory.
- Validates `source` as a child under the already validated, non-symlink runtime root.
- Retains previous leaf `source` symlink protections.
- On symlinked root state, `PiRuntimeInstallerError` is raised, runner is not called, stale outside marker remains unchanged, and outside data remains unchanged.

### RED Evidence

New regression before implementation:

```text
uv run --project packages/grid-agent pytest packages/grid-agent/tests/runtime/test_installer.py::test_installer_rejects_symlink_runtime_root_before_runner_or_marker_mutation -q
1 failed in 0.06s
```

Failure proved a symlinked runtime root was accepted and install proceeded.

### GREEN Evidence

New regression:

```text
uv run --project packages/grid-agent pytest packages/grid-agent/tests/runtime/test_installer.py::test_installer_rejects_symlink_runtime_root_before_runner_or_marker_mutation -q
1 passed in 0.33s
```

Focused runtime tests:

```text
uv run --project packages/grid-agent pytest packages/grid-agent/tests/runtime/test_installer.py packages/grid-agent/tests/runtime/test_locator.py -q
29 passed in 0.20s
```

Full grid-agent tests:

```text
uv run --project packages/grid-agent pytest packages/grid-agent/tests -q
537 passed, 1 warning in 73.34s
```

Additional checks:

```text
uv run --project packages/grid-agent python -m compileall -q packages/grid-agent/src/grid_agent/runtime packages/grid-agent/tests/runtime
exit 0

git diff --check
exit 0

rg "breakpoint\\(|pdb\\.set_trace|TODO DEBUG|print\\(" packages/grid-agent/src/grid_agent/runtime packages/grid-agent/tests/runtime/test_installer.py packages/grid-agent/tests/runtime/test_locator.py -n
exit 1, no matches
```

### Residual

The pinned Pi 0.80.6 dependency-audit finding remains out of scope and was not changed.
