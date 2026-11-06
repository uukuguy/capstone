# Direct native entry verification

Runtime source: `367374aa8184154528e9aacb50cb7248cb5a6d3f`.
Recovery: `refs/capstone/fixes/direct-native-entry-20261105`, parent3a8eaf76.
Intranet configuration: `255c8855b2424428c9f295bb1d4a2b51ec744628`,
`refs/capstone/fixes/intranet-tool-origins-20261105`. This changes the Compose
overlay, not runtime package source or App source. Both identities stay distinct.

## Behavior

New default native conversations freeze admitted context and enter the execution
model directly. They do not initialize or invoke an independent recognition model.
The model can answer or select authorized skills, MCP and Domain Pack tools.
Local context preparation does not generate a fake understanding LLM trace.
Existing accepted decisions remain recoverable; an old input without a decision
can load the old recognizer lazily. Explicit professional entry points retain
their contracts. Permissions, ownership, tool schemas and evidence checks remain.

The direct path now freezes the admitted application catalog. An actual schema2
executor request receives the correct Domain Pack grant, including on retry.
Historical result/evidence references are not implicitly imported. Existing skill
summaries, gateway instructions/discovery and domain tool contracts are reused.
Only the missing unavailable-pack status is added; full descriptions are not
copied into a second catalog. Generic gateway discovery bypasses the old static
catalog_lookup model-table shortcut on this new default path.

## Focused checks and build

314 checks passed,33 skipped in17.01s. New regressions were observed failing
before implementation. Independent review passed after the professional catalog
grant correction.22 deployment checks passed in1.62s, including actual Compose
resolution for empty default and explicit professional origins. No CI was started.
Canonical local rebuild completed.1787 package/config source files match the
runtime archive. App TypeScript/Vite checks passed for all three stage builds.
The normal Git index and unrelated work were preserved by scoped temporary indexes.

## Real model checks

Local ordinary attempt `attempt_cbacee44ed23fe9d`, dsv4:
answer你好;9.5574s total;first preview6.1139s;one execution LLM;no tool call;
zero intent_started and zero understanding label.16 preview batches and2 durable
Thinking events. Real browser observed visible text growth and refresh restoration.

Local professional attempt `attempt_772cda0c715e63b3`, thread
`thr_d12364943225fdad09cd`, successfully called
grid_model_list, grid_environment_describe, grid_context_open,
grid_model_constraints_describe and grid_evidence_get, plus bash to save a JSON
product. The UI showed the saved ieee39_overview.json. It exceeded the180s trial
budget while continuing model output; the agent stopped its own trial. This proves
professional tool access and product publication, not complete answer acceptance
or acceptable performance. No user task was stopped and no repeat benchmark ran.

63 original question: currently available gateway tools. Attempt
`attempt_80e7f12b66fc1458` completed in96.3927s. It made a real
data_gateway_discover_gateway call (334ms), with two execution LLM rounds and no
independent recognition. The answer describes gateway entry tools and the returned
provider/verification state, rather than the81-model table. This accepts entry-level
gateway discovery, not exhaustive underlying business service coverage.
26 preview batches/7 durable Thinking events; browser observed26 visible changes;
refresh restores370 characters and the gateway answer without a model table.

That63 run also exposed18.2904s of pre-model connection delay: the intranet overlay
disabled optional professional workers but retained their root Compose origins.
The configuration fix defaults those connections to empty. Explicitly configured
professional worker origins remain supported. Root local Compose is unchanged.
The overlay correction is applied on63 and66. Only general-pi was recreated;
effective origins are empty. API/worker/App containers, all runtime images,
private environment values and gateway files are unchanged. Protected stage-local
backups include the prior overlay and ledger. Local professional origins remain.

Post-fix63 attempt `attempt_1c777f19549e21c8` completed the short ordinary greeting
in8.0752s,first preview6.1726s;one execution LLM and no tools or recognition.
Observed native preparation fell from18.2904s to1.7879s. This is a phase measurement
across these trials, not a universal response-time promise. Browser observed live
Thinking;8 preview batches/2 durable events and refresh restoration passed.

## Deployment and evidence

All three runtime stages use367374aa. API and workers within each stage use the
same backend image; native and App full revisions match. Both intranet defaults
remain dsv4:18804 with reasoning capability. Local default remains unchanged.
Protected backups and fresh idle guards precede activation; gateway credentials
and user data remain stage-local. No user tasks were cancelled.

Exact image identities are in `../status/VERSION-CONTROL.md`.
Raw receipts: `.capstone-agent/direct-native-20261105/` (ignored).
Runtime screenshots: `output/playwright/direct-native-*.png` (ignored).
Runtime source is deployed from a recovery ref; it is not yet integrated into dev.
Simple conversation timing is a measured sample, not a general latency guarantee.
