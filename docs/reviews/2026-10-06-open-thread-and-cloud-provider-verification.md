# Direct Thread entry and cloud Provider recovery

The user requests direct workbench entry during function validation, using the
existing Provider credentials. The local App must pass before any cloud-dev
deployment. Demo promotion still requires human acceptance.

## Change

`CAPSTONE_THREAD_OPEN_ACCESS` selects anonymous Thread access. Local Compose
defaults to open mode; cloud-dev selects it explicitly. The App reads only the
mode from `/api/v1/thread-access`, creates one Thread under StrictMode and sends
no browser token in open mode. Provider secrets stay in worker environment
variables. The older scripted-demo credential retains its separate scope.

New conversation and Conversation list now sit in the shared brand header.
Their menu opens below the header. Mobile controls retain named44px buttons.
Existing new/switch/archive/restore, history, draft and reconnect paths remain.

Local real acceptance also found two PyPSA failures in the shared Thread bridge:
an unused operations Pack downgraded verified model observations, and published
guide reads lacked calculation provenance. Admission now uses participating
Packs and treats reference-free published guide reads separately. Unknown tools,
unowned references and failed participating Packs retain their rejection rules.

The Thread runtime also omitted the existing Kernel model-handoff contract.
The Application bridge now prepares typed, current-workspace receipts under
declared grants, verifies the bound model or its descendants, persists/replays
the receipts and gives Pi the private index. Target tools receive only the
granted handoff. No domain semantics or raw models were moved into the Kernel.

## Local verification

| Check | Result and receipt |
| --- | --- |
| Actual root App | Empty browser authentication enters directly at5173; `runs/thread-open-local-browser-layout.log` |
| Navigation and drafts | New/switch/reload drafts pass; `runs/thread-open-local-browser-session-result.log` |
| Archive and restore | Restored metadata is active and composer accepts input; `runs/thread-open-local-browser-archive-final.log` |
| Mobile layout |390px and320px have no horizontal overflow; both controls44px; `runs/thread-open-local-mobile.log`; inspected screenshots under `output/playwright/thread-open-local-mobile-*` |
| App tests |267 pass in full release log; TypeScript and production build pass |
| Thread admission |45 pass, including two red/green regressions and fail-closed ownership checks; `runs/thread-open-admission-green.log` |
| Real authority handoff |Base and derived PyPSA dispatch, replay and foreign-reference rejection pass; `runs/thread-open-handoff-derived.log` |
| Current backend and boundaries |489 pass,35 skip; package boundaries pass; `runs/thread-open-final-admission-gates.log` |
| PyPSA tests |39 pass; `runs/thread-open-final-pypsa-tests.log` |
| Types and doctor |Pass; `runs/thread-open-final-types-verified.log`, `runs/thread-open-doctor.log` |
| Full release |`make check-release` exits0; `runs/thread-open-local-release.log`; later bridge changes have the focused gates above |

The local catalog question and pandapower AC power flow complete in real AI
Turns. Local success is a regression result; the original missing-key fault is
cloud-only. The final rebuild and actual PyPSA recheck are still in progress.
Earlier failed local QA Turns remain in their owned histories; they are not
successful acceptance receipts.

## Cloud-dev acceptance

Pending local completion. No new cloud deployment or credential change has
occurred at this checkpoint. The planned rollout uses one exact locally verified
revision for the API, both workers and App. It sets the existing Provider key
through protected variables, then checks the actual root App and reported catalog
question in normal mode. Deployment health alone cannot accept AI conversation.

Demo remains unchanged. This record does not claim human release approval.
