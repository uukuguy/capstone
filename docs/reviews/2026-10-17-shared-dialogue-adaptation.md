# Shared dialogue adaptation: verification record

Status: implementation in progress. No deployment or delivery acceptance.

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

- Complete final App tests and independent review after the latest changes.
- Check actual layouts at 1440, 1280 and 390 pixels, with wider-window adaptation.
- Integrate the already verified backend changes through `a8b4e578` before a local
  rebuild. Older dev Work validation cannot read the current local-dev records.
- Rebuild the exact candidate and verify API, worker and Vite source identities.
- Verify the actual local entry point. Scripted CLI runs alone do not establish
  end-to-end application acceptance.

The separate native conversation backend remains paused with an unresolved
parent Harness failure in the real RPC test. It is not part of this UI acceptance.
