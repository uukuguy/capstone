# Catalog completeness release

The user authorizes automatic cloud-development verification and promotion of
the locally verified repair. Manual acceptance is waived for this release only.
The candidate is `39007a1381dd0e617a2fe9c63a6d23b65474bcf9`; the
[local repair report](2026-10-06-catalog-completeness-local-fix.md) records its
540 backend tests, registered worker tests, canonical rebuild and actual App
verification.

Cloud development and demo pass automatic acceptance on the same backend source.
Both receipts have status `passed_catalog_release_checks` and exit code zero.
The [demo root](https://capstone-app-production-975e.up.railway.app/) opens the
conversation workbench without a login step.

## Artifact and configuration

The cloud-development API and both workers match all 344 committed backend
Python source files. Demo verifies the same 344 files in all three roles. Runtime
contract and logical artifact hashes match the accepted local services. Both
worker Providers resolve successfully. Demo uses the same source archive and
six pinned model assets that passed cloud-development acceptance.

| Backend role | Cloud-development deployment | Demo deployment |
| --- | --- | --- |
| API | `219f8e72-6bfb-4b96-8b2e-96e6aaded7a5` | `74dc2455-0bfd-4ea6-874f-da8d6442de19` |
| pandapower worker | `044d4154-697e-4fa9-bfa2-d854dfdb6176` | `bbfefc4a-2f15-466b-ab4d-8c5ac8edbed6` |
| PyPSA worker | `b2d02d89-f4a1-4d5c-8224-2fd38c8091bc` | `146ffa3a-d749-4033-b2a7-1b04f7a59260` |

All six backend deployments are SUCCESS. Cloud-development App deployment
`9cdf0b94-217f-4bc3-8a79-5dfa928d1d9e` and demo App deployment
`3f6a362f-377d-4400-beff-2c7e74d0ef08` remain unchanged.

No App source changes, App deployment, credential rotation, infrastructure
configuration or capacity changes are part of this release. Cloud development
and demo keep separate databases, artifact buckets, storage credentials,
operator tokens and public origins. The App root remains the conversation page.

## Automatic checks

Cloud-development acceptance covers the following:

- Replay the original incomplete catalog prose through the deployed admission
  code with the current stage catalog. All 21 registered PyPSA identifiers appear
  in the corrected deterministic informational answer, with zero evidence refs.
- Submit Chinese and English catalog questions through the actual App, then
  submit the Chinese question after selecting two-bus through the model control.
  All three final answers show every registered identifier. These live answers
  are already complete and keep their Provider prose.
- Complete actual two-bus economic dispatch plus AC validation with four result
  refs, four evidence refs and verified current-run lineage. Reload preserves
  the answer; the 390-pixel layout has no horizontal overflow or App alerts.
- Continue a pre-deployment IEEE-39 Thread with a new AC calculation. Its old
  terminal event remains unchanged. Earlier report/result hashes and evidence
  remain readable through their own stage API.
- Complete both registered scripted cases, generate reports and replay evidence.
  Public demonstration credentials receive 403 for Provider session creation.
- Observe 75 seconds of idle recovery. Both workers report zero retained and
  active contexts; the ledger has no active Attempts or legacy sessions.

Demo repeats the deployed omission replay and one actual original Chinese
catalog query, which shows all 21 identifiers with no result/evidence refs.
It verifies the App root, unknown-model rejection, model switching, reload,
actual dispatch plus AC validation, continued use of a pre-deployment IEEE-39
Thread, retained reports, both registered cases and evidence replay. The PyPSA
answer has five admitted result refs and five evidence refs with verified lineage.
The continued IEEE-39 calculation completes in 53.3 seconds; the Cloud-development
continuation completes in 33.2 seconds. These are functional observations, not
new load measurements.

Demo also passes the 75-second idle check with zero retained/active worker
contexts, zero active Attempts and zero active legacy sessions. A final read-only
reopen confirms the persisted numerical answer and current two-bus diagram are
visible without alerts. Final desktop and mobile screenshots are inspected.
All owned browser sessions are closed; the automation browser list is empty.

Private receipts are under `runs/catalog-completeness-release-20261006/`, with
separate `cloud/` and `demo/` folders. Screenshots are under
`output/playwright/catalog-release-20261006/`. Owned test browsers close after use.

## Verification recovery and scope

The first cloud check uses a wrong prior receipt filename. Two UI checks use
premature display assumptions, including counting a delayed model-open reply as
the following catalog reply. Their failure logs and stored events are preserved.
The final check matches the current turn's completed message and verifies that
message's identifiers. These corrections change verification scripts only.

One HTTP status read times out after a scripted case has successfully closed.
Fresh direct and proxy-route reads return ready/completed in about one second.
Read-only recovery checks the same two completed sessions, reports and evidence;
it submits no extra calculation. The failed polling log remains available.
Future scripted checks bound retries to GET operations; POSTs are submitted once.

The Railway SSH gateway also closes the direct TCP connection after 31.3 seconds.
The same existing identity, service and command succeed in 4.44 seconds through
the already configured local HTTP proxy. A task-owned SSH wrapper uses
[OpenSSH ProxyCommand](https://man.openbsd.org/ssh_config) and the existing proxy
for these operator commands. It changes no server setting, key or global SSH
configuration. Successful routed reads then verify both demo workers before the
API upload. The worker deployments are submitted once each.

Routine patches should reuse completed stage checks and validate receipt paths
before cloud operations. Cloud development verifies configuration, startup and
critical integration behavior. Demo verifies the exact promoted source and key
user flows. Broad queue, memory and recovery tests are appropriate when runtime
or capacity behavior changes.

The [earlier demo pressure report](2026-10-06-demo-load-validation.md) remains the
measurement record for source `4dfd792`. This release changes catalog completion
and does not repeat the complete pressure suite. Its resource claim is limited
to successful idle cleanup after the targeted functional checks.
