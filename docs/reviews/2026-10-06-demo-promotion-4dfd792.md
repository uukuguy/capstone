# Accepted cloud-development source promoted to demo

The user explicitly requested demo deployment after expanded cloud-development
acceptance. Promote backend source
`4dfd79260fdf874ac26af67ccd94dcb8a93f6062`, the exact accepted source. The later
documentation commit is not a new application candidate.

The [cloud-development report](2026-10-06-session-use-validation.md) records
the prerequisite local rebuild, fixes, source/runtime alignment and expanded
sequential, concurrent, recovery and resource checks. This promotion verifies
the deployed demo. It does not repeat local testing or the expanded load suite.

## Deployment identity

| Service | Deployment | Status |
| --- | --- | --- |
| API | `11335ecb-8f47-4e5b-97d5-0ee9c70f341a` | SUCCESS |
| pandapower worker | `8b278f1f-7b22-40f0-b042-2ca7f5ea9b2a` | SUCCESS |
| PyPSA worker | `c908954d-6bd3-4b95-8e5b-19c2ca32e2a5` | SUCCESS |
| Existing App | `3f6a362f-377d-4400-beff-2c7e74d0ef08` | Preserved; App source is unchanged |

Workers deploy first. Each passes health, source, contract and logical artifact
checks before API deployment. After deployment, all 343 backend source files
match the accepted archive in each of the three roles. Runtime contract
`48d470f5626f3b2abfd8a7c483f569f7e32721384dd343142b71cafdb80fa5ef`
and logical artifact
`21e36f81fa03a83477940092d2c837ff85d6627e4db8b0226ea586fb7884462c`
match local and cloud-development acceptance. Both workers have Provider
configuration and all backend roles are ready.

Existing demo environment values, credentials, resource limits and replicas
are preserved. Database, bucket and operator credentials remain separate from
cloud development. The App still selects the demo API origin. The previous
`c68f6e1` deployment IDs and settings are recorded as rollback targets.

## Deployed checks

| Check | Result |
| --- | --- |
| Entry and configuration | API ready; root App opens directly with open Thread access; bundle contains only the demo API origin. |
| Unknown model regression | Thread creation returns HTTP 422. |
| Real pandapower work | IEEE-39 AC power flow completes in 33.0 seconds with current-run authority admission and verified lineage. |
| Real PyPSA work | Two-bus economic dispatch plus AC validation completes in 59.0 seconds with current-run authority admission and verified lineage. |
| Original catalog question in App | Visible submission completes and contains all 21 registered PyPSA model IDs; result and evidence references remain empty. |
| Registered scripted cases | Both families complete; reports, result hashes and evidence replay pass. Public scripted credentials cannot create Provider sessions. |
| Retained data | Old demo report/result hashes match before and after deployment; evidence remains readable. Earlier terminal Thread events match their prior receipts. |
| App recovery | Root and New work; disconnect/reconnect and reload preserve the draft and answer. Composer is available; no remaining alert. |
| Display | Screenshots inspected. Widths 320 and 390 have no horizontal overflow. |

The numerical work has a 75-second idle observation. Both workers return to
zero retained and active contexts, with no resource-probe errors.

Final inspection after another 75-second idle observation, with the App still
open, confirms zero retained and active contexts in both workers. Active Thread
Attempts and active legacy sessions are also zero. The agent-owned Chrome
session is then closed; the browser session list is empty.

During the two real calculations, sampled combined backend working memory
peaks at 740.8 MiB and returns to 496.7 MiB in the idle sample. Working memory
excludes inactive file cache. These figures cover the API and two workers;
database, object storage and total billed usage are separate. Each backend
container reports eight CPUs and 8,000,000,000 memory bytes as its limits.

All deployed checks complete with exit code zero. The sealed receipt is
`runs/demo-promotion-4dfd792-20261006/acceptance.json`. The exact backend source
has local release tag `demo-20261006-4dfd792`.

Private promotion receipts are under
`runs/demo-promotion-4dfd792-20261006/`. Previous promotion and cloud-development
receipts remain separate. No stored user data is deleted.

The [release lifecycle](../architecture/capstone-development-lifecycle.md)
continues to govern later changes. Cloud-development capacity measurements
describe the tested workloads; this deployment check does not establish a new
simultaneous-execution limit or a total cloud-cost estimate.
