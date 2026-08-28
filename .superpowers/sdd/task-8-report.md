# Task 8 Report: Clean artifact installation

## Summary

Implemented a hermetic package artifact gate for the extracted packages.

- Added `make test-packages`.
- Added `tools/test_package_artifacts.sh`.
- Added installed smoke coverage at `packages/grid-agent/tests/contract/installed_smoke.py`.
- Restricted both npm package tarballs to runtime `src/` files via `files`.

The gate builds four Python wheels and two npm tarballs into a temporary
artifact directory, creates a clean venv, installs the four local wheels in one
`uv pip install` invocation, copies the smoke program to a non-repository
temporary directory, and runs it from there.

## TDD Evidence

RED:

```sh
make test-packages
```

Initial result: failed after clean wheel install and smoke success because
`@capability-agent/pi-tools` tarball included
`package/test/domain-tools.test.mjs` and
`package/test/model-request-capture.test.mjs`.

GREEN:

```sh
make test-packages
```

Result: passed with:

```text
package-boundaries: ok
installed-smoke: ok
package-artifacts: ok
```

## Verification

```sh
make test-packages
```

Result: passed. The output included all required markers:

```text
package-boundaries: ok
installed-smoke: ok
package-artifacts: ok
```

```sh
make check-package-boundaries
```

Result: passed with `package-boundaries: ok`.

```sh
git diff --check
```

Result: passed with no whitespace errors.

## Notes

- The smoke program uses a fake executor for `environment.describe`, derived
  from the installed capability contract documents, so no provider and no real
  simulator invocation are needed.
- The smoke program materializes and validates both `tool-catalog.json` and
  `guide-index.json`.
- No repository-path fallback was added.
- Python packaging manifests did not require changes; installed resources were
  already present in clean wheels.
- Existing controller changes in `docs/status/JOURNAL.md` and
  `docs/status/RESUME-NEXT-SESSION.md` were left untouched and unstaged.
