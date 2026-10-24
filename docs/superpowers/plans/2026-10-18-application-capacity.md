# Application capacity implementation plan

**Goal:** Remove hidden small limits from the application execution and reading
chain. Supply ample defaults and application-initialization overrides, with
consistent client/server checks and explicit failures that preserve work.

**Architecture:** Application owns one versioned CapacityProfile. Initialization
loads defaults plus partial JSON/programmatic overrides and freezes a fingerprint.
API, worker and native executor consume it. API bootstrap publishes safe values
to the App. Domain Packs and Kernel receive neutral capacity parameters through
their existing composition contracts; they do not import application modules.
Identity formats, hashes, isolation and Authority admission remain exact.

**Acceptance:** A changed initialization value works through actual upload,
native execution, file persistence, API projection and App parsing. Large streamed
responses and outputs above old4/8MiB thresholds complete. Configured overflow
returns capacity name/configured value/actual value/unit and does not erase files.
Drafts and research records are not silently truncated. Real same-source research
and independent report checks remain required; failed runs are never speed gains.

- [ ] Central profile and strict initialization/override tests; one canonical JSON,
  immutable effective snapshot, safe public projection and startup fingerprint.
- [ ] Persistence: remove redundant task aggregate cap, apply configured file/count/
  storage budgets, retain saved descriptors and failed workspace; sweep by retention.
- [ ] Native transport/context/upload/timeout/model metadata use the initialized
  profile. Pass neutral limits into SDK/Kernel/Pack contracts and validators.
- [ ] Frontend bootstrap consumes same limits across drafts, artifacts, materials,
  products, history and result parsing; clear capacity errors replace silent loss.
- [ ] Complete the file:line audit with coverage/status for remaining capacity
  guards, including existing configurable ones and external SDK defaults.
- [ ] Focused boundary/override/retention tests, relevant regression suites, normative
  local rebuild, actual browser upload/research/download/number checks.
- [ ] Record implemented/verified/merged/deployed separately in canonical control;
  no cloud/demo promotion or dev merge claimed without their own gates.

The current original research continuation reached model completion but failed
at persistence485.115s/71responses because of the old8MiB aggregate product cap.
Its history remains failed. The next actual run starts only after capacity wiring
passes checks and the local entrypoint has been rebuilt.
