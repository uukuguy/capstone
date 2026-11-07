# Sectioned gateway contract recheck

## Scope and source

PR98 merged normally into dev9689c434 after the single approved macOS CI
42370539679 passed in2m43s. The actual dev checkout fast-forwarded to that commit.
Root mixed changes were backed up under refs/capstone/recovery/pre-pr98-root-20261107
and the ignored pre-pr98-integration manifest. Fourteen old code patches were
proved included in the accepted tree before normalization; unrelated paths remain.
Git HTTP transport failed. The exact signed merge object was obtained through
GitHub's API and imported only after its SHA, existing parents and accepted source
tree matched. No source or commit history was fabricated or rewritten.

Local backend remains product9773fca6, with the same source code as merged dev;
App remainsdf4ddf61. No Capstone remote stage or main deployment changed.
The user reports the gateway update deployed to local,66and63. This recheck used
the 本机联调 instance; it does not independently verify66or63.

Fresh publication still has43tools, but its fingerprint changed from
d02ef76f21e5ee1c1f83c97afe15b1bf72f718df6f08961a750e394108968cb0 to
a1c0f5f1913dc6234af1a91f06f33964c320495ff82d41cb76c985bfd8a6a2fb.
Thirty-eight tools carry data-gateway/capability metadata. Contract lookup exposes
complete,usage,input_schema andoutput_schema sections. Tool counts were not used
to infer publication freshness. New task snapshots were created after selection
and refresh; old task snapshots were not modified.

## Same-task real-model comparison

Both conversations used the same two instructions and the same selected model.
Turn1 requests a saved capability-based period/change analysis plan without business
reads. Turn2 changes focus to abrupt changes and requests a revised saved plan.
Baseline Thread:thr_c4c37ecc4c5889841c93. Updated Thread:thr_0f28cd848a3088a729fe.

| Publication / turn | Contract reads | Contract JSON bytes | All gateway JSON bytes | Model responses | Seconds |
| --- | --- | ---: | ---: | ---: | ---: |
| Before /1 |29complete|633674|743593|20|121.21|
| Before /2 |2complete|41795|151711|10|117.68|
| After /1 |8usage+6input_schema|87213|352842|15|100.42|
| After /2 |17usage+5input_schema|158571|424197|11|159.57|

Counts and bytes come from task-bound persisted host observations, deduplicated by
tool_call_id. Bytes count UTF-8 text of the returned MCP JSON, including its content
and structuredContent copies; they are not compressed HTTP/SSE wire measurements.
Model response counts come from persisted response_completed events. Raw receipts,
usage counts and scripts are in root .capstone-agent/gateway-guide-20261107/.

Complete-contract reads fell31to0. Total contract bytes fell675469to245784
(63.6%). Total gateway bytes fell895304to777039(13.2%). Discovery grew from about
109.9kB to265.6kB per turn because it now carries the capability summaries.
Total time rose238.89to259.99seconds. This one paired trial does not establish
planning speedup or regression causality; the gateway's three-sample67% reduction
is a separate measurement, not an end-to-end speed result.

## Requested reasoning checks

- Both updated plans distinguish a source hour row with V00..V59 from minute_sample
  output at60seconds, and distinguish page_size from the output point count.
- The updated outputs no longer assert that unspecified two periods necessarily
  exceed a budget. They request object/metric/window inputs and state budget limits.
  The second plan labels a single-object60second sampling calculation as an explicit
  conditional estimate rather than measured cardinality.
- The results support correction of these two observed errors in this trial. They
  do not establish general business-analysis accuracy. Point-count/duration and
  relationship-evidence interpretation still need real-data evaluation.

Saved products are16007and27159bytes. API downloads match their admitted SHA256
descriptors. No business records, tests-as-production fallback, invented business
references or numerical Authority claims were used.

## Version boundary probe

Through the current Capstone adapter, a usage section returned contract revision
fec039eaf0004299c98677f181c289d0f27096a4ac4f777ef8656c8b131d9fa1.
An input_schema request with that expected_revision succeeded and returned the
same revision. Substituting the summary fingerprint was rejected with isError=true.
Capstone passed the declared values unchanged; no tool-name-based semantic routing
or business inventory was added. This verifies the adapter/server boundary, not a
claim that every model call supplied optional expected_revision.

## Remaining Capstone work

The follow-up read22sections, versus2complete contracts in the baseline follow-up.
The baseline saved a separate29-contract context artifact; the new first turn saved
only its plan. This difference is consistent with missing exact-contract carryover,
but needs a dedicated test before assigning causality. Improve bounded, versioned
capability-context reuse across instructions without treating business data or
historical sources as current Authority evidence. Do not solve this by hardcoding
tool names or requiring models to write a large contract file every turn.

Source integration and these rechecks are distinct from production numerical
execution, remote-job interruption recovery and performance acceptance, which remain open.
