# Workspace branch integration

User authorized closing fix/workspace-reading-type and integrating it into dev.
PR56 contains the accumulated application and its runtime dependencies. Browser
scratch, research-worker scratch and the superseded multi-user proposal are not
included. No cloud/demo deployment is authorized by this integration.

The candidate includes runtime b87ac5d2, App c34b4780 and acceptance docs db60bc8d.
Merge ae9dd0fe incorporates the previous dev7b2adbc6. Test correction c8bc4ac3
updates obsolete capacity assertions without changing published limits.

## Integration corrections

- Nine Python narrowing errors fixed before the first complete gate.
- Transfer recovery fixtures supply the configured transfer timeout.
- Overflow tests use an explicit small capacity profile and check the separate
  delegation-reply and event budgets. Complete professional receipts and admitted
  references remain required.
- Missing-key tests isolate the host's Provider/model override variables.
- Source/data descriptors recognize four exact registered shared-resource links,
  hash their target bytes, and reject unknown links, rebinding and missing targets.
- Source distributions and wheels materialize shared resource bytes. The enterprise
  Domain Pack is included in independent grid and PyPSA installation tests.
- Build-layer, scoped cache-maintenance and native-report checks enter the existing
  local-rebuild gate. Its aggregate coverage test failed before registration and
  passed after it.

## Local results

Product gate segments passed on the final product source, with loopback addresses
excluded from the macOS system proxy. Logs retain earlier failed runs as failures.

| Segment | Result |
| --- | --- |
| Package boundaries/global types | Pass, zero type errors |
| Professional application | 938 passed, 3 skipped, 408.80seconds |
| Simulator | 244 passed, 2 skipped, 126.94seconds |
| Shared agent | 1994 passed, 139 skipped, 100.40seconds |
| Capability SPI | 13 passed |
| App | 942 passed, 82files |
| Client | 15 passed |
| Deployment/runtime contracts | 94 passed, 3 skipped |
| Local installation/data contracts | 211 passed |
| Verification targets | 52 passed |
| Kernel | 658 passed |
| pandapower Domain Pack | 144 passed |
| Generic tools | 116 passed |
| Inventory | 11service, 132pack, 1transport passed |
| PyPSA | 58authority/modeling/sector, 1planning, 5operations, 7cases, 58application passed |
| Workbench | 156 passed |
| Registered workers | 3 passed |
| Additional build/cache/report checks | 39 passed, 2subtests |
| Shared-resource and deployment regressions | 41 passed |
| Full legacy reference aggregate | 997 passed, 3 skipped |
| E2E | 39 passed |

Offline and scripted validation plus real SDK capture checks passed. Artifact
installation and source setup passed, including installed resource configuration,
grid smoke, HTTP Authority, PyPSA modeling/operations/planning/sector, installed
SDK registration and frozen source installation. Remote CI must
pass on the final commit before merge; earlier cancelled revisions do not count.

Primary logs: /tmp/workspace-integration-check-pr-direct.log,
/tmp/workspace-integration-check-pr-resume-final.log,
/tmp/workspace-integration-remaining.log,
/tmp/workspace-integration-final-packages.log,
/tmp/workspace-integration-release-extra.log,
/tmp/workspace-packages-final.log. Preserved dev control state:
c306060c175483dbcfa9eec8f4ae0875e593d219. Unique documentation reconciliations are
retained for the dev control closeout.

URL-named workspace isolation, workspace name display and refined home/empty
states remain follow-up work. They are not accepted as implemented here.
