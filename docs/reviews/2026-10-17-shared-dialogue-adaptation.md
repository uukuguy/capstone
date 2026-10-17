# Shared dialogue adaptation: verification record

Status: grid-first local trial verified at `00a8cd85`, including authorized
Provider calls. PR #53 merged into dev at `f5eda4e4` after macOS CI passed;
its merge tree equals `00a8cd85`. Full enterprise delivery is not accepted.

## Professional trial follow-up (2026-10-17 15:51 CST)

Existing pandapower IEEE39 cases are the primary acceptance scope. PyPSA has
one user sample; its repair tests do not replace IEEE39 application validation.

The original IEEE39 thread also completed line11 endpoint lookup and a line7
outage: the derived AC case converged and line11 loading was 103.33%.
The overview answer contains a transformer-count wording inconsistency.
The full extended receipt is `ieee39-extended-events.json` in the same runs directory.

The original load-scaling prompt was repeated in fresh thread
`thr_898080db6ff8aaa06fb6` at `4120e57b`. It changes the correct load from
9.2/4.6 to 11.96/5.98 MW/Mvar, compares both converged scenarios, and correctly
identifies the existing high voltage at bus name36/index35 as unchanged.
The answer still attaches the neighbouring PV generator to bus name31/index30.
This is an open professional explanation defect, not a fully passed answer.
Receipt: `ieee39-load-final-events.json`. Earlier failed receipts remain preserved.
Generic Pack guidance now covers balancing-source interpretation and name/index
identity. No fixture IDs or expected answers were added to agent or Kernel code.

The single PyPSA task was repeated in its retained thread after fixes: effective
time-series demand is reported, preparation succeeds, and fixed-capacity linear
dispatch returns an optimal result. This does not verify a standalone LPF or AC
voltage calculation. Receipt: `pypsa-final-trial-events.json`, latest attempt
`attempt_44a5cfea6bd6538d`. Earlier failed attempts remain in that receipt.

PR #54 holds these professional fixes and remains pending CI/integration.
Demand changes passed 126 PyPSA tests; recovery changes passed 11 focused tests,
including concurrent launchers, close/failure cleanup and retained evidence.
Type checks and independent reviews through6415a57d passed.
The local candidate `4120e57b7f306710d1aaf7d562c032abf0d2bd42` passed canonical
rebuild/readiness. API and both workers match all1153 managed source files and
image `sha256:067fb34e1aa580a5ebbad3f73571b9ad8221ebe5820244d7225f605be74dd35f`.
Current identity: `local-identity.json`; the earlier accepted baseline identity
is retained in `local-identity-00a8cd85.json`.

## Authorized local conversation trial

The user authorized local Provider validation on 2026-10-17. The real browser
entry completed three consecutive turns in `thr_49d8b5216e2ab2847739`:

| Turn | Outcome | Displayed duration |
| --- | --- | --- |
| Explain a rainbow in three sentences | Formal ordinary answer, no Authority result or evidence references | 4.6 s |
| Run IEEE39 power flow and rank buses/lines | Converged calculation, admitted result and evidence, result card and automatic right pane | 20.1 s |
| Recall the highest line loading without recalculation | Same line21 and73.371%, read from saved results and compared with model limits | 17.6 s |

The saved structured projection ranks lines21,11,26 first, matching the answer.
The third turn calls evidence retrieval, result ranking, model constraints and
topology endpoints; it does not call a power-flow solver. Refresh restores all
three answers and the result links without reopening the result pane. Opening
a saved result restores its table. The 1440px view has no page overflow.

Receipts: `runs/shared-dialogue-adaptation/provider-trial-receipt.json` and
`provider-trial-events.json` in the implementation worktree. Unique inspected
image: root `output/playwright/enterprise-trial-result-1440-20261017-1501.png`.
This verifies the existing grid-first shared conversation path. It does not
certify every scientific task, native model-free execution or general reports.

## Actual local entry verification

The canonical rebuild completed at `00a8cd85975107a55455cb981152d83d0a69e034`.
API and both professional workers use image
`sha256:f102e8ca316d6a4a7299d395c9748d060785c40db2cfc97e7740e48ef7a7c010`.
All 1153 managed source files match that commit in each role. Vite reports the
same clean revision. Readiness passed. The identity receipt is
`runs/shared-dialogue-adaptation/local-identity.json` in the implementation worktree.

The current App suite passed 570 tests, plus TypeScript and build checks.
The PostgreSQL-backed Work, execution, thread and research checks passed all
88 tests against a separate test database. No database tests were skipped.

Actual browser checks used existing local-dev records, without HTTP fixtures:
history restoration, mixed-version session navigation, persisted result tables,
electrical topology, draft restoration, split resizing and expanded-view return.
New conversation creation opens the mature composer with no save/start stage.
The measured 1440px page has no horizontal overflow. These read checks do not
rerun or certify the historical numerical conclusions.

The mixed-version list initially failed under the v1 reader. Commit `00a8cd85`
adds a v2 list-only retry after the explicit version error. It keeps the active
session protocol unchanged and does not replay writes or retry permission errors.
A regression test and independent review cover this correction.

The initial entry checks made no Provider calls. The later authorized trial is
recorded above. Long-running research and the separate native conversation
chain still need their own acceptance.
Cloud, demo and the delivered user package were not changed.

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

### Original PyPSA defect and its correction

On source00a8cd85, real thread `thr_2ca59c9ed9e634204467` completed model
inspection and `operations.dispatch`, including the persisted seven-line result
table. However, the answer interpreted static `p_set=0` defaults as zero operating
demand despite time-series overrides. It also conflated fixed-capacity dispatch
optimization with a power-flow check. This answer does not pass acceptance.
The original event receipt is `runs/shared-dialogue-adaptation/pypsa-provider-trial-events.json`.

The correction belongs to the PyPSA Authority and Packs: publish bounded effective
demand ranges with missing-snapshot counts, identify static defaults, and describe
the calculation actually performed. No scenario-specific agent behavior or new
solver is introduced. The actual repeat and its remaining scope are recorded above.
The separate pandapower three-turn acceptance remains valid.

- Repeat affected checks if further source corrections are made. The current
  App suite, independent review and static layout checks passed as recorded above.
- Preserve the backend changes through `a8b4e578`, already merged locally in
  `b703e37b`. Older dev Work validation cannot read current local-dev records.
- PR #53 is integrated. Complete PR #54 checks before claiming its integration.
- Keep the remaining IEEE39 explanation defect open. Model-free enterprise
  dialogue and general artifacts require their own acceptance.

The separate native backend `c9e57152` fixes the RPC parent failure caused by
oversized research excerpts. Its offline tests pass; it is not deployed or part
of this UI trial acceptance.
