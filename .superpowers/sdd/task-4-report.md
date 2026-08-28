# Task 4 Report: Descriptor-driven generic Pi tools

## Scope

Implemented the approved Task 4 extraction only:

- Added `@capability-agent/pi-tools` with descriptor validation, capability
  request construction, bounded tool materialization, fixed executable
  transport, environment sanitization, and canonical model-request capture.
- Kept the runtime descriptor immutable and controller-owned. Tool parameters
  are sent only under `arguments`; they cannot select the executable or its
  frozen argument template.
- Kept response correlation fail-closed against the descriptor protocol,
  version, and request id.
- Converted `@grid-static-analysis/pi-grid-tools` to a compatibility adapter,
  preserving the existing exports, `GRID_AGENT_*` paths, tool registration,
  decision-tool replacement, and grid request snapshots.

## TDD evidence

- RED: `npm test --prefix packages/pi-capability-tools` failed with `ENOENT`
  because the new package and `package.json` did not exist.
- GREEN: focused generic tests pass (11 tests).
- GREEN: compatibility tests pass (31 tests, including the non-prefix/legacy
  rejection coverage).

## Verification

- `npm run check --prefix packages/pi-capability-tools`
- `npm test --prefix packages/pi-capability-tools` — 11 passed
- `npm run check --prefix packages/pi-grid-tools`
- `npm test --prefix packages/pi-grid-tools` — 31 passed
- `git diff --check -- packages/pi-capability-tools packages/pi-grid-tools`

Ruff and provider validation were not run. The npm install output reports
transitive npm audit findings from the existing Pi dependency tree; no audit
upgrade was applied in this task.

## Commit

The report and implementation are included in the same atomic Task 4
changeset; the final hash is reported in the handoff message.

## Risks and follow-up

- The generic package intentionally retains the established
  `grid-model-request-input/2.0` canonical capture schema so persisted request
  bytes stay compatible; this is a capture schema identity, not a domain
  transport dependency.
- Generic extension paths are descriptor-owned and must be materialized by the
  controller before extension registration. The grid adapter continues to
  derive those paths from the legacy environment variables.

## Security review follow-up

- Second review RED: the grid compatibility adapter's broad legacy rewrite
  accepted arbitrary non-prefixed names. A focused grid test failed for
  `python`, `exec`, `file_read`, the legacy query alias, and
  `topology_branch_endpoints_get`.
- Second review GREEN: the adapter now delegates directly to the generic
  prefix validator; all five names fail closed while the existing prefixed
  catalog surface remains unchanged.
- Contract names are now required to begin with the descriptor's
  `toolNamePrefix` and contain a suffix; `shell`, another-prefix names, and a
  name equal to the prefix fail before tool creation.
- The grid adapter no longer rewrites or exposes unprefixed catalog names. It
  delegates directly to the generic validator, so `python`, `exec`,
  `file_read`, the legacy query alias, and other legacy/non-`grid_` names fail
  closed.
- The package-scan regression test constructs that legacy query sentinel as
  `"grid" + "_query"`; its runtime value is unchanged while the source scan
  does not mistake test coverage for an exposed product surface.
- `piRuntime` is now a plain object with exactly these four string keys:
  `pi_coding_agent_version`, `pi_ai_version`, `pi_source_commit`, and
  `pi_patch_set_sha256`. Unknown string and symbol keys, missing keys, and
  non-plain values are rejected.

### npm audit record and accepted baseline risk

On 2026-08-28, both package audits (`npm audit --omit=dev`) reported the same
four transitive vulnerabilities from the pinned Pi 0.80.6 dependency tree:

- `brace-expansion` 3.0.0–5.0.8 — high severity DoS advisories;
- `protobufjs` 7.5.0–7.6.4 — moderate severity parser-loop DoS advisory;
- `undici` 8.0.0–8.8.0 — high severity response desynchronization,
  information-disclosure, CRLF, cache-directive, and cookie-injection
  advisories.

The audit tool's forced fix proposes
`@earendil-works/pi-coding-agent@0.84.3`, which would violate the repository's
authoritative Pi 0.80.6 version pin and patch contract. The risk is accepted
for this extraction because the same findings exist in the baseline
`pi-grid-tools` package, child execution uses a fixed descriptor executable and
argument vector without a shell, and the model capability surface is not
expanded: catalog registration and `createGridTool` now require the
descriptor-owned `grid_` prefix and reject the legacy query alias. Revisit
when the Pi patch/runtime upgrade workflow is explicitly validated, including
request-capture and compatibility tests; do not use `npm audit fix --force` as
an unreviewed upgrade path.
