# Pandapower application

The supported public entry is capstone-agent. The retired grid-agent distribution,
CLI and compatibility commands have been removed.

## Ownership

The application package is packages/pandapower-application. It selects the
pandapower Domain Pack and registered gridctl Authority, owns worker/hosted entries,
reports, application workspace and trajectory projections. The Domain Pack owns
semantic tools, policies and state. Kernel owns neutral execution and contracts.
Raw pandapower networks do not cross these boundaries.

## Run registered requests

```sh
make setup-capstone
make doctor
make capstone-agent-run REQUEST=validation/client/pandapower-analysis-task.json
make capstone-agent-run REQUEST=validation/client/pandapower-analysis-test.json
```

Provider requests use the configured real model and may incur charges. Credentials
stay in protected backend environment or ignored project authentication state.
Use make auth-import-pi or make auth-login for project-local Pi authentication.
make install-pi reuses a managed runtime when its identity and version match.

For deterministic execution-contract validation:

```sh
make capstone-agent-run REQUEST=validation/client/pandapower-scripted-task.json
make validate-application
```

Scripted output is not real-model acceptance. See the [runbook](RUNBOOK.md#capstone-统一客户端)
for interactive and hosted entry points.

## Output and evidence

Captured CLI stdout contains one capstone-client-result/1.0 JSON object. It wraps
the registered application's composite result with core and domains.grid. Terminal
output shows a completion summary and report path. Progress goes to stderr.

The application persists admitted answers, reports and current-run result/evidence
references. The model cannot assert ownership of a result or invent numerical
claims. Required persistence failure remains fatal. Historical trajectory producer
labels and ignored .grid-agent storage paths are retained for existing data.

## Verification and retirement

Application tests live under packages/pandapower-application/tests. Development
commands use its independent environment. The installed application must neither
import grid_agent nor expose a grid-agent console script.

The [retirement plan](superpowers/plans/2026-10-11-retire-grid-cli.md) and
[verification report](reports/2026-11-13-pandapower-application-owner.md) distinguish
implemented, tested, installed and integrated states. A branch commit does not
prove deployment or final acceptance.
