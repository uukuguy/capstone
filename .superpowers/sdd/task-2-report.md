# Task 2 Report: Extract the neutral Python SDK and runtime preparation

## Scope

- Added independently buildable `capability-agent-kernel==0.1.0` with the
  `capability_agent` public namespace.
- Moved the neutral Workstream A domain contracts, catalog, guide index, and
  profile-driven runtime preparation into the kernel.
- Replaced the old `grid_agent.domain`, `grid_agent.tools`, and
  `grid_agent.application.composition` implementations with identity-preserving
  compatibility exports. The grid tool compatibility module retains only its
  repository contract loader; it no longer mutates kernel classes or installs
  product behavior at import time.
- Added the local editable kernel dependency and refreshed `packages/grid-agent/uv.lock`.
- Kept `load_packaged_capability_documents` only at the legacy grid import path;
  the neutral catalog consumes injected documents.
- Made kernel catalog and guide schema IDs neutral by default, with runtime
  schema IDs explicitly derived from the selected profile namespace. Tool name
  prefixes are inferred from documents when not supplied. Catalog extension
  limitations are read through a generic recursive rule, and an optional
  profile description builder provides an explicit presentation seam.
- Added the explicit grid description builder in the grid-owned compatibility
  layer and injected it through the pandapower runtime profile, preserving the
  product's localized flow-direction warning without changing shared kernel
  behavior.
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

Second review RED evidence, before removing compatibility import side effects:

```text
test_legacy_modules_do_not_mutate_kernel_class_methods
AssertionError on ToolCatalog.from_documents.__func__ identity

test_kernel_helpers_use_neutral_default_schema_ids
AssertionError: 'capability-tool-catalog' == 'inventory-tool-catalog'
```

The first failure was caused by the legacy catalog and guide modules replacing
shared classmethods during import. The second failure showed that a neutral
catalog must derive its default schema namespace from the resolved tool-name
prefix.

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

Second review focused GREEN evidence:

```text
uv run --project packages/grid-agent pytest \
  packages/capability-agent-kernel/tests/test_public_api.py::test_legacy_modules_do_not_mutate_kernel_class_methods \
  packages/capability-agent-kernel/tests/test_kernel_composition.py::test_kernel_helpers_use_neutral_default_schema_ids -q
2 passed

uv run --project packages/grid-agent pytest packages/capability-agent-kernel/tests -q
8 passed

uv run --project packages/grid-agent ruff check [modified Task 2 Python files]
All checks passed!

uv run --project packages/grid-agent pyright [modified Task 2 Python files]
0 errors, 0 warnings, 0 informations
```

The original combined focused command reaches `46 passed, 2 failed`; the two
failures are pre-existing direct grid-helper assertions for product-specific
description text and the legacy guide schema default. They bypass the explicit
profile composition path and require the out-of-scope grid test/domain-pack
migration to pass a description builder and guide protocol explicitly. The
kernel and compatibility-layer GREEN evidence above does not rely on those
legacy defaults.

The final compatibility fix first changed those direct tests to assert the
neutral defaults and generic extension limitation behavior, then added a real
pandapower Profile composition regression for the product-specific builder and
schema IDs. The complete original focused command is now green:

```text
uv run --project packages/grid-agent pytest \
  packages/capability-agent-kernel/tests \
  packages/grid-agent/tests/domain \
  packages/grid-agent/tests/application/test_composition.py \
  packages/grid-agent/tests/tools -q
49 passed

make test-agent
621 passed, 1 warning

make check-package-boundaries
package-boundaries: ok
```

Before the second-review refactor, the complete grid-agent suite passed:

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
- `packages/grid-agent/src/grid_agent/domains/pandapower.py`
- `packages/grid-agent/tests/application/test_composition.py`
- `packages/grid-agent/tests/tools/test_catalog.py`
- `packages/grid-agent/tests/tools/test_guide.py`
- `packages/capability-agent-kernel/tests/test_kernel_composition.py`
- `.superpowers/sdd/task-2-report.md`
- `packages/capability-agent-kernel/src/capability_agent/domain/profile.py`

## Commit

Implementation commit: `73d377b feat: extract capability agent kernel sdk`.
Review-fix commit: `fix: neutralize extracted kernel helpers` (final hash is
reported in the task handoff).
Second review-fix commit: `fix: remove compatibility import side effects` (final
hash is reported in the task handoff).
Final compatibility-fix commit: `fix: restore grid profile presentation compatibility`
 (final hash is reported in the task handoff).

## Risk / note

The pre-existing dirty `docs/status/JOURNAL.md` was left untouched and
unstaged. Grid-specific presentation now enters only through the explicit
profile hook; no import-order behavior is used.

## M6 Task 2: Pure CaseExecution state and sequential strategy

Implemented immutable, bounded Case execution state in
`packages/capstone-agent/src/capstone_agent/case_execution.py`:

- `PinnedCaseContext`, `CaseStepState`, and `CaseExecution` use frozen slotted
  dataclasses and bounded `to_document`/`from_document` projections.
- `StepOutcome` provides running and terminal factories, serialisation, and
  clears partial answer/result/evidence data for non-success outcomes.
- `SequentialBatchExecutor.advance` waits for running outcomes, requires the
  exact current terminal attempt ID, preserves completed steps, advances only
  after committed success, and blocks failed/cancelled/interrupted steps.
- Initial execution creation remains pure state construction; Turn and Attempt
  dispatch stay outside this module.

TDD evidence:

```text
uv run --directory packages/capstone-agent pytest tests/test_case_execution.py -q
8 passed

uv run --directory packages/capstone-agent pytest tests/test_case_definition.py tests/test_case_execution.py -q
24 passed

uv run ruff check packages/capstone-agent/src/capstone_agent/case_execution.py packages/capstone-agent/tests/test_case_execution.py
All checks passed!

uv run pyright packages/capstone-agent/src/capstone_agent/case_execution.py
0 errors, 0 warnings, 0 informations
```

Files added:

- `packages/capstone-agent/src/capstone_agent/case_execution.py`
- `packages/capstone-agent/tests/test_case_execution.py`
