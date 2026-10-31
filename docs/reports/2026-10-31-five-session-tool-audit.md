# Five-session tool audit

The five browser sessions have13failed tool-end events from12distinct failed
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
| 10:05:45 | `thr_77fafc46bc7ea5047007` / `attempt_23b69d02cb493a24` | Seq132: composition selected source names and rejected them. Seq158: scope resolution rejected `scope:"北京"`; request `070002ea672b4eb9babf7819295fe166`. Seq208: direct call used the correct registered directory name but that tool was absent from the active menu, returning `Tool ... not found`; this is activation state, not an alias mismatch. |
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
-33JavaScript checks pass, including actual pinned SDK parent/child execution,
  real isolated composition workers, mixed identities, grant restrictions,
  collisions, cancellation and resource-budget alias reuse.
-136focused Python checks pass;32environment-specific checks skip. Duration5.45s.
- The three original failed composition programs pass name-resolution replay
  using the current real catalog and mock responses. This proves name handling,
  not fresh business results. No business tool is called by that replay.
- Packaging copies the shared module into the native image and includes it in
  the executor revision hash.
- No CI, push, PR, merge or cloud deployment was started.

Local evidence: `runs/gateway-five-session-audit-20261031/summary.json`, each
thread's event file, and `composition-replays.json`. Historical tool/provider
names in this report describe incidents only; they are not runtime policy.
