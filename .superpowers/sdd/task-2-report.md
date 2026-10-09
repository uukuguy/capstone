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

## M6 Task 2 review fixes

The independent review identified state-machine gaps in the initial pure
execution model. The fix now rejects completion from a failed, cancelled, or
interrupted Attempt until `with_current_step()` installs a distinct retry
Attempt, and refuses to overwrite an active running Attempt. Durable step
state rejects answer/result/evidence fields on every non-completed status.
Terminal executions validate the incoming Attempt identity before returning an
idempotent no-op. `SequentialBatchExecutor` is frozen after its definitions
are pinned and checks the Case identity/revision when created from a full
`CaseDefinition`; it cannot be rebound to another definition. Test fixtures
use Literal-compatible status annotations so source and test Pyright checks
cover the same contracts.

Review-fix verification:

```text
uv run --directory packages/capstone-agent pytest tests/test_case_execution.py -q
16 passed

uv run --directory packages/capstone-agent pytest tests/test_case_definition.py tests/test_case_execution.py -q
32 passed

uv run ruff check packages/capstone-agent/src/capstone_agent/case_execution.py packages/capstone-agent/tests/test_case_execution.py
All checks passed!

uv run pyright packages/capstone-agent/src/capstone_agent/case_execution.py packages/capstone-agent/tests/test_case_execution.py
0 errors, 0 warnings, 0 informations

## M6 Task 2 pinning review fix

The follow-up review found that a sequence-only `SequentialBatchExecutor`
could advance a foreign Case with the same number of steps because it had no
Case identity or revision to compare. The executor now refuses `advance()`
until a complete `CaseDefinition` identity/revision and ordered step tuple are
pinned. Sequence constructors remain available for tests and bind exactly once
through `create_execution()`; full `CaseDefinition` construction normalizes the
ordered definitions to an immutable tuple, and reuse rejects a different
definition.

Regression coverage includes the unbound sequence fail-closed path and a
foreign same-length Case identity/revision mismatch.

TDD evidence:

```text
uv run --directory packages/capstone-agent pytest tests/test_case_execution.py -q
17 passed, 1 failed (expected RED: unbound sequence advance did not raise)

uv run --directory packages/capstone-agent pytest tests/test_case_execution.py -q
18 passed

uv run --directory packages/capstone-agent pytest tests/test_case_definition.py tests/test_case_execution.py -q
34 passed

uv run ruff check packages/capstone-agent/src/capstone_agent/case_execution.py packages/capstone-agent/tests/test_case_execution.py
All checks passed!

uv run pyright packages/capstone-agent/src/capstone_agent/case_execution.py packages/capstone-agent/tests/test_case_execution.py
0 errors, 0 warnings, 0 informations
```
```


---

## Shared general Pi delivery — 2026-10-09

### Native executor — 1964dc5

Implemented 11 owned files. The first launch/RPC tests failed for the missing
module; 14 focused process/server tests then passed. The real Docker check
found missing controller permissions and a detached tool that survived its
parent. Task UID cleanup fixed those failures. Both entry points passed with
actual bash/read/write/edit inventory, saved products, zero live task processes,
denied access to `/proc/1/environ`, and absent business assets.

The native test and Docker build passed. Combined contract/process/server
checks passed 55 tests; source/process checks passed 14 after source capture
was added. These checks used only a local loopback Provider.

The root service and each Pi task have separate UIDs in a dedicated image.
The task environment excludes Provider credentials and the control token.
Each task uses a relay grant that is revoked during cleanup. The image has
no business packages or assets. Managed native configuration discovery is active.

Compose declares a separate network, read-only root, task tmpfs, persistent
receipt volume, and limited controller capabilities. Full Compose and hosted
integration were still pending at this commit. Source records identify actual
tool observations; they do not independently verify external documents.

### Review fixes — 153734a

Task UID termination now precedes pipe closure. Native timeout test starts a detached child that retains pipes; bounded client cancellation confirms a terminal receipt and zero live task UID. All launch/cleanup paths revoke relay grants in an independent finally block. Multibyte answer or artifact persistence failure settles failed and releases workspace.

Private storage keeps hash-checked product bytes and provides authenticated bounded retrieval. Default content retention: 24 hours; aggregate storage: 64 MiB; durable receipt/tombstone capacity: 4096. Expired input/result/observations/products are removed; finite tombstones prohibit blind replay. Capacity exhaustion rejects new work. Receipt restoration observes the memory cap.

Actual active tools are obtained through Pi's public extension API and RPC notification during startup, without a Provider call. Readiness publishes this inventory. Both task entry points preserve token/cache counts and reported usage; price is explicitly unknown. Relay supports API-key chat-completions transport; Anthropic/OAuth configuration is rejected.

Verification: 19 process/server tests pass; changed modules Pyright has zero errors. Rebuilt native image and real native test pass in the Compose-equivalent read-only/capability/memory/PID/tmpfs layout, including product retrieval and inherited-pipe timeout. Loopback fake Provider only. Full Compose rebuild and hosted integration remain Task5. Native RPC implementation is local to this isolated service because task-UID/process-tree ownership is outside the professional PiRpcClient contract.
