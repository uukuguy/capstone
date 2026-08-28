# Task 1 Report: Lock Distribution and Compatibility Baselines

## Summary

Implemented Task 1 for Workstream B package extraction.

Commit:

- `a92bda0 test: characterize package extraction boundary`

The commit adds compatibility characterization for current public imports, pandapower profile runtime shape, and Pi grid request construction. It also adds `tools/check_package_boundaries.py`, a real AST/TOML boundary checker with a `--root` option, and wires it into `make check-package-boundaries`.

No real future package roots were created:

- `packages/capability-agent-kernel` absent
- `packages/pandapower-domain-pack` absent

Protected pre-existing worktree state preserved:

- `docs/status/JOURNAL.md` remained unstaged and unmodified by this task.

## Files Changed

Committed files:

- `Makefile`
- `packages/grid-agent/tests/contract/test_package_extraction_baseline.py`
- `packages/grid-agent/tests/domain/test_pandapower_profile.py`
- `packages/pi-grid-tools/test/domain-tools.test.mjs`
- `tools/check_package_boundaries.py`
- `tools/tests/test_check_package_boundaries.py`

Report artifact, not included in the commit:

- `.superpowers/sdd/task-1-report.md`

## RED Evidence

Command:

```sh
uv run --project packages/grid-agent pytest tools/tests/test_check_package_boundaries.py -q
```

Result before implementation: FAIL, 4 failed tests.

Relevant output:

```text
FFFF                                                                     [100%]
...
python: can't open file '/Users/sujiangwen/sandbox/LLM/speechless.ai/SGAI/grid-static-analysis/.worktrees/workstream-b-package-extraction/tools/check_package_boundaries.py': [Errno 2] No such file or directory
...
4 failed in 0.12s
```

This was the expected RED state from the missing checker/interface.

## GREEN Evidence

Focused boundary checker:

```sh
uv run --project packages/grid-agent pytest tools/tests/test_check_package_boundaries.py -q
```

Result:

```text
....                                                                     [100%]
4 passed in 0.14s
```

Task characterization and boundary set:

```sh
uv run --project packages/grid-agent pytest \
  packages/grid-agent/tests/contract/test_package_extraction_baseline.py \
  packages/grid-agent/tests/domain/test_pandapower_profile.py \
  tools/tests/test_check_package_boundaries.py -q
```

Result:

```text
..........                                                               [100%]
10 passed in 0.29s
```

Pi grid tools:

```sh
npm test --prefix packages/pi-grid-tools
```

Result:

```text
tests 30
pass 30
fail 0
```

Direct checker:

```sh
python3 tools/check_package_boundaries.py
```

Result:

```text
package-boundaries: ok
```

Make target:

```sh
make check-package-boundaries
```

Result:

```text
python3 tools/check_package_boundaries.py
package-boundaries: ok
```

Whitespace:

```sh
git diff --check
git diff --cached --check
```

Result: both exited `0` with no output.

Repository gates:

```sh
make doctor
```

Result:

```text
{"gridctl": ".../packages/grid-simulator/.venv/bin/gridctl", "live_probe": false}
```

```sh
make test
```

Result:

```text
packages/grid-agent/tests: 620 passed, 1 warning
packages/grid-simulator/tests: 164 passed, 126 warnings
packages/pi-grid-tools: tests 30, pass 30, fail 0
```

```sh
make validate
```

Result:

```text
pandapower 3.4.0 static-analysis coverage: 24/24 (100.00%) partial=0 missing=0 release_ready=True
```

```sh
make test-e2e
```

First run while `make validate` was also running:

```text
2 failed, 15 passed in 47.09s
```

The failures were in continuous-analysis scripted runs, including `unknown_result` during result reuse. The same command was rerun in isolation.

Isolated rerun:

```text
17 passed in 48.18s
```

## Boundary Checker Coverage

The tests cover:

- `--root` temp repository fixtures.
- A kernel violation from `from grid_agent import cli` with diagnostic `bad.py imports grid_agent.cli`.
- Deterministically sorted diagnostics across metadata, AST imports, and source-path literals.
- `ast.Import` and `ast.ImportFrom` alias expansion.
- `pyproject.toml` parsing with `tomllib`.
- Rejection of `grid-agent` dependency metadata.
- Rejection of source path literals matching `packages/.+/src`.
- Clean pass with both future roots present and valid metadata.
- Clean pass when future roots are absent.

The checker itself does not shell out.

## Self-Review

- The committed path set matches the task ownership list.
- The checker avoids simulator/runtime internals and only enforces package extraction boundaries.
- Diagnostics are sorted before printing, making failure output deterministic.
- Current-tree execution passes because the future package roots are absent.
- Temporary test fixtures create future roots only under pytest `tmp_path`, not in the real repository.
- The Makefile target uses the requested command.

## Concerns

- The first `make test-e2e` run failed while `make validate` was running concurrently. The isolated rerun passed, so this appears to be shared run-state or concurrent scripted-analysis interference rather than a Task 1 regression.
- A post-commit project-state reminder requested a journal update. I did not edit `docs/status/JOURNAL.md` because the task explicitly required preserving that unstaged file and not staging, editing, or reverting it.

