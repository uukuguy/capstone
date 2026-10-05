# Shared Harness: cloud-dev verification

## Candidate and scope

The deployed source is `188abe3536722623c2e85d596195de6f60401a16`, the exact
candidate from the passing [local Harness verification](2026-10-06-harness-provider-configuration-local-verification.md).
The user authorized cloud-dev deployment after local checks. All four services
deploy successfully in normal mode. No protected variables or credentials were
changed. Demo remains unchanged.

Provider-free automated verification passes. Ordinary AI conversation remains
unverified and blocked by missing dedicated Provider credentials in both workers.
This is not manual acceptance or permission to promote to demo.

## Deployment identity

Target: Railway `capstone-cloud-dev`, project
`5eecde6b-fec2-40d2-8b26-427025b02b96`, environment
`5afd6aeb-07a6-4320-92e9-4bf193a442cb`.

| Role | Deployment ID | Result |
| --- | --- | --- |
| API | `d004bca6-3ada-4902-b5fa-7631a8fb8faf` | SUCCESS |
| pandapower worker | `daa856c4-8893-4efe-bac1-733c45943398` | SUCCESS |
| PyPSA worker | `daefd425-de5f-41f8-a6b1-9b6ee4bf939b` | SUCCESS |
| App | `d92ccacf-c08a-426d-a6f9-29c9464a38d8` | SUCCESS |

All deployment source messages identify the full candidate revision. Protected
SSH checks match the five changed runtime, Harness, worker and adapter files
against the locally verified hashes in all three backend roles. Railway builds
each role separately; identical backend image digests are not claimed.

[Cloud-dev App](https://capstone-app-production-83ef.up.railway.app/) opens the
private Thread route. Its generated domain contains “production”; the deployment
target is the isolated cloud-development project above. The API origin is
`https://capstone-api-production-bb72.up.railway.app`.

## Automated checks

Ignored receipts: `runs/thread-harness-cloud-verification/`.

| Check | Result and receipt |
| --- | --- |
| Normal readiness and App | API ready, App HTTP 200, M11 endpoint disabled; `normal-readiness.json` |
| Source identity | All three backend roles match local188abe3 across five files; `backend-source-identity.json` |
| Public access boundaries | Nine denials cover Provider options, unknown cases and private Threads; `normal-readiness.json` |
| Registered model catalog | Both families available, 81 models; `fresh-thread-catalog.json` |
| Fresh private Threads | One Thread per family retains its initial Context; no instruction submitted; `fresh-thread-catalog.json` |
| Missing configuration | Real factories in isolated memory return `runtime_configuration_invalid` and retain prepared Contexts; `cloud-missing-configuration.json` |
| Fresh registered cases | Both families complete three turns, reports and admitted evidence reads; `cloud-normal/legacy-f1364be1856d.json` |
| Restart retention | Eight prior result projections and prior browser events/diagram remain available; `normal-readiness.json` |
| Final private health | Both workers normal/ready; zero active Thread Attempts and legacy sessions; `private-health-final.json` |

The retained results use the explicit `a1f028d` verification baseline. This
repair did not repeat the earlier M11 matrix or claim new lost-receipt browser
execution. Fresh pandapower session: `session-b0f445cab699e90b16e17e72`.
Fresh PyPSA session: `session-dad44827e797cc8d11ce2282`.

The served App asset is `/assets/index-h98qCI42.js`, SHA-256
`eeb0087d657ab15444539d9e821048be5ce915f0991cc677ed473532e65149d8`.
It contains the verified command-recovery behavior and new configuration
guidance. A headed browser opens the root route and renders its private Thread
login; screenshot `output/playwright/harness-cloud-dev-root-login.png` was
inspected. No operator token was submitted in that QA browser, and authenticated
browser conversation is not claimed. The QA browser is closed.

## Remaining acceptance

Protected configuration checks confirm `DEEPSEEK_API_KEY` is absent in both
cloud-dev workers. Actual Provider resolution is therefore not ready. Evidence:
`provider-configuration.json` and `backend-source-identity.json`. No secret value
is written to logs or receipts; no local or demo credential is copied.

No real Provider request was made. Missing-configuration checks use an absent
test credential only in isolated subprocess memory; the registered cases use
the public scripted boundary. Dedicated cloud-dev credentials and separate
authorization are required before real Provider smoke checks. Human cloud-dev
acceptance must pass before demo promotion.
