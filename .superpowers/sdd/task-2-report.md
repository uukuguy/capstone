# Task 2 Report: Extract the neutral Python SDK and runtime preparation

## Scope

- Added independently buildable `capability-agent-kernel==0.1.0` with the
  `capability_agent` public namespace.
- Moved the neutral Workstream A domain contracts, catalog, guide index, and
  profile-driven runtime preparation into the kernel.
- Replaced the old `grid_agent.domain`, `grid_agent.tools`, and
  `grid_agent.application.composition` implementations with identity-preserving
  compatibility exports.
- Added the local editable kernel dependency and refreshed `packages/grid-agent/uv.lock`.
- Removed `load_packaged_capability_documents` from the neutral catalog so it no
  longer reconstructs a grid repository path.

## TDD evidence

### RED

After adding the direct kernel tests and before creating the package:

```text
uv run --project packages/grid-agent pytest packages/capability-agent-kernel/tests -q
ImportError while loading conftest ...
ModuleNotFoundError: No module named 'capability_agent'
```

### GREEN

```text
uv run --project packages/grid-agent pytest packages/capability-agent-kernel/tests -q
4 passed

uv run --project packages/grid-agent pytest packages/grid-agent/tests/domain packages/grid-agent/tests/application/test_composition.py packages/grid-agent/tests/tools -q
40 passed

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

## Commit

Implementation commit: `feat: extract capability agent kernel sdk` (final hash
is reported in the task handoff).

## Risk / note

Running the plan's combined default-import-mode pytest command with both the
new `tests/test_composition.py` and the existing
`grid-agent/tests/application/test_composition.py` causes pytest's known module
name collision (`import file mismatch`). The new kernel tests and legacy tests
were therefore run separately; the same combined set passes with
`--import-mode=importlib`.

The pre-existing dirty `docs/status/JOURNAL.md` was left untouched and
unstaged.
