# Pi branch — current dev baseline adaptation

## Source and scope

The user requested that the Pi branch include current dev before discussing
Capstone's general enterprise usage. This is a baseline merge, not a new
enterprise application implementation or a deployment.

- Branch: `feat/pi-skills-integration`.
- Previous head: `38e19db`; recovery reference:
  `archive/pi-before-dev-baseline-20261015`.
- Accepted source: `f209fb18d7abb122b689e1b1a52c54fa13bf5371`.
- Shared history is preserved. No rebase or force push is used.
- The previous uncommitted journal line is preserved in the task-specific
  `pi-journal-before-dev-20261015` stash and restored into the branch journal.

## Merge decisions

Keep Pi-native and delegated execution, immutable inputs and resource versions,
skills/MCP, context selection and input controls. Keep dev's research controller,
task records, source-bound result projections, model preparation, failure delivery
and execution presentation. The model-context cache key includes selected
capabilities and accepted resource revision; opening-time preparation has no
accepted task resource and does not run a model request.

The Pi runtime wrapper forwards model preparation to the wrapped runtime. A new
regression first failed because this forwarding method was absent, then passed.
Intent preparation failures use the current dev failure-delivery contract.
Old tests now assert retained failure answers and verified receipts instead of
requiring an absent answer. A fake test session supplies the new metrics extension.

Hosted research mode retains dev's single-loop router. The existing native Pi
intent/delegation mode remains a separate selection. This merge does **not** claim
that the general executor already shares the complete research loop. That is the
next design question. In particular, `AttemptResearch` still requires a selected
model snapshot, and general products do not become simulator evidence.

Independent review found that an early hosted research return could bypass the
Pi wrapper after an explicit mode switch. The merged entry now retains the wrapper:
Capstone research uses its existing router and business runtime; direct Pi retains
the isolated executor or fails explicitly when it is not configured. Regressions
cover all three message commands and explicit model exclusion. The actual hosted
mode-switch test confirms that missing native Pi never falls into Authority work.

The merged simulator retains the Pi structural-audit adapter and dev's current
contracts, diagnostics and metadata. Its protected tree digest is updated to the
actual merged tree; protected path scope is unchanged.

## Verification

- `make setup`, `make install-pi`, `make doctor`: passed in this worktree.
- Pyright: zero errors and warnings.
- App: 512 tests passed; type check and production build passed.
- Focused backend repeat: 169 passed, 1 optional test skipped.
- Hosted configuration, selection and mode switch: pandapower 5 passed;
  PyPSA 5 passed before the shared wrapper correction.
- Real isolated UTF-8 PostgreSQL persistence: 23 passed. The first temporary
  cluster used SQL_ASCII and returned text as bytes; the correct UTF-8 database
  passed without a product workaround.
- Simulator merge regressions: 35 passed, 2 optional tests skipped.
- Compose example configuration and `git diff --check`: passed.
- Full backend repeat with loopback proxy exclusion: 1300 passed, 65 skipped;
  one upstream Starlette deprecation warning.

The first full backend run had 1286 passes, 65 skips and 13 failures. Causes were
old answer expectations, incomplete fake session fields/resources, a removed
heuristic hook and local HTTP requests entering the host proxy. Focused repeats
with explicit loopback `NO_PROXY` passed after contract/fixture adaptation.
Independent follow-up review found no remaining merge blocker; its intent checks
passed 20 tests with 1 skip, and hosted checks passed 5 tests.
These are local source checks. Optional Docker-native and Provider
acceptance remain separate; no credentials were copied and no paid Provider
request was made. Local-dev, demos, cloud and the delivered offline archive are
unchanged. No whole-product or enterprise-business acceptance is claimed.
