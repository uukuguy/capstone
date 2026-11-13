# Pandapower application ownership migration

Candidate implementation: `e4427e4a`. This is one step in the accepted
[retirement plan](../superpowers/plans/2026-10-11-retire-grid-cli.md).
The formal worker and console entry still use the old package; retirement is
not complete.

## Ownership change

`packages/pandapower-application` is independently installable. It owns the
application profile, report shell, report and trajectory rendering, report
workspace, and submission projection. These implementations moved with their
existing output behavior. The new package imports the Kernel and Domain Pack,
and does not import `grid_agent`.

Existing consumers now import the new owner directly. Removed module paths
were not replaced with forwarding aliases. The old package depends on the new
application while its remaining worker and entry modules are migrated.
This does not grant professional sessions generic tools or raw model access.

Package boundary checks reject application-to-old-package imports and reverse
Kernel/Domain Pack dependencies. The artifact build/install list includes the
new wheel. Docker adds one stable manifest layer at the dependency cache
boundary; application source uses the existing grouped `COPY packages/` layer.
The backend layer count changed from62 to63, matching that one cache boundary.

## Verification

- The first ownership test failed because the new package did not exist.
  It now loads the full profile with all `grid_agent` imports blocked.
- A separate `uv run --project packages/pandapower-application` environment
  loaded the full profile with `grid_agent` absent from the installation.
- Source distribution and wheel build passed. Artifacts are under
  `/tmp/capstone-pandapower-application-dist-20261113`.
- 82 focused application, report, workspace and submission checks passed
  in34.50seconds. They cover composite output, saved submissions, report failure,
  rejected report symlinks, persistence failure and report reconstruction.
- 72 package boundary checks passed in3.04seconds. `make doctor`, shell syntax
  for the artifact runner, and `git diff --check` passed.
- AST comparison confirms the six migrated implementations differ only in
  imports and module documentation. The wheel contains all seven application
  modules (including its package initializer), with no old-package modules.
- Initial broad application-directory run was stopped after177.03seconds when
  it entered unnecessary full-model coverage:64passed,4failed,3skipped. The four
  failures exposed one old relative profile import. It was fixed before the
  focused82-check run. The interrupted run is not accepted as a passing gate.

## Installed runtime

Canonical rebuild of `e4427e4a` passed on a single retry after an npmECONNRESET
failure. The failed build stopped before service replacement. The retry log is
`/tmp/capstone-application-owner-rebuild-retry-20261113.log`.
API and all three workers use
`sha256:5113e7b367b8311af99ff126c77b2bf76a2461cfe9f853658204051f7c3d6bda`.
Readiness passed. Scoped cache maintenance ran in apply mode; receipt ends
`145544-16964.log`.

An installed-worker probe blocked all `grid_agent` imports, invoked the actual
registered Authority environment tool, and rendered the returned environment
through the new report owner. It verified the saved question/answer envelope
and repeated projection without changing the submission bytes. Temporary
workspace files were removed. The [receipt](receipts/2026-11-13-pandapower-application-owner.json)
records the1469-byte report and submission digest. This uses a host-created
answer file for an environment query; it is not model, solver or complete
historical-run replay acceptance.

The first local probe omitted the registered answer file and failed its report
content assertion. The probe was corrected to supply that required input;
the renderer was not changed to accept unregistered answers.

No CI, dev merge or cloud deployment was performed. Existing user data and
other stages remain preserved.

## Remaining migration

Move formal composition, registration, worker, previews and model projections
to the application owner. Remove worker dependencies on CLI helpers. Then switch
registered commands and retire the old console and dedicated compatibility
contracts as specified in the owning plan. Keep shared behavior checks with
their owners and verify the supported Capstone entry, reports and evidence replay.
