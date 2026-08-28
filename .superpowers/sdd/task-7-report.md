# Task 7 Report: Explicit Extracted-Package Assembly

## Summary

Implemented Workstream B Task 7.

- Switched production `grid-agent` CLI assembly to direct owning imports:
  - `capability_agent.application.prepare_domain_runtime`
  - `capability_agent.domain.ArtifactAuthority`
  - `pandapower_domain.build_pandapower_profile`
- Removed repository-root arguments from the production pandapower profile selection paths.
- Added controller-side Pi runtime descriptor materialization in `PiConfigMaterializer.materialize_domain_runtime`.
- Added `RuntimePaths.domain_runtime_descriptor_path` and passed only `CAPABILITY_AGENT_RUNTIME_DESCRIPTOR` to the Pi child environment while preserving existing `GRID_AGENT_*` variables.
- Extended package boundary checks so production CLI code cannot regress to compatibility assembly imports.
- Preserved stdout/stderr contracts and did not add shell, filesystem, Python, pandapower, or arbitrary execution capabilities to the model.

## TDD Evidence

RED:

```sh
uv run --project packages/grid-agent pytest \
  packages/grid-agent/tests/cli/test_app.py \
  packages/grid-agent/tests/runtime/test_pi_config.py \
  packages/grid-agent/tests/contract/test_package_extraction_baseline.py -q
```

Result: failed as expected:

- `test_cli_assembles_runtime_from_extracted_package_owners` failed because `cli/app.py` still imported compatibility paths.
- `test_materializer_writes_fixed_domain_runtime_descriptor` failed because `PiConfigMaterializer.materialize_domain_runtime` did not exist.
- `test_pi_launch_adds_only_domain_runtime_descriptor_path_to_legacy_grid_environment` failed because `RuntimePaths.domain_runtime_descriptor_path` did not exist.

GREEN focused verification:

```sh
uv run --project packages/grid-agent pytest \
  packages/grid-agent/tests/cli/test_app.py \
  packages/grid-agent/tests/runtime/test_pi_config.py \
  packages/grid-agent/tests/contract/test_package_extraction_baseline.py -q
```

Result: `20 passed in 0.26s`.

## Implementation Details

- Descriptor path: `.grid-agent/pi/domain-runtime.json`.
- Descriptor payload is canonical JSON with sorted keys, compact separators, and a trailing newline.
- Descriptor mode is fixed to `0600`; Pi config directory mode is fixed to `0700`.
- Descriptor executable is manifest-owned and fixed to `gridctl`.
- Descriptor executable arguments are controller-owned and fixed to:

```json
["request", "--workspace", "<current run path>"]
```

- Descriptor tool names are derived from the manifest prefix:
  - `grid_guide_open`
  - `grid_analysis_context_get`
  - `grid_record_decision`
- Writes use `tempfile.mkstemp`, `fsync`, and atomic replace.

## Verification

Boundary and focused/broader suites:

```sh
make check-package-boundaries
uv run --project packages/grid-agent pytest \
  packages/grid-agent/tests/cli \
  packages/grid-agent/tests/runtime \
  packages/grid-agent/tests/domain \
  packages/grid-agent/tests/application -q
```

Result:

- `package-boundaries: ok`
- `95 passed in 0.84s`

Offline E2E:

```sh
uv run --project packages/grid-agent pytest \
  packages/grid-agent/tests/e2e/test_offline_walking_skeleton.py \
  packages/grid-agent/tests/e2e/test_semantic_pi_path.py -q
```

Result: `14 passed in 31.17s`.

Diff hygiene:

```sh
git diff --check
```

Result: exit 0, no whitespace errors.

## Self-Review

- Confirmed production `cli/app.py` no longer imports `grid_agent.application.composition`, `grid_agent.domain`, or `grid_agent.domains`.
- Confirmed compatibility public imports remain covered by `test_legacy_public_imports_are_preserved`.
- Confirmed the Pi child environment still includes existing `GRID_AGENT_TOOL_CATALOG`, `GRID_AGENT_GUIDE_INDEX`, and `GRID_AGENT_WORKSPACE`.
- Confirmed descriptor fields are not expanded into environment variables; only `CAPABILITY_AGENT_RUNTIME_DESCRIPTOR` is added.
- Confirmed `docs/status/JOURNAL.md` was pre-existing controller-owned dirt and was not edited, staged, committed, or reverted.

## Concerns

None.
