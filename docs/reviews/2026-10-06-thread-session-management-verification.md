# Thread management and recovery verification

## Candidate and behavior

Backend catalog/archive/history is committed in `508a44d`. App session controls,
draft and unresolved-command recovery, automatic reconnection and bounded history
are committed in `a2dbb5d6e54be57090010e5eb60d80358a8f8075`.

The App exposes New conversation and Conversation list. Users can switch,
archive and restore Threads. Archive retains all events and evidence and rejects
active work. Drafts and one unresolved exact command stay in sessionStorage,
scoped by API origin, authentication session and Thread. Temporary transport
failure retries at capped intervals; interrupted AI execution needs explicit retry.

Initial history reads the latest reverse page. Older messages are available by
button, with at most 50 rendered messages and a 1024-event/8 MiB event cache.
Current network state uses bounded source events from the same Model Context and
Attempt. History paging does not change current-run evidence admission or Kernel
model context. Hidden pages close subscriptions; idle API polls back off to 2 seconds.
Thread records do not reserve workers. Attempt leases control active execution.

## Local evidence

The user required local App acceptance before any new cloud-dev deployment.
The required rebuild passed and all three roles share image
`sha256:dcb71ae91eff67e66a00f178e31ae2bef8b4bddf446bf00853e09a9ed7990311`.
Hashes match the checked-in API, Thread service and management helper.

| Check | Evidence |
| --- | --- |
| App tests and TypeScript | 266 tests pass; `runs/thread-session-app-tests.log` |
| Backend/API and type checks |Focused tests and pyright pass; `runs/thread-session-backend-tests.log` |
| Disposable PostgreSQL | 21 tests pass; `runs/thread-session-postgres-tests.log`; no operator ledger used |
| Rebuild and source identity |`runs/thread-session-local-rebuild.log`, `runs/thread-session-local-source.json` |
| App production build |Pass; `runs/thread-session-app-build.log` |
| Actual browser |`runs/thread-session-local-browser-acceptance.json` and browser command receipts |
| Full release gates | Pass, exit 0; `runs/thread-session-release.log`, `runs/thread-session-local-acceptance.json` |

The actual browser uses the rebuilt API on 8767, current App source on temporary
Vite 18782 and a loopback proxy on 18781. The proxy retains the local operator
secret in memory, limits writes to task-owned Threads and rejects Provider
instructions. Seventy QA-only text Turns are generated through the durable
service, with workers briefly paused and restarted. They make no numerical claim
and contain no result or evidence references. Task Thread
`thr_18fa231adf6060534f92` retains 210 events after API restart; a second Thread is
`thr_8d0c800e74b0e98d165e`. Existing operator Threads are not modified.

Actual browser checks pass for new/switch, separate drafts, page-refresh drafts,
API restart automatic recovery, archive/read-only/restore, all 70 history Turns,
50-message windows, returning to the latest message and 390px layout with no
horizontal overflow. Screenshots were inspected under
`output/playwright/thread-session-local-*`. The temporary browser, proxy and Vite
are closed; the normal local App and Compose services remain available.
Both task-owned QA Threads are archived after acceptance, with their histories
retained, so the normal recent-conversation list stays clear.

## Cloud acceptance

Full local gates passed before deployment preparation. The target is only Railway cloud-dev project
`5eecde6b-fec2-40d2-8b26-427025b02b96`, environment
`5afd6aeb-07a6-4320-92e9-4bf193a442cb`. The deployment helper requires a passing
local acceptance receipt for the exact source above. Existing Harness deployment
receipts remain intact. No demo deployment is authorized by this record.

All four services deploy successfully in normal mode on the exact candidate:

| Role | Deployment ID |
| --- | --- |
| API | `d0af9f58-f349-4db6-8615-b552cce4bf23` |
| pandapower worker | `9f0a9bd2-fa1f-4c61-a844-979a3d55cf5a` |
| PyPSA worker | `590a7137-f0c6-4efb-9457-bd162f1f279d` |
| App | `aec4baef-4853-4de8-8b12-806861260ee6` |

All 53 backend Python files match local hashes in the API and both workers.
The App bundle contains the new controls and configuration guidance. API and App
health, both model families, retained result projections, public access denials,
both registered scripted cases, reports and evidence reads pass. Reverse history
on the earlier browser Thread reads nine public events in pages of two, with no
gaps or duplicates. Its bounded network projection returns the source diagram,
layer and completed event from one Attempt and Model Context.

The actual hosted App root was opened in a dedicated headed browser. A one-use
loopback bootstrap placed the cloud-dev operator token in that browser's normal
sessionStorage; the token never entered command arguments, logs or receipts.
The bootstrap process was then closed. Browser requests go directly to the
formal hosted API, with no API interception during these checks.

Thread `thr_4a08b89a6856da4c37b4` was created while the API still ran `188abe3`.
The browser retained it and an unsent draft throughout the actual API deployment.
Its event stream automatically opened one new connection and returned to live;
the draft survived without a reconnect click or page reload. Later checks pass
for refresh, visible new/switch, separate drafts, archive/read-only/restore and
retained initial Contexts in both families. Screenshot
`output/playwright/thread-session-cloud-accepted.png` was inspected.

All three task-owned cloud QA Threads are archived after acceptance; histories
are retained. The browser authentication state is cleared and the browser is
closed. Final health reports both workers ready, normal mode and zero active
Thread Attempts or legacy sessions. Receipts remain under
`runs/thread-session-cloud-verification/`; all earlier receipts are preserved.

Both workers still lack dedicated `DEEPSEEK_API_KEY` values and actual Provider
resolution is not ready. No real Provider request was made. These results accept
session management and recovery, not ordinary AI conversation or human release
approval. Demo remains unchanged.

## Review and remaining limits

Independent review spawn was attempted twice and rejected by the tool because
its inherited model is unsupported. No independent agent ran or approved these
changes. Inline source review and executable/browser verification provide the
evidence listed here.

Ordinary cloud-dev AI conversation is still blocked by missing dedicated Provider
credentials. Provider calls need separate authorization. This repair does not
claim Provider or human acceptance, and demo remains unchanged. Existing operator
authentication is retained; no individual account isolation or semantic memory
compaction is claimed.
