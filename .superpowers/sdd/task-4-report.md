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
- GREEN: focused generic tests pass (9 tests).
- GREEN: compatibility tests pass (30 tests).

## Verification

- `npm run check --prefix packages/pi-capability-tools`
- `npm test --prefix packages/pi-capability-tools` — 9 passed
- `npm run check --prefix packages/pi-grid-tools`
- `npm test --prefix packages/pi-grid-tools` — 30 passed
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
