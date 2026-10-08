# Cloud-dev App version acceptance

Status: passed. Source `ed2524f5774eb105178ba3f52d34ad36706b5cf8`.
The user requested a visible version during authorized demo promotion.
Cloud-dev was verified first. No Provider request was made.

The App shows `v0.1.0 · ed2524f` beside CAPSTONE. Its tooltip contains the
complete source commit. Desktop and 390-pixel mobile checks pass. Production
does not call the local build metadata route. Local Vite also marks uncommitted
product changes and refreshes Git metadata while the development server runs.

All four services were uploaded from the exact Git archive, with six verified
model assets and a non-secret App source receipt. Deployment messages bind
all four services to this source. API and both workers preserve the accepted
backend identity: source artifact
`d2a862c8d98737055810e49d563a470af372a39f66d8e83b377aba541b022787`,
installed artifact
`ba73684a9ba99314f12c6b1ba0963f5bb7166584591d921f0ebdb80909ad1741`.
The local/cloud runtime alignment gate passes.

| Service | Deployment | Image digest |
| --- | --- | --- |
| App | `1571b0d2-3c50-447b-891f-bf337aee3e83` | `sha256:6208f721ef2d23c10e8272bd4f702d4fc3253f8dc49458215a6638b71b17ef7c` |
| API | `f542e97f-ac75-4828-98d9-19f9374ee3d8` | `sha256:398e2bd69b79a1359573df3c667e48d51fb2b9994ee88cfbea9528bb876ee879` |
| pandapower worker | `834d9163-5bf7-4b32-b767-22a0b2c2e6a0` | `sha256:14d4a4215365840ea687bfacd5ace4eedffb003ee88f6bd11e28047a6c4deb96` |
| PyPSA worker | `4af7aedc-2519-482d-b463-9a596e1ddbb6` | `sha256:b7657b36d1e7f63f08be285dec0950731b84c4b0349307b4a03da67a4e58cb5a` |

Fresh checks pass: `make doctor`, `make test`, `make test-e2e`, `make validate`,
App build, 348 App tests, local rebuild, runtime identity, and both registered
scripted cases with three turns each, reports and evidence reads. Workbench
preparation reports actual database and both family readiness, completing in
0.478 seconds while warm. Owned version-check Threads were archived.

The sleep/activity implementation is unchanged from the
[automatic sleep acceptance](2026-10-08-cloud-dev-automatic-sleep.md). Its actual
idle and cold-wake measurements belong to that earlier acceptance; they were
not repeated for this header-only change. Backend installed identity is exact.
Demo promotion is a separate stage acceptance and receives its own tag.

Bounded operator receipts are in ignored
`runs/demo-idle-promotion-20261008/`, including `cloud-bindings.json`,
`cloud-runtime-alignment.json`, `cloud-cases.json`, `cloud-preparation.json`
and `browser-version.json`. Release logs are `/tmp/demo-version-*.log`.
