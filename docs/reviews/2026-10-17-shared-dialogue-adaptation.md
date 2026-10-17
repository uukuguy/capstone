# Shared dialogue adaptation: verification record

Status: implementation in progress. No deployment or delivery acceptance.

## Design alignment checkpoint

The layout in `8685d46b` was rejected. Passing component tests does not establish
prototype alignment. The current correction follows the accepted prototype's
full-height brand navigation, workspace top bar, task heading and result area.
It preserves the mature conversation and execution components.

Local merge `b703e37b` retains the professional Work backend from `a8b4e578`.
The merge baseline passed 565 App tests, TypeScript checks and the App build.
Focused backend checks passed 49 tests; 14 database-dependent tests were skipped.
These results do not cover the new layout changes or establish local deployment
acceptance. See the [architecture and function review](2026-10-17-enterprise-design-alignment.md)
for reused assets, temporary differences and remaining contracts.

An independent source review of `b703e37b` found no new actionable backend
regression in exact v1/v2 retries, Work/Attempt cancellation ownership, terminal
races, lease checks or professional history isolation. This review did not run
tests and excluded native WIP. The recovery-only UI start action remains a
separate entry-point correction in the current UI slice.

Previously delivered mutable screenshot paths are invalid evidence. The distinct
`enterprise-dialogue-1440-20261017-0349-verified.png` and topology counterpart
were checked for rendering errors, but show the rejected layout. Future visual
checks use unique filenames and compare equivalent conversation/result states.

## Original professional cases

On macOS, the five existing registered scripted cases passed against backend
source `45913f1cd71a39b6f160305d0da02081b1e2b1c0`. Each case produced three answers,
a report reference and completed domain statuses. No Provider calls were made.
These runs used real registered Authority calculations with deterministic task
selection. They do not verify free-form model reasoning or browser interaction.

| Case | Run |
| --- | --- |
| pandapower-scripted-task | run-3896d229538d844e8b30db32 |
| pandapower-scripted-test | run-4ffffde61014584c63ed8851 |
| pypsa-regional-demo | run-ed303e4e5a6a9f7528485436 |
| pypsa-scigrid-demo | run-98ad7533cd4c47990043b05b |
| pypsa-ac-dc-demo | run-bef6fd149f7fccea08a9c467 |

Local receipt: `.worktrees/model-decision/runs/shared-dialogue-adaptation/original-cases.json`.
Run artifacts remain in that worktree's ignored `runs/capstone-agent/` directory.
The receipt records report digests and domain statuses. PyPSA used the existing
pinned model library. No authentication files or user data were copied.

## UI acceptance scope

### Corrected source: `6f1c3412`

The shared shell now follows the accepted prototype hierarchy. The existing
conversation, transport, composer, topology and result viewers remain in use.
Recovery mode rejects new starts but retains exact retries and stopping the
current matching execution. Independent review found two expanded-view issues;
both were fixed and reviewed again. Closing an expanded result restores chat.
The settings shortcut is hidden while its conversation container is hidden.

Verification: 569 App tests passed; TypeScript/build and diff checks passed.
Static-build browser checks covered 1440, 1280, 390 and 1920 pixel viewports,
keyboard split resizing, preference retention, expansion/close/reopen and mobile
return to chat. The inspected chat body remains 11px. No page overflow occurred
in the measured desktop views. These checks do not establish live API execution.

Unique inspected images under root `output/playwright/`:

- `enterprise-prototype-empty-1440-20261017-0412.png`
- `enterprise-prototype-topology-1440-20261017-0413.png`
- `enterprise-prototype-topology-1280-20261017-0414.png`
- `enterprise-prototype-topology-390-20261017-0415.png`
- `enterprise-prototype-conversation-result-1440-20261017-0417.png`

The last image uses explicitly labelled offline HTTP fixture messages/results in
the real application entry. It has no Provider or numerical-validation claim.
Optional unprovided resources return 404 and the finite fixture stream reconnects;
the visible reconnect notice is retained. No report or document viewer is faked.

Use the mature dialogue components, input controls and execution process.
The standard viewport width is 1440 CSS pixels. Preserve existing font sizes
and line heights. Verify the adjustable conversation/result split, saved width
preference, expanded result view, history restoration and keyboard focus.

Only a newly received, persisted result for the current attempt may trigger the
first automatic result view. Restored history and later updates must not steal
the user's reading position. Professional evidence keeps its accurate name.
The label “引用资料” applies to actual reference material, not all tool records.

The current public Thread contract supports result projections. It does not yet
provide a general document artifact identity, revision, preview and download
contract. Existing session reports must not stand in for current Thread artifacts.

## Remaining verification

- Repeat affected checks if further source corrections are made. The current
  App suite, independent review and static layout checks passed as recorded above.
- Preserve the backend changes through `a8b4e578`, already merged locally in
  `b703e37b`. Older dev Work validation cannot read current local-dev records.
- Rebuild the exact candidate and verify API, worker and Vite source identities.
- Verify the actual local entry point. Scripted CLI runs alone do not establish
  end-to-end application acceptance.

The separate native conversation backend remains paused with an unresolved
parent Harness failure in the real RPC test. It is not part of this UI acceptance.
