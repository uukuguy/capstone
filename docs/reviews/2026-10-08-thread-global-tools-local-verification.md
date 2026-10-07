# Global grid-tool preferences

Local verification only. No remote deployment, Provider requests or new tags.

## Delivered behavior

- All registered tool groups are enabled by default. Global switches do not
  depend on the open model's family and have no “需 PyPSA 模型” restriction.
- Saving changes App preferences, without a model command or model mutation.
  The preferences survive switching models and conversations in the mounted App.
- Each new Web message supplies exact registered versions of enabled tools
  compatible with its active or pending target model. The service validates and
  binds that selection atomically before creating the Attempt. PostgreSQL and
  in-memory paths share the same validation. Application context locks remain
  enforced. Commands without this optional field retain their old behavior.
- An empty global preference can be saved. If no compatible enabled tools are
  available, the App retains the draft and rejects submission before any task
  can restore defaults. A missing catalog also fails closed when there are
  saved exclusions. Retries and registered-case starts guard against disabled
  tools; a Case continues to use its accepted preset tool configuration.

## Limits

Preferences are App memory only. Refresh restores the all-enabled default.
Persistent configuration, startup loading and reload are recorded future work.
Group preferences use stable IDs; runtime references use the catalog's exact
versions. New groups without an override follow the enabled default.

The zero-Pack runtime remains incomplete. Ordinary conversation and model
switches with no compatible enabled tools are still blocked. This delivery does
not claim independent zero-tool model access, cross-engine model conversion or
the advanced unified grid-model system.

## Verification

- Final App run: 25 files, 306 tests passed; TypeScript and Vite build passed.
- Backend focused run: 32 Attempt tests passed, including atomic selection,
  target-model activation, malformed input, idempotency and context locking.
- App model-opening coverage confirms that disabling current pandapower tools
  does not block a switch to an enabled PyPSA target, and the activating message
  contains only the enabled target tools without resetting the global choices.
- Isolated PostgreSQL container: all 15 Thread store tests passed, including
  current/pending model selection and incompatible-selection rejection. The
  test container was removed; local application data was not used.
- `make test`, `make test-e2e` and `make validate` passed. The end-to-end gate
  includes 39 grid tests and three registered-worker tests. Validation remains
  offline/scripted. A final App/focused run covers the last guarded-catalog and
  context-lock checks after their additions.
- `make doctor check-package-boundaries`, relative documentation links,
  `CLAUDE.md -> AGENTS.md` and `git diff --check` passed.
- Final local rebuild: API ready and API/worker share image digest
  `sha256:7a5480e83cfb1c787552d8e4c5da8ee0c89343a5edad01879712d74feff69040`.
- Headless real `ThreadLiveEntry` with isolated HTTP fixtures: both default
  switches enabled; choices retained across a new conversation with another
  model family; zero disabled-tool commands; exact PyPSA subset on a permitted
  task; draft retained on blocked execution; empty preference saved.
- Desktop 1200×900, mobile 375×812 and landscape 812×375: compact menu stays
  within the viewport. Mobile tool rows are 44px; menu height is about 217px.

Browser artifacts: `output/playwright/global-tools-20261008/`. Test and gate
logs: `/tmp/capstone-global-tools-*.log`. The acceptance browser is closed.
Inline source review covered application ownership, exact registration,
transaction ordering, immutable Attempts, context locking and failure paths.
Independent agent review remains pending because the platform's configured
review model was unavailable in earlier attempts.
