# MCP self-description: enterprise and grid task trials

Date: 2026-10-27. Local authenticated MCP service: gateway 1.30.0,
protocol 2025-11-25, contract revision
`6d73ef216541b1de4c276a00ce7ade2979bdca02834decb38c67e0540e106ae1`.

## Result

The published self-description supports the tested enterprise research task and
useful grid discovery, local structure queries and evidence-limited answers.
It does not yet establish a complete grid calculation or workbench acceptance.
One synchronous readiness inspection timed out; a frozen view was still preparing
within the trial's bounded checks. No unverified calculation claim was produced.

Two fresh agent contexts received only the MCP transport interface and business
question. They did not read repository docs, source, credentials or each other's
results. The orchestrator read the handoff to set acceptance scope. Calls used a
host-controlled CLI bridge to real Streamable HTTP, preserving full MCP responses.
This tests agent use of gateway self-description, not the configured Capstone
Provider, deployed native executor or Vivaldi interaction.

## Checks and actual results

| Check | Result |
| --- | --- |
| Published interfaces | 54 tools; all 54 detailed input/output schemas match tools/list and pass JSON Schema checks. Audit took 2.398 seconds. |
| Business errors | Invalid contract selectors and foreign object identity return isError with structured Result, reason, request ID and correction guidance; no success pagination action. |
| Protocol input error | Missing required input returns isError text without structured Result. Text must be retained. |
| Enterprise task | 20 calls; compared North/East catalog structure, checked exact plant identity through two legal query combinations and identified evidence missing for September 2026 consumption analysis. |
| Grid task | 19 calls including one timeout; identified 8 busbars, 2 transformers, 3 windings of one transformer, and 14 station-associated lines at Chaoyang through source-qualified IDs. |
| Grid limits | Two lines have explicit terminal/endpoint inconsistencies. Source relationships were not treated as closed electrical paths. No AC readiness or most-loaded-line claim. |

Enterprise counts are directory records, not installed MW or verified operating
assets: primary photovoltaic records North 6,991 / East 45,534, wind 1,500 / 506,
wind-solar 157 / 6. Overlapping subtype counts were kept separate. Two sampled PV
objects had no September 2026 source series under the discovered mapping, with
missing annual table and coverage_complete=false. The monthly consumption table
was declared-only/readable=false. These are scoped negative findings, not proof
that every possible source lacks the data.

The grid agent used an alternative valid directory/relationship path after the
readiness request timed out. It did not repeat that request, build a model, run a
solver or invent parameters. Exactly two job checks were made. Preparing views,
calculation readiness, executed solves and persisted results remained distinct.

## Significant gateway feedback

One improvement merits a coordinated discussion: **long-running model inspection
needs a bounded response and a diagnosable continuation contract**. The trial's
`inspect_network_model(north, power_flow)` did not return within the 40-second
HTTP read timeout, so no business Result/request_id was received. The frozen-view
job also remained in extracting_source during the bounded trial. This does not
identify a proven gateway defect: network, source and compute time remain to be
distinguished. It does identify an interaction boundary that can block the agent.

Recommended direction: measure the expensive phase, expose a fast cached or
scoped inspection when valid, and use the existing bounded asynchronous pattern
for work that cannot finish promptly. Include job identity, progress/failure and
poll guidance; preserve model/version identities. Acceptance should demonstrate
that a cold regional inspection returns either a bounded result or a usable job
reference, without requiring repeated identical scans. Do not solve this by an
unbounded client timeout or automatic retries. This is a proposal, not a request
to rewrite every tool or proof that asynchronous internals are absent.

Minor wording/status issues are recorded in the enterprise trial only and are
deferred: a missing measurement partition requires reading coverage fields even
when status=ok; an older short description conflicts with published read-only SQL
availability. Neither blocked this trial. No sibling gateway code was changed.

## Capstone-owned integration gaps

The existing static business-name policy still excludes eight published tools,
including discover_gateway and describe_gateway_contract. The MCP client also
discards initialize instructions. These are client integration gaps, not missing
gateway self-description. Dynamic admission, initialization guidance and bounded
on-demand semantic discovery must be connected before claiming workbench support.
Do not merely add the two discovery names to another permanent business list.

The new task-scoped menu groundwork and Authority import source changes are
committed but not rebuilt/deployed. Gateway data observations do not become
registered calculation evidence without Authority admission. The actual East
demo import/solve work is separate; it cannot substitute for this North trial.

## Evidence

Local ignored evidence root: `outputs/mcp-self-discovery-20261027/` in the main
checkout. `audit/contract-audit.json`, `tool-contracts.json`, `error-contracts.json`
retain deterministic checks. `enterprise/RESULT.md` and raw JSON receipts retain
all 20 calls and request IDs. `grid/result.md`, `receipt-index.json` and
`timeout-evidence.json` retain the partial grid outcome and the failed request.
No credentials were written to these records. Complete agent transcripts and
source responses are retained locally; this report is the reviewable conclusion.
