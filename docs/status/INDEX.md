# docs/status INDEX

## Active

| File | Purpose |
| --- | --- |
| `CURRENT-STATE.md` | Structural project snapshot. |
| `JOURNAL.md` | Append-only durable event log. |
| `RESUME-NEXT-SESSION.md` | Current recovery baton. |
| `INDEX.md` | This discovery index. |
| `DECISIONS.md` | Active architectural decision ledger. |
| `climb/research-tree.md` | Generated Workstream B package extraction hypothesis and 100/100 scoring summary; resume-load. |
| `climb/session-state.json` | Active Workstream B Climb completion state and integration-review next action. |

## Climb storage and configuration

| Path | Purpose |
| --- | --- |
| `climb/config.yaml` | Workstream B package extraction climb adapter configuration, including receipt-backed app/dist gates. |
| `climb/session-target.md` | Machine-readable 100% Workstream B package extraction target. |
| `climb/hypotheses.yaml` | Append-only package extraction hypothesis state. |
| `climb/runs.csv` | Append-only local package extraction score ledger. |
| `climb/calibration.json` | Local/online calibration state. |
| `climb/pending-lb.json` | Pending external score state; empty for local-gate mode. |
| `climb/adjudicator-log.md` | Append-only hypothesis decision record. |
| `climb/research-tree.json` | Machine-readable generated research tree. |
| `climb/_archive/2026-08-18-full-capability/` | Completed 2026-08-18 full-capability climb session snapshot. |
