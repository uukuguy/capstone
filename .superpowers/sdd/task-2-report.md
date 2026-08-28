# Task 2 Report: Extract the neutral Python SDK and runtime preparation

## Scope

- Added independently buildable `capability-agent-kernel==0.1.0` with the
  `capability_agent` public namespace.
- Moved the neutral Workstream A domain contracts, catalog, guide index, and
  profile-driven runtime preparation into the kernel.
- Replaced the old `grid_agent.domain`, `grid_agent.tools`, and
  `grid_agent.application.composition` implementations with identity-preserving
  compatibility exports. The grid tool compatibility module restores its
  repository contract loader and product-specific description/protocol
  materialization without adding those semantics to the kernel.
- Added the local editable kernel dependency and refreshed `packages/grid-agent/uv.lock`.
- Kept `load_packaged_capability_documents` only at the legacy grid import path;
  the neutral catalog consumes injected documents.
- Made kernel catalog and guide schema IDs neutral by default, with runtime
  schema IDs explicitly derived from the selected profile namespace. Tool name
  prefixes are inferred from documents when not supplied.
- Renamed the kernel composition test module to
  `test_kernel_composition.py` so the plan's combined default-import-mode
  pytest command has no module-name collision.

## TDD evidence

### RED

After adding the direct kernel tests and before creating the package:

```text
uv run --project packages/grid-agent pytest packages/capability-agent-kernel/tests -q
ImportError while loading conftest ...
ModuleNotFoundError: No module named 'capability_agent'
```

Review-fix RED evidence, before the corresponding implementation changes:

```text
test_kernel_source_has_no_grid_owned_semantic_literals
AssertionError: ['tools/catalog.py', 'tools/guide.py']

test_kernel_helpers_use_neutral_default_schema_ids
AssertionError: 'grid-tool-catalog' == 'capability-tool-catalog'

test_legacy_catalog_loader_keeps_repository_path_compatibility
ImportError: cannot import name 'load_packaged_capability_documents'
```

### GREEN

```text
uv run --project packages/grid-agent pytest packages/capability-agent-kernel/tests -q
7 passed

uv run --project packages/grid-agent pytest \
  packages/capability-agent-kernel/tests \
  packages/grid-agent/tests/domain \
  packages/grid-agent/tests/application/test_composition.py \
  packages/grid-agent/tests/tools -q
47 passed

make check-package-boundaries
package-boundaries: ok
```

The complete grid-agent suite also passed:

```text
make test-agent
620 passed, 1 warning
```

## Distribution verification

- `uv build --project packages/capability-agent-kernel` produced the 0.1.0
  sdist and wheel.
- The wheel installed in a clean temporary venv containing only the kernel and
  Pydantic; all public API imports passed.
- `git diff --cached --check` passed before commit.

## Files changed

- `packages/capability-agent-kernel/pyproject.toml`
- `packages/capability-agent-kernel/src/capability_agent/`
- `packages/capability-agent-kernel/tests/`
- `packages/grid-agent/pyproject.toml`
- `packages/grid-agent/uv.lock`
- `packages/grid-agent/src/grid_agent/domain/`
- `packages/grid-agent/src/grid_agent/tools/catalog.py`
- `packages/grid-agent/src/grid_agent/tools/guide.py`
- `packages/grid-agent/src/grid_agent/application/composition.py`
- `packages/capability-agent-kernel/tests/test_kernel_composition.py`
- `.superpowers/sdd/task-2-report.md`

## Commit

Implementation commit: `73d377b feat: extract capability agent kernel sdk`.
Review-fix commit: `fix: neutralize extracted kernel helpers` (final hash is
reported in the task handoff).

## Risk / note

The pre-existing dirty `docs/status/JOURNAL.md` was left untouched and
unstaged.
