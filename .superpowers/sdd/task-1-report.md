# M6 Task 1 Report: Trusted Application Case Definitions

## Status

DONE

## Commit

- `79647c5` — `feat: add trusted application case definitions`

## Changes

- Added frozen `CaseStepDefinition`, `CaseDefinition`, and `CaseCatalog`.
- Added strict parsing for the server-built `capstone-catalog/1.0` projection.
- Added bounded validation for case IDs, versions, model constraints, step count, titles, and instructions.
- Added raw SHA-256 instruction digests and canonical UTF-8 `case:sha256:` revisions.
- Added trusted step titles and version/model metadata to the existing pandapower and PyPSA catalog projection.
- Added focused registration, determinism, duplicate, bounds, unknown-field, schema, and lookup tests.

## TDD Evidence

The first focused run failed during collection because `case_definition.py` did not
exist:

```text
ModuleNotFoundError: No module named 'capstone_agent.case_definition'
```

After implementation, the focused tests passed:

```text
uv run --project packages/capstone-agent pytest \
  packages/capstone-agent/tests/test_case_definition.py \
  packages/capstone-agent/tests/test_catalog.py -q

11 passed in 0.02s
```

## Verification

Targeted diagnostics passed:

```text
uv run --project packages/grid-agent pyright \
  packages/capstone-agent/src/capstone_agent/case_definition.py \
  packages/capstone-agent/src/capstone_agent/catalog.py \
  packages/capstone-agent/tests/test_case_definition.py

0 errors, 0 warnings, 0 informations
```

The full Capstone Agent test suite passed:

```text
uv run --project packages/capstone-agent pytest \
  packages/capstone-agent/tests \
  --ignore=packages/capstone-agent/tests/test_registered_workers.py -q

261 passed, 27 skipped, 1 warning in 8.34s
```

The warning is the existing Starlette deprecation warning for importing
`httpx` through `starlette.testclient`. `git diff --check` passed, and the real
`build_catalog()` output was parsed successfully for pandapower and PyPSA cases.

## Concerns

- The full suite retains one pre-existing FastAPI/Starlette deprecation warning.
- The required report is committed separately from the implementation commit.
- Task 2 and Thread persistence were not started or modified.
