# Published electrical-view integration

Status: active local integration, 2026-10-26. Source display and calculation acceptance are separate.

## Verified local boundary

Local gateway release20261026-05 publishes52tools, including electrical discovery,
open, read and preparation jobs. Capstone's protected discovery returned7model
references. The first protected discovery took2.664seconds.

Canonical local rebuild completed successfully with backend image
`sha256:5be84475ac02959307ed662250a9a403bd80bfa0c48c74733edaa46149476816`.
API and workers share that image. The build includes backend changes through
83827d03. Later changes are frontend/documentation only. Scoped cache maintenance
receipt is under the active worktree's `.capstone-agent/cache-maintenance-20261026-225331-39460.log`.
Cloud, demo and main were not changed.

Protected API evidence is saved in ignored
`outputs/electrical-integration-20261026/` in the root checkout. The acceptance
script used fixed local routes and protected credentials without printing them.

| Check | North: 神二 | East: 怀洪变电所 |
| --- | --- | --- |
| Directory total | 27075 | 75013 |
| Directory read | Two pages of200, no duplicate identities | Two pages of200, no duplicate identities |
| Devices / ports / connection nodes | 188 /186 /75 | 72 /104 /36 |
| Actual connections / composition relations | 180 /26 | 104 /14 |
| Groups / boundaries / issues | 6 /10 /98 | 3 /4 /0 |
| Frozen child reopen | Exact same view reference | Exact same view reference |
| Complete probe elapsed | 14.929seconds | 15.795seconds |

Every stream page was checked against the opened model, revision, selection,
snapshot, view reference and declared stream count. The elapsed times include
directory pages, child opening, eight independent streams and frozen reopening;
they are not single-call or model-response latency claims.

## Visible verification and remaining display work

The existing Vivaldi workbench tab loaded the North directory and 神二 station.
The new scene preserves449objects and372display edges, including180real source
connections. Composition and port ownership edges remain nonconducting.
Diagram labels hide technical IDs; details and search retain them.

Live inspection found that equal-area component packing squeezes the connected
component into a small corner while isolated switches occupy most of the canvas.
This is a Capstone layout defect, not missing gateway connectivity. Its correction
and final two-model visual acceptance remain pending. Do not call the current
layout accepted based only on passing parser tests.

## Gateway feedback to retain

- 神二 contains98reported issues and10boundaries. Keep their identities and
  source explanations when assessing connection gaps; do not draw substitute wires.
- The first nonempty North directory entry, 神头一厂, contains10devices, zero
  ports/connections and7issues. This is a valid structural response with incomplete
  connectivity, not a calculated electrical model.
- Root directories contain many zero-member station records. A future bounded
  server-side station-name search or nonempty-group selection would reduce manual
  paging. No unsupported filter is sent by Capstone now.
- Cold preparation is asynchronous. Capstone offers explicit progress checks
  and does not restart preparation in an unbounded retry loop.

## Calculation mapping is incomplete

The pure client parser/binder requires exact element table and typed original key,
matching model/artifact/revision/engine/scenario and admitted result identity.
Missing, ambiguous and nonconverged mappings are explicit. Tests do not substitute
for actual Authority calculation evidence.

Current pandapower Authority has no gateway-bundle import operation. The actual
East demo bundle was generated and mapped by the gateway, but has no solve evidence.
The proposed next unit is the
[Authority admission design](../superpowers/specs/2026-10-26-gateway-authority-admission-design.md).
Do not run arbitrary native-executor Python and label it an Authority calculation.
