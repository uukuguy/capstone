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

## Review Fix Addendum

Fixed both Important review findings from `task-8-review.md`.

- `@grid-static-analysis/pi-grid-tools` no longer publishes a repo-relative
  `file:../pi-capability-tools` dependency. Its dependency is now the exact
  semver `@capability-agent/pi-tools@0.1.0`, and the package exports both `.`
  and `./model-request-capture`.
- `tools/test_package_artifacts.sh` now installs both produced npm tarballs in
  one `npm install` from a clean non-repository temporary cwd, runs `npm ls`
  for both packages, and imports both top-level and subpath exports.
- npm tarball inspection now uses Python `tarfile` member iteration with
  explicit member-name validation instead of raw `tar -tf | grep`.
- The tarball boundary self-test creates negative tar fixtures and verifies the
  checker rejects `Foo.MAP`, `.ENV`, `unit.test.mjs`, `../escape`, backslashes,
  and `%2f`/`%5c` encoded separators.

Review RED 1:

```sh
make test-packages
```

Output:

```text
npm error code ELSPROBLEMS
npm error invalid: @capability-agent/pi-tools@
make: *** [test-packages] Error 1
```

This proved the previous grid npm tarball was not independently clean
installable.

Review RED 2:

```sh
make test-packages
```

Output:

```text
npm tarball boundary self-test expected rejection: artifact-boundary-negative-1.tgz
make: *** [test-packages] Error 1
```

This proved the previous raw tar listing predicate missed the `Foo.MAP`
negative fixture.

Review GREEN and verification:

```sh
make test-packages
```

Output:

```text
package-boundaries: ok
installed-smoke: ok
npm-tarball-boundary-selftest: ok
npm-install-smoke: ok
package-artifacts: ok
```

```sh
npm run check --prefix packages/pi-capability-tools
```

Output:

```text
node --check src/domain-tools.mjs && node --check src/model-request-capture.mjs
```

```sh
npm test --prefix packages/pi-capability-tools
```

Output:

```text
tests 11
pass 11
fail 0
```

```sh
npm run check --prefix packages/pi-grid-tools
```

Output:

```text
node --check src/domain-tools.mjs && node --check src/model-request-capture.mjs
```

```sh
npm test --prefix packages/pi-grid-tools
```

Output:

```text
tests 34
pass 34
fail 0
```

```sh
make check-package-boundaries
```

Output:

```text
package-boundaries: ok
```

```sh
git diff --check
```

Output: no whitespace errors.

Additional check:

```sh
rg -n 'file:\.\./pi-capability-tools|\.\./pi-capability-tools|invalid|link' packages/pi-grid-tools/package.json packages/pi-grid-tools/package-lock.json
```

Output: no matches.
