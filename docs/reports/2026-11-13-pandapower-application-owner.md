# Pandapower application ownership migration

## Accepted merged development source (2026-11-14)

PR101 merged as0616023f;its tree exactly matches tested20469225. Focused macOS
CI43443261387 passed in1m58s:988 Python,84 Node,93 App and254 overlapping public
governance checks. Earlier failed runs retain their original evidence.

Actualdev canonical rebuild passed. API and both professional workers share
image8cf3d25fed92e7deeb672bff28e493645526e396127af389adbab4a831cb2fd6
and are healthy. Native worker readiness also passed. Pi installation was cached;
scoped cache maintenance completed. Default App5173 now serves actualdev;its
repositoryRevision is0616023f and product revisiond3191a5d. Product revision
intentionally excludes later documentation and test-only commits.

The existing real Thread restores completed state after backend recreation.
Both product downloads still match registered SHA256 values. Browser recovery
retains the result preview and composer without horizontal overflow. See
[merged-dev receipt](receipts/2026-11-14-merged-dev.json),
[real-model receipt](receipts/2026-11-13-integrated-runtime.json) and
[CI receipt](receipts/2026-11-13-retirement-ci.json).

All six deployment reference edges avoid cards in browser coordinate checks.
This corrects an earlier screenshot inference of a crossing. Final control
documentation merged through PR102 as4b857ac9;its separately approved macOS docs
CI43473293838 passed2m08s. This paragraph records the post-merge receipt without
starting a self-referential documentation commit cycle. Cloud/demo and broader IG1 acceptance
are unchanged. No full release or Linux acceptance is claimed.

## Final installed retirement candidate

Real-model follow-up on the same installed source passed: a new Thread uploaded
a CSV, used tools to compute the value sum and saved total=10;continuation read
that product and saved previous_total=10. Both downloaded files match registered
SHA256 values. A new HTTP snapshot read restored completed state. Stages took
8.178s and10.224s (single samples). The [bounded receipt](receipts/2026-11-13-retirement-real-runtime.json)
contains product digests without model reasoning or credentials. This verifies
HTTP restore and actual model/tool/product continuation;browser recovery and
visual acceptance remain unverified.

Source `ecb5781b` removes the old distribution, source and CLI. Remaining shared
tests live in pandapower-application and development gates select its environment.
399 critical tests and239 gate/contract checks passed after fixing stale paths.
Full package-artifacts validation passed, including installed Python packages,
Authority experiments, PyPSA Packs and npm extension installation.

Canonical rebuild passed. API and all three workers are healthy on
`sha256:b21d9070f50d385b7614ab68ec15be359f7f2fc4bdfbd4bfcb95d0d328b2171b`.
Scoped cleanup completed;receipt ends `182236-21055.log`.
The installed environment has no grid_agent module. A running-worker Authority
environment/report probe passed with legacy imports blocked.

The installed capstone-agent CLI completed registered scripted case
`pandapower-scripted-task`, run `run-7d5414214efc6c9c00a7b4e1`, using real
gridctl tools over three turns. Captured stdout is capstone-client-result/1.0
with completed status and composite core/domains. The4435-byte saved report exists.
This is scripted execution acceptance;real-model, browser and dev integration
acceptance remain open. No cloud stage was updated.

Logs: `/tmp/capstone-retirement-artifacts.log`,
`/tmp/capstone-retirement-final-rebuild.log`,
`/tmp/capstone-retirement-installed-case.json`.
Control register and graph regenerated in both checkouts;browser enumeration
returned no sessions,so visual graph acceptance is not claimed.

## Verified independent runtime update

Candidate source `bdd4b6ab` now runs locally. The registered worker, preview,
hosted API/worker and catalog export use `pandapower_application`. Docker and
runtime configurations select its independent environment. Its installed
environment contains neither `grid_agent` nor the `grid-agent` console script.
The repository still has legacy CLI source and development commands; complete
retirement remains open.

Canonical rebuild completed successfully. API and all three workers are healthy
on `sha256:3776c9f84e1ce2f4f986f3571e28264ebecc4ddcf8716523915ff114d21f624d`,
with62 filesystem layers. The image revision label is `development`; it is not
a Git provenance claim. A byte comparison found no mismatches among1401 existing
tracked package files. Complete directory digests differed and were not used as
matching evidence.

Installed-image and running-worker probes blocked legacy imports, called the
registered Authority environment tool, rendered a1469-byte report and checked
repeat submission stability. Submission SHA256:
`379ae0da2bb7380cef42c09fd2661a4089f26ca6b06aa5f1cbca63e2d9a61e12`.
These probes use a host-created environment answer; real model/session and
browser acceptance remain open. The real scripted lineage case passed after
restoring43 shared dependency versions to the prior tested lock.

Rebuild log: `/tmp/capstone-independent-app-rebuild-20261113.log`.
Running-worker probe: `/tmp/capstone-independent-app-running-smoke.json`.
Scoped cache cleanup ran in apply mode; receipt:
`.capstone-agent/cache-maintenance-20261113-154940-77937.log`.

Subsequent candidate `b8a9a456` removes legacy CLI inputs and dedicated checks
from artifact validation. Shell syntax, wheel count and application build pass;
the full artifact suite has not run. Local running source remains `bdd4b6ab`.

## Initial migration evidence

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

Subsequent committed source changes are not yet rebuilt:

| Commit | Change | Focused evidence |
| --- | --- | --- |
| 3213a14a | Worker uses the shared runtime environment loader, without CLI imports |4 worker/projection checks |
| 28d9e417 | Network diagram projection moves to application owner |114 consumer checks,90.09s; standalone import |
| c21107e5 | Admitted Thread projection moves to application owner; host dependency declared |109 checks,88.74s; standalone import |
| 368e757a | Registry and Thread assembly move to application owner |10 registry/ownership checks;4 prepared-session checks |
| 6eaee885 | Composition and paths move; Kernel locator retains explicit command environment |35 functional checks;3 domain boundary checks |
| 0ea50d76 | Validation runner and provider-free host use current owner imports | Missing-import regression reproduced;2 checks pass |

These check groups overlap and must not be added into a unique test total.
The installed evidence above remains attributed toe4427e4a. Complete scripted
execution still reaches old workspace, contracts and validation helpers through
validation/run.py; this must be resolved before claiming runtime independence.

Move formal composition, registration, worker, previews and model projections
to the application owner. Remove worker dependencies on CLI helpers. Then switch
registered commands and retire the old console and dedicated compatibility
contracts as specified in the owning plan. Keep shared behavior checks with
their owners and verify the supported Capstone entry, reports and evidence replay.
