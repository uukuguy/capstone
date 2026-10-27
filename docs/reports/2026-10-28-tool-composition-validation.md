# Shared tool composition: local validation

Date: 2026-10-28. Scope: enterprise lightweight execution and DR workers.
No changes were made in the sibling data-gateway repository.

## Implemented behavior

`agent_tools_execute` runs an async program in a separate process under the
existing task UID. It supports parallel and dependent admitted gateway calls,
Python calculations, and saved semantic packages. The worker inherits a small
environment allowlist. Gateway endpoints and grants stay in the SDK parent.
Every nested invocation keeps its own call ID, host schema check, receipt and
execution event. DR organizers retain their organization-only grant.

Packages use `capstone-semantic-data/1`. Actual issued refs and JSON pointers
produce observed fields. Literals remain declared. Missing optional binding
fields remain unknown with source gaps. Unissued refs, altered hashes and
unadmitted paths are rejected. Packages are source observations, never Authority
evidence. Separate DR nodes receive packages through existing typed artifact
inputs. Normal continuations can load only their exact admitted inputs.

Large program returns spill to files before both model and host transport.
Parallel saves use unique package paths and serialize atomic manifest updates.
The original primary product and every support package remain registered.

## Focused checks and independent review

- 60 Node checks cover real worker execution, call overlap/dependencies, budgets,
  credentials, cancellation, actual Python descendant termination, output spill,
  session refs, package hashes, source gaps, input grants, SDK discovery and graph
  consumers. Duration is about one second on this Mac.
- 133 affected Python checks passed in 4.54s; 16 historical version combinations
  were skipped. This includes 89 host checks, 43 harness checks and the real
  Node worker/package regression runner.
- File-scoped Pyright: zero errors after reproducing and fixing the provider
  status narrowing error found by PR71 CI40572210058 (failed after 2m37s).
- App type check, `git diff --check` and doctor passed.
- Independent review reproduced concurrent manifest loss. The fix retains a
  primary product plus eight same-name concurrent packages. The reviewer
  confirmed that the Important finding was resolved; no further Important
  finding was reported in the reviewed scope.

## Real Vivaldi tasks

All tasks were submitted through the existing Vivaldi Capstone tab. Each initial
task used a new conversation; no browser tabs were added. The two lightweight
instructions had identical SHA256
`682e93e37f77d7accd301d207a86c36b1f011ce7c157e3be36f4ec69d6907c50`.

| Case | Source | Time | Model responses | Programs | Gateway calls |
| --- | --- | ---: | ---: | ---: | ---: |
| Beijing June15–21 load/weather, initial feature | 7229b0b7 | 176.61s | 34 | 25 | 66 |
| Same instruction, output/ref corrections | cabf52cc | 225.88s | 31 | 12 | 61 |
| DR metadata preparation → dependent HTML report | 3d0089b4 | 231.15s | 4 parent +47 child | 6 | 23 |
| Follow-up: load and inspect the delivered package | 184a519e | 24.20s | 7 | 3 | 0 |

Lightweight threads: `thr_c2015dde0ef738d7cf3c` /
`attempt_afa41de54edc8467`, then `thr_9c239c92f808e3fc36e2` /
`attempt_cd28a9346ee05450`. Both delivered real-data HTML and support products.
Programs contained up to seven and eight gateway invocations respectively, with
individual receipts/events retained. The first run exposed return-budget and
cross-program ref defects, fixed in 6627764f/cabf52cc.

DR thread: `thr_34ff2d501486e586ed3b`, attempt
`attempt_707cc115863184bf`. Producer `prep_package` used real composition calls
and saved the canonical package. Consumer `brief_report` received the frozen
file and generated HTML with **zero gateway calls**. It read the package with
native code; it did not use the requested loadContext helper in that node.
The following ordinary instruction (`attempt_8748d218bf6772c0`) did call
loadContext three times and made zero gateway calls. It returned the Beijing
identity, 43 metrics, load-proxy metric ID and unit from the delivered package.
The next-instruction DR control was off, as required.

Downloaded canonical package `bcdb53e45d5c0758-context.json` was 79,999 bytes;
the API artifact SHA256 and package/source digests passed. Normal artifact
renaming did not break references. It contains observed object identity,
definition revision, metric refs, coverage windows and the 43-item dataset.
The HTML product was 25,687 bytes. Browser rendering and recorded UI states are
retained with the trial evidence.

Actual DR tool time occupied 8.47s of the 231.15s task; summed parent/child model
response time was about 223.72s. Native script repairs and optional-field probes
remain visible in the trace. The latter caused repeated source calls, so
184a519e records missing optional binding fields as unknown instead of rejecting
the usable package. Forged source refs still fail.

These tasks verify composition and explicit data reuse. They do **not** establish
an overall speed improvement. The two lightweight runs chose different queries
and had different native script repairs; the DR instruction was a smaller
metadata task, not the full earlier summer PPT comparison. A matched full-task
performance comparison remains a separate measurement.

Raw local evidence: ignored `runs/tool-composition-20261028/`, with initial,
final-lightweight, dr and dr-and-continuation events, attempts, summaries,
per-call CSV, program intervals and downloaded artifact hashes. The previous
[full summer comparison](2026-10-27-summer-lightweight-dr-comparison.md) remains
unchanged.

## Integration boundary

Implementation commits: 7229b0b7, 6627764f, cabf52cc, 3d0089b4, 184a519e,
and e2abb75b (type fix and regression registration).
Latest functional local rebuild was 184a519e, backend image
`sha256:921826ad1faa7cf7e1dac1866111bea86b04c0ea7a94ee91b69d7107fc305863`.
API and workers passed readiness and image consistency checks. Scoped cache
maintenance receipt: `.capstone-agent/cache-maintenance-20261028-035708-79790.log`.
PR71 targets dev; required CI, actual dev integration and its final entry-point
check are tracked separately. Cloud-dev, demo and main have not been updated.
