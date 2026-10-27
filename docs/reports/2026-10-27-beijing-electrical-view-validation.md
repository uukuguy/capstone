# Beijing electrical view — local validation in progress

## Measured view loading

Measured in the existing Vivaldi workbench tab on 2026-10-27. App source
`0565f8b4`; backend image
`sha256:2bf062f3876d065e6368ed6cbaf6a5adf061ef71b1f0ea0afc1954b7f7495218`.
The browser opened the model through the model selector after an agent run failed.
These measurements do **not** establish natural-language end-to-end success.

| Measurement | Result |
| --- | --- |
| Complete overview, first drawn frame | 0.49 seconds |
| All eight detail streams committed to browser cache | 16.30 seconds |
| Overview objects / source line groups | 189 / 275 |
| Detail records, all streams | 78,407 |

Both durations start immediately before the workspace model-open request. The
overview measurement follows the renderer's first actual frame and animation
frame callback. Completion follows validated page and IndexedDB checkpoint
commits. No pause or drilldown occurred during this sample. The gateway model
was already prepared; this was the first browser download of this view in this
test. Do not include the earlier gateway preparation in these two figures.

The selection is Beijing's published `provincial` profile, minimum AC voltage
220 kV. It contains 17,256 devices, 24,828 ports, 7,671 connection nodes, 24,762
connections, 2,309 device relations, 856 groups, and 725 issues. It is **not** the
earlier 0 kV `station` capture with 219 overview objects and 472 line groups.

## Natural-language opening: first failure

New conversation `thr_615c7ad5ae762838a6eb` received the exact instruction
“打开北京电网” at 10:24:35. The agent discovered the business object and opened
its grid scope with `selection_profile: provincial`. The first open returned
`preparing`; the gateway later returned a valid ready v2 descriptor. After
approximately 101 seconds and 22 tool calls, native event transport rejected
the descriptor's `model_revision` as a protected field. The system cancelled
the native execution. The user did not stop it.

Fix `a86e65d6` permits only a validated display descriptor in its expected event
envelope. Generic protected fields remain rejected. Focused checks and replay
of the actual saved response passed. A rebuild and new visible trial are still
required. Preparing-state handoff currently uses agent polling and remains a
separate interaction gap.

## Station drilldown

In Vivaldi, search “朝阳”, select the station, and activate the existing expand
action. The child view loaded 183 devices, 275 ports and 275 source connections,
including six busbars and two transformers. This proves the data path, not
visual acceptance: the original entry was buried below details, and the
station layout is still dense. Clear primary actions and readable layout are
being corrected. Zoom alone does not load another hierarchy level.

## Acceptance still open

- Completed: new conversation `thr_072a9587b4bda536cd19`, exact input
  “打开北京电网” at 11:19:57; no resource-panel operations. The agent completed
  14 tool calls in 26.3 seconds and automatically opened “北京电网 · 厂站概览”.
  Backend image `sha256:9d69f54bdbf19620a21161a65bb76fafc32e04a00813ef0449e37bd2dc0f9a3f`;
  App `e80df08f` with subsequent breadcrumb fix. Gateway and browser cache were
  warm. Evidence: `outputs/beijing-electrical-20261027/vivaldi/natural-open-success.*`
  in the root checkout. This is successful natural-language routing, not a cold
  download benchmark. The earlier failed case remains recorded above.
- Verify a normal chat instruction while a real background download is active.
- Verify clear station entry, readable electrical detail, and hierarchy return.
- Verify refresh restoration and pause/resume in real IndexedDB.
- Resolve model names from gateway object identities, without a local ID/name table.
- Record final source, runtime identity, and integration state.
