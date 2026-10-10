# Demo N−1 repair release

Status: withdrawn and rolled back. User trials exposed missing formal answers
and false partial outcomes, including a GBnetwork introduction where all 28
tool calls succeeded. The following 2ea2266 deployment record is historical.
Current demo source: `ed2524f5774eb105178ba3f52d34ad36706b5cf8`.

## Verified rollback, 12:31

All four roles reuse their previous verified image digests. API and App health,
App source display, three registered cases (nine turns), reports and evidence
replay pass. These checks make zero Provider calls. PostgreSQL and user history
are retained. This rollback does not certify a fix for the original N−1 issue.

| Role | Rollback deployment |
| --- | --- |
| API | `26571056-7983-42c0-9cae-5764841d7eb7` |
| pandapower | `c0a0b907-7744-4426-9833-238096cf91f7` |
| PyPSA | `772d84c0-394b-4204-ab89-28d499719e17` |
| App | `7b89d17b-7993-4879-9db9-2755aad07bf5` |

Receipts: `runs/demo-n1-debug/demo-rollback-verification.json` and
`demo-rollback-checks.json`. Annotated tag `demo-20261010-1231-ed2524f` is pushed.
The withdrawn `demo-20261010-1150-2ea2266` tag remains unchanged for audit.

Local registered GBnetwork replay reproduced the cause: an internal whole-grid
ID hint made the result projection 97,559 bytes, exceeding its 64 KiB contract.
Generic ValueError recovery then fabricated failed tool receipts. The current
unreleased patch validates the full graph and retains only displayed IDs:
41,182 bytes. Optional display errors preserve admitted answers and evidence;
recovery applies only to typed reference rejection. New deployment requires
local verification and an isolated local demo first.

The user explicitly requested direct demo deployment before cloud-dev. This
release follows that instruction. Cloud-dev is unchanged. The existing demo
database, artifacts, credentials, access selection and sleep settings are
unchanged. The release contains the portable incident repair on `ed2524f`,
without newer local workspace and input features.

## Deployed services

| Role | Deployment | Image digest |
| --- | --- | --- |
| API | `b199342b-cc4a-4e49-81b5-33f19f74a490` | `sha256:845d901384c5e420aa22a846419bd8c9a9711ab45d0ad77a1037f434902280bc` |
| pandapower | `09aedccd-b017-425d-aa23-386ebc875f6e` | `sha256:8ea46e9b8c7565108610b024333d1cb326c968d8fdaf7e70466feb8f555e5ee3` |
| PyPSA | `1ac71210-cbdd-4107-8252-92db52865878` | `sha256:95fda77c89b21a4d2706dc7ec0b7be189458cff618a0d711d82e2805a5596cde` |
| App | `722910e8-c229-4f69-85c9-bfaec137f93f` | `sha256:02b2cce1257471b759f9671a8d4df81ea7442207ea0820be4c17262f74b6f064` |

All deployment messages identify the exact source. All three backend receipts
report stage `user-trial`, the expected role, and ready dependencies. Their
source, installed artifact and runtime contract hashes agree:

- Source artifact: `fd1d3f8053fe718252438636d9f12a16f3eb56a6653c5b851b1ea7b5429a21a3`.
- Installed artifact: `2c57c2552349ed9e1e1e02f82138ac1108658c7d0ab07e302327f02384e0911f`.
- Runtime contract: `48d470f5626f3b2abfd8a7c483f569f7e32721384dd343142b71cafdb80fa5ef`.

The source hash was independently recomputed from the exact tested release
archive, six verified model assets, and the installed public package identities.
The public App build receipt identifies the same commit.

## Checks and limits

- Local and portable gates are recorded in the [repair verification](2026-10-10-demo-n1-repair-verification.md).
- API and App health pass. Workbench preparation reaches ready for the database
  and both workers. Warm preparation measured 0.487 seconds; this is not a cold
  startup or sleep-policy benchmark.
- `pandapower-scripted-task`, `pandapower-scripted-test`, and
  `ac-dc-interconnection` each pass three registered turns, report retrieval and
  evidence replay. No Provider request was made by these checks.
- All 32 previously captured incident events remain unchanged in the 91-event
  history. The original Thread snapshot remains readable.
- Actual desktop and 390-pixel mobile pages display `v0.1.0 · 2ea2266` without
  horizontal overflow. No question was submitted through the browser check.
- Local network interruption caused TLS and SSH checks to fail in transit.
  After the user restored the network, read-only checks completed. Existing
  successful owned case sessions were reused for report and evidence checks.
- Temporary verification SSH registration, private identity and discovery
  links were removed. Existing user keys were preserved.

The user's full generator N−1 question has not been re-executed by the agent.
The historical missing powerflow completion remains undiagnosed. This release
does not certify a complete N−1 ranking or resolve startup and recovery latency.
Those limits remain visible in the outcome contract and
[known issues](../status/KNOWN-ISSUES.md).

Stage tag: `demo-20261010-1150-2ea2266`, pushed and exact target verified.
No cloud-dev tag is created for this direct demo release.

## User retry, 11:46–11:50

Read-only events for Thread `thr_669d57b23187d2a92a7d` show that the first final
answer includes English pre-tool narration. The substitute Attempt returns two
successful N−1 batch results. Two later result queries fail with
`result_field_unavailable`; a risk ranking fails with `unknown_result`. The
partial-admission path replaces the model answer with generic retention text.
The App repeats identical blocker summaries. These events identify invocation
errors, not missing model data or failed N−1 calculation. Complete scenario
coverage and numerical conclusions still require reading the saved results.

Rollback source: `ed2524f5774eb105178ba3f52d34ad36706b5cf8`. Previous deployments:
API `38508535-2a5c-4646-895e-1a3b560742dd`, pandapower
`e8bad5f8-fa7d-4c8d-9358-8e04d167bb64`, PyPSA
`4b64611d-5d17-4b7f-9587-8eff444c53e0`, App
`cc6321c6-60d5-4f5b-aadc-e5f704327a0b`. Restore matching source across all four
roles if required; preserve PostgreSQL and stored evidence.

Ignored receipts: `runs/demo-n1-debug/demo-final-deployments.json`,
`demo-runtime-receipts.json`, `demo-source-verification.json`,
`demo-release-checks.json`, and `demo-history-preservation.json`.
