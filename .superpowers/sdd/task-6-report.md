# Workstream B Task 6 Report: Extract the pandapower Domain Pack

## Summary

Task 6 now owns the complete pandapower profile adapter closure in
`pandapower_domain`:

- Moved capability-context metadata, Pydantic analysis state models, domain
  projection, and current-run artifact verification into the Domain Pack.
- Added `pandapower_domain.build_pandapower_profile()` with no repository-root
  parameter. It retains installed resources through `PandapowerResourceSet` and
  exposes the same `grid-capability/1.0`, `gridctl`, and `grid_` manifest values.
- Materialized simulator contracts, policy, and guides through
  `importlib.resources`; policy and guide files are now canonical package
  resources and are included in the wheel.
- Kept implementation-free `grid_agent.analysis.*` and
  `grid_agent.domains.pandapower` compatibility exports. The legacy builder
  accepts its former optional repository-root argument and deliberately ignores
  it.
- Moved the localized pandapower tool-description builder to the Domain Pack.
  Added the neutral public kernel `describe_tool_document` API so neither the
  Domain Pack nor grid compatibility code imports the private kernel helper.
- Preserved Pydantic class identity by forwarding old analysis model imports to
  the single Domain Pack model definitions.
- Added the direct Domain Pack test suites and refreshed Domain Pack/grid-agent
  lock metadata for the direct Pydantic dependency.

Repository resource paths that existing operator/tests still read are tracked
as symlinks to the package-owned policy and guide resources; there is no second
editable source.

## TDD evidence

RED was observed before creating the profile/projection/authority implementation:

```text
uv run --project packages/grid-agent pytest \
  packages/pandapower-domain-pack/tests/test_profile.py \
  packages/pandapower-domain-pack/tests/test_projection.py \
  packages/pandapower-domain-pack/tests/test_authority.py -q

3 collection errors: pandapower_domain had no build_pandapower_profile or
PandapowerArtifactAuthority exports.
```

The kernel description export also had a focused RED collection failure before
its implementation was added:

```text
ImportError: cannot import name 'describe_tool_document'
```

## Verification

Direct Domain Pack parity and all package tests:

```text
uv run --project packages/pandapower-domain-pack pytest \
  packages/pandapower-domain-pack/tests/test_profile.py \
  packages/pandapower-domain-pack/tests/test_projection.py \
  packages/pandapower-domain-pack/tests/test_authority.py -q
7 passed

uv run --project packages/pandapower-domain-pack pytest \
  packages/pandapower-domain-pack/tests -q
18 passed
```

Compatibility and analysis regression slices (excluding the stale pre-move
repository-path assertion in `test_pandapower_profile.py`):

```text
uv run --project packages/grid-agent pytest \
  packages/grid-agent/tests/analysis/test_capabilities.py \
  packages/grid-agent/tests/analysis/test_domain_projection.py \
  packages/grid-agent/tests/analysis/test_integrity.py \
  packages/grid-agent/tests/analysis/test_projector.py \
  packages/grid-agent/tests/analysis/test_reducer.py \
  packages/grid-agent/tests/contract/test_analysis_context_docs.py \
  packages/grid-agent/tests/trajectory/test_capture.py \
  packages/grid-agent/tests/domain/test_manifest.py \
  packages/grid-agent/tests/domain/test_contracts.py \
  packages/grid-agent/tests/application/test_composition.py -q
87 passed
```

The compatibility assertions were then updated to call the legacy builder with
its former root argument while checking that all three manifest resources equal
the installed `PandapowerResourceSet` and do not live below checkout-owned
simulator, policy, or guide paths. The legacy catalog loader now ignores its
root argument and reads the 30 installed simulator contracts through the Domain
Pack. The focused compatibility/profile and kernel public-API tests pass:

```text
uv run --project packages/grid-agent pytest \
  packages/grid-agent/tests/domain/test_pandapower_profile.py \
  packages/capability-agent-kernel/tests/test_public_api.py -q
9 passed
```

The complete application suite is green after this compatibility fix:

```text
make test-agent
634 passed, 1 warning
```

Boundary and forbidden-import checks:

```text
python3 tools/check_package_boundaries.py
package-boundaries: ok

rg -n "from grid_agent|import grid_agent" packages/pandapower-domain-pack/src
domain-source-grid-agent-imports: none
```

Ruff and Pyright passed for the moved Domain Pack modules, compatibility
exports, kernel description API, and their tests (`0 errors, 0 warnings, 0
informations`). `git diff --check` also passed.

Clean artifact smoke built kernel, simulator, and Domain Pack wheels, installed
them into a fresh Python 3.12 environment outside the checkout, loaded the
profile/resources, and opened a packaged guide:

```text
clean-domain-wheel: ok
```

The Domain Pack wheel contained policy and all guide files and had no
`grid_agent`, source-checkout, test-fixture, cache, or secret leakage.

The one warning is the existing Starlette/httpx deprecation warning from the
test environment; no trajectory files were modified or staged for this task.

The follow-up compatibility check also confirms that the legacy profile and
catalog loader contain no checkout-resource literals, and the boundary,
forbidden-import, Ruff, Pyright, and `git diff --check` gates remain clean.

## Commit

Implementation commit: `feat: extract pandapower domain pack`.

The pre-existing `docs/status/JOURNAL.md`, climb state, and unrelated trajectory
changes remain unstaged.