## Review Fix: Normalize Distribution Names

Review found one Important issue: `tools/check_package_boundaries.py` rejected only exact `grid-agent` dependency metadata, but Python distribution names normalize case and runs of hyphen, underscore, and dot.

Fix commit:

- `69be2f1 fix: normalize boundary dependency names`

### Review RED Evidence

Command:

```sh
uv run --project packages/grid-agent pytest tools/tests/test_check_package_boundaries.py -q -k normalized
```

Result before fix: FAIL, 3 failed tests.

Relevant output:

```text
FFF                                                                      [100%]
FAILED tools/tests/test_check_package_boundaries.py::test_rejects_normalized_grid_agent_dependency_names[Grid-Agent]
FAILED tools/tests/test_check_package_boundaries.py::test_rejects_normalized_grid_agent_dependency_names[grid_agent]
FAILED tools/tests/test_check_package_boundaries.py::test_rejects_normalized_grid_agent_dependency_names[grid.agent]
3 failed, 4 deselected in 0.20s
```

Each failure returned `0` with `package-boundaries: ok`, proving the checker missed normalized spellings.

### Review GREEN Evidence

Focused regression:

```sh
uv run --project packages/grid-agent pytest tools/tests/test_check_package_boundaries.py -q -k normalized
```

Result:

```text
...                                                                      [100%]
3 passed, 4 deselected in 0.10s
```

Covering boundary tests:

```sh
uv run --project packages/grid-agent pytest tools/tests/test_check_package_boundaries.py -q
```

Result:

```text
.......                                                                  [100%]
7 passed in 0.22s
```

Python syntax/compile:

```sh
python3 -m py_compile tools/check_package_boundaries.py
```

Result: exited `0` with no output.

Current-tree checker:

```sh
python3 tools/check_package_boundaries.py
```

Result:

```text
package-boundaries: ok
```

Whitespace:

```sh
git diff --check
```

Result: exited `0` with no output.

### Fix Self-Review

- Added parameterized regression coverage for `Grid-Agent`, `grid_agent`, and `grid.agent`.
- Implemented local canonicalization only: lowercase and normalize runs of `-`, `_`, and `.` to `-`.
- Did not add a runtime dependency.
- Did not change AST import diagnostics or source-path literal diagnostics.
- Preserved unstaged `docs/status/JOURNAL.md`.

## Second Review Fix: Direct Reference Dependencies

Second review found one Important issue: PEP 508 direct references such as `grid-agent @ https://example.invalid/grid-agent.whl` were not detected because the dependency-name parser did not split on `@`.

Fix commit:

- `d13f9fc fix: reject direct grid-agent references`

### Second Review RED Evidence

Command:

```sh
uv run --project packages/grid-agent pytest tools/tests/test_check_package_boundaries.py -q -k direct_references
```

Result before fix: FAIL, 3 failed tests.

Relevant output:

```text
FFF                                                                      [100%]
FAILED tools/tests/test_check_package_boundaries.py::test_rejects_normalized_grid_agent_direct_references[grid-agent @ https://example.invalid/grid-agent.whl]
FAILED tools/tests/test_check_package_boundaries.py::test_rejects_normalized_grid_agent_direct_references[Grid_Agent @ file:///tmp/dist.whl]
FAILED tools/tests/test_check_package_boundaries.py::test_rejects_normalized_grid_agent_direct_references[grid.agent @ file:///tmp/dist.whl]
3 failed, 7 deselected in 0.12s
```

Each failure returned `0` with `package-boundaries: ok`, proving the checker missed direct-reference dependency declarations.

### Second Review GREEN Evidence

Focused regression:

```sh
uv run --project packages/grid-agent pytest tools/tests/test_check_package_boundaries.py -q -k direct_references
```

Result:

```text
...                                                                      [100%]
3 passed, 7 deselected in 0.11s
```

Covering boundary tests:

```sh
uv run --project packages/grid-agent pytest tools/tests/test_check_package_boundaries.py -q
```

Result:

```text
..........                                                               [100%]
10 passed in 0.36s
```

Python syntax/compile:

```sh
python3 -m py_compile tools/check_package_boundaries.py
```

Result: exited `0` with no output.

Current-tree checker:

```sh
python3 tools/check_package_boundaries.py
```

Result:

```text
package-boundaries: ok
```

Whitespace:

```sh
git diff --check
```

Result: exited `0` with no output.

### Second Fix Self-Review

- Added parameterized regression coverage for direct references using `grid-agent`, `Grid_Agent`, and `grid.agent` spellings.
- Extended the local dependency-name parser to split on `@` before canonicalization.
- Preserved existing handling for extras, version specifiers, environment markers, whitespace, and prior normalized-name variants.
- Did not add `packaging` or any other runtime dependency.
- Did not alter non-metadata diagnostics.
- Preserved unstaged `docs/status/JOURNAL.md`.
