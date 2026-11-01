# Summer rerun and instruction-local observation reuse

## Evidence

The user authorized one fresh rerun of the exact original summer instruction.
Thread: `thr_4201a737211f31836047`; attempt: `attempt_17c69ddab9f8b968`.
The existing browser tab was reused. Historical snapshots were not changed.
Raw records, call inputs, durations and provider diagnostics are under
`runs/summer-rerun-20261101/`.

The attempt failed after589.524s:58 model responses including three terminal error
responses,282 tool executions including227 nested calls, and8 tool errors.
First model start was1.111s after attempt start. The last model request stalled
for102s with ReadTimeout, followed by two ConnectError retries. The user confirmed
a network outage. This termination is separate from earlier planning/reuse defects.
No final PPT was delivered. Intermediate workspace files are referenced in the
saved execution record; they are not accepted final products.

The eight tool errors were: an unregistered outer composition reference; array
paging applied to a non-array field; a source-discovery sample limit; an ambiguous
data source requiring source_id; a local Python input missing next_offset; an
observation read over the byte budget; an invented truncated field; and a Python
date operation on NaT. Only the first is the outer-reference defect corrected here.
The other errors retain their exact inputs and outputs in errors.json. Do not
attribute these pre-outage failures to the network interruption.

## Why162 sequence calls were excessive

| Group | Calls |
| --- | ---: |
| 2025 daily data for35 objects | 35 |
| Exact repeat of that successful batch after incorrect local field extraction | 35 |
| 2024 daily data for35 objects | 35 |
| Another measurement expanded directly to35 objects | 35 |
| Hourly data for7 objects over two yearly windows | 14 |
| Probes, source selection and response inspection | 8 |

There were37 additional sequence calls with identical arguments, plus two other
identical discovery requests. The first35-object batch succeeded but its generated
table omitted numeric fields. The next program corrected extraction by repeating
all35 source requests. The repeated batch cost25.288s wall time; this is not a cache
fault. Other overlap cannot be merged without checking source and aggregation
semantics. A broad catalog does not establish that every object belongs in the
requested detailed comparison.

## Implemented correction

The composition executor retains an instruction-local map of exact tool identity
and canonical arguments to successful observations. Eligibility requires the
published tool to declare readOnlyHint=true and idempotentHint=true, with no
destructiveHint=true contradiction. Only status=ok observations are reused.
Unknown tool semantics, failures and partial results are not reused. The existing
task catalog and grants remain the boundary; no business tool names, identifiers,
provider names or time-field conventions enter this mechanism.

Repeated composition requests return the original ref and provenance, plus
reused=true and observed_at. They emit no new gateway invocation. Concurrent
identical requests share the first successful observation. Local transform or
export failures do not discard it. Capacity and argument preflight remain enforced.
This is reuse of an earlier observation, not a claim that current source data is
unchanged and not an Authority result.

An explicit tools.call or tools.batch option with a nonempty refresh_reason
performs a fresh read; the reason is retained in the completed-call manifest.
Failed refresh invalidates the earlier reusable entry. tools.follow always runs
the exact returned action, including waits and polling, rather than reusing it.
No source requests are combined across time windows or resolutions.

Successful programs now expose completed_calls as failures already did. Large
manifests remain available through saved-file references. Both successful and
failed composition outputs register their actual host-issued observation alias,
so callers can inspect the program result and manifest without repeating its work.
The composition wrapper is not relabelled as a business response.

## Verification and limits

The failing regression reproduced extra calls before implementation.68 focused
Node checks pass, including a35-call batch followed by local processing failure:
the corrected program makes zero new gateway calls and reuses35 original refs.
Coverage includes concurrent repeats, explicit refresh, failed refresh, failed
reads, unknown semantics, returned actions and outer native-reference manifests.

This fixes exact successful rereads inside composition. It does not certify
business scope selection, eliminate all model-generated script errors, automatically
combine daily/hourly statistics, or claim a completed full summer acceptance.
Direct model tool calls do not use this composition reuse map. Broader retrieval
still needs evidence of coverage and a stated use in the requested comparison;
no arbitrary count cap or provider-specific route is introduced.
