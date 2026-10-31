# Five-session tool audit

The five browser sessions have 13 failed tool-end events from 12 distinct failed
operations. One nested failure appears at both the child and composition level.
All five attempts ended with status `completed`; that status does not certify
each intermediate call or the CSV contents. This audit reads existing records
and saved gateway observations. It does not rerun those five business requests.

## Per-session findings

| Local start | Thread / attempt | Failure and evidence |
| --- | --- | --- |
| 09:46:47 | `thr_2a8c6144e693917d8410` / `attempt_a0cafca03506c6b9` | Seq98: loader rejected three source names. This run predates the09:58 loader deployment. Seq268: directory query used an unknown business scope; gateway gap `invalid_arguments`, request `03877034269e4cc9907c741057a8cb9b`. Old input projection recorded `{}`, so the exact directory arguments are not claimed. |
| 10:03:38 | `thr_7838e98121b8943c6314` / `attempt_38d290538aadfa2d` | Seq92: `resolve_region_scope({scope:"北京"})` is outside the published business scope definitions; request `917f203884534fe7981789f8c4cdb244`. Seq153: temporary Python iterated `for k in data` but read `v`, which was not defined in that scope: `NameError`. |
| 10:04:55 | `thr_3f7f605a9f0b6e39aa3b` / `attempt_1458de7fe6113c4c` | Seq20: contract lookup supplied `operation:"discover"`; gateway returned `Unknown operation`. Seq77: composition selected three source names and rejected them before any call. Seq93: corrected composition reached scope resolution, which rejected `scope:"北京"`; request `33aba9064496436f9f8d898a1059b78b`. |
| 10:05:45 | `thr_77fafc46bc7ea5047007` / `attempt_23b69d02cb493a24` | Seq132: composition selected source names and rejected them. Seq158: scope resolution rejected `scope:"北京"`; request `070002ea672b4eb9babf7819295fe166`. Seq208: direct directory call returned `Tool ... not found`. Seq180 had replaced the active menu with scope discovery and region membership tools. Seq218 reloaded the directory tool; Seq226 called it successfully. This is activation state, not an alias mismatch. |
| 10:06:51 | `thr_f27049daaaefe431e8d6` / `attempt_6e7c600b220d7311` | Seq98: composition selected source name `find_business_objects` and rejected it. Seq148–149: directory call wrapped the grid reference as `scope:{object_ref:{...}}`; the exact schema requires scope values to be strings, so this nested shape failed validation. Child and parent recorded the same failure. |

The common name defect remained in composition after the earlier loader repair.
These records confirm that the previous repair was incomplete. Four naming
failures appear across the sessions: one historical loader failure and three
composition failures. Other failures concern business parameters, activation
state, a contract operation value, or generated Python code.

## Shared correction

`resources/tool-identity.mjs` now owns the neutral identity index and resolution
function. Loader, composition selection, program call dispatch and program
contract lookup import it. It derives source and registration identities from
the current admitted publication; it contains no business/provider names or
namespace slicing. Both the parent process and isolated program worker enforce
the selected scope. Composition receives the actual session-admitted names from
the SDK, so a publication entry alone cannot broaden the grant.

Aliases share the same call budget, resource-failure limit and receipt identity.
Unknown and ambiguous names fail before dispatch. The agreed gateway contract
lookup parameter conversion remains within the MCP adapter; it uses the same
published source identities and introduces no business aliases.

Invalid business scopes and malformed arguments remain errors. The runtime must
not guess a scope, unwrap arbitrary business objects, silently activate an
unselected tool, or reinterpret an unsupported operation to hide those errors.

## Verification

- New composition regressions failed on the original code and pass with the
  shared resolver.
- 33 JavaScript checks pass, including actual pinned SDK parent/child execution,
  real isolated composition workers, mixed identities, grant restrictions,
  collisions, cancellation and resource-budget alias reuse.
- 136 focused Python checks pass; 32 environment-specific checks skip. Duration: 5.45s.
- The three original failed composition programs pass name-resolution replay
  using the current real catalog and mock responses. This proves name handling,
  not fresh business results. No business tool is called by that replay.
- Packaging copies the shared module into the native image and includes it in
  the executor revision hash.
- No CI, push, PR, merge or cloud deployment was started.

Local evidence: `runs/gateway-five-session-audit-20261031/summary.json`, each
thread's event file, and `composition-replays.json`. Historical tool/provider
names in this report describe incidents only; they are not runtime policy.

## Rebuilt runtime and browser check

The canonical local rebuild passed, including scoped cache maintenance. A real
isolated program worker in the rebuilt image resolved source names for both
selection and contract lookup, then dispatched a registered-name call to a mock
source. This checks image packaging and process wiring without querying business
data.

The visible browser then submitted the unchanged CSV question in a new thread:
`thr_92b158ca824ba8f1d6fe` / `attempt_3381beb95896818a`. It completed in 36.7s,
with 16 model responses and 18 tool calls. Source-name activation succeeded.
There were no name-resolution errors. The model used direct gateway tools in
this browser run; composition coverage comes from the worker checks and original
program replays above.

One business failure remains: `resolve_region_scope` rejected `scope="北京"`,
request `160dc47c1c2446df96770367abfe8722`. The model recovered through grid object
lookup and saved `beijing_substations.csv`. The GUI download has exactly five
rows; SHA-256: `5c5ace366953ae14cb82d2fcac208e95d93e422a4de0ac2a3a0473e2f0b9f5f1`.
The original five sessions were preserved.

Evidence: `browser-shared-resolver.json`, `browser-shared-resolver.png`, and
`browser-download.csv` under the same ignored audit directory.

## Concrete gateway contract improvement request

For instance `3db5bb96-2c27-4d97-8584-346bc4a18656` at
`http://127.0.0.1:18001/mcp`, the published scope parameter is only a string.
The business question concerns the Beijing grid directory, while the region
resolver accepts a different, finite set of business scope definitions. Publish
the actual accepted scope IDs and aliases as an input-schema enum, generated by
the provider from its current definitions. Similarly, publish the accepted
contract-query operation values as an enum rather than an unrestricted string.

Examples: `scope="北京"` produced the request above; `operation="discover"`
produced `Unknown operation` in the10:04:55 session. These examples illustrate
contract precision, not a request to add Beijing-specific behavior. Capstone
must not maintain a business value list or guess an alternate scope. Its existing
generic schema validation can enforce values once the gateway publishes them.
This is an improvement request; the business task can currently complete via
the existing object-directory route. No gateway change is claimed in this audit.
