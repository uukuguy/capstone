# Cloud-dev autonomous-agent trial — 2026-10-13

Source: `24d9a3254a453df0cf79561ccd09d58d91c460e3`.

The user authorized development trial deployment with basic functional checks. This is not release acceptance or acceptance of all scientific explanations.

## Deployment

| Role | Deployment ID | Status |
| --- | --- | --- |
| API | c45652d9-ca67-4d91-ba4b-3d54d6431034 | SUCCESS |
| pandapower worker | 20f375b7-f658-405e-91b4-aa8cce802779 | SUCCESS |
| PyPSA worker | b7854082-965c-4858-be82-2b5e44a5bd04 | SUCCESS |
| App | abb8b601-634b-404c-b312-98b75d61ff6e | SUCCESS |

All roles were uploaded from the same exact committed source archive. The App contains a public source/environment receipt. Backend research mode is enabled. Existing stage database, bucket and protected credentials were retained. Demo was not changed.

## Checks

- API readiness returned 200; open Thread access returned 200.
- Browser displayed `cloud-dev · v0.1.0 · 24d9a32` and opened the workbench.
- Exact model-information question completed in 81.699 seconds with a Chinese opening and a persisted formal reply.
- Browser reopened that completed task: `thr_270d03cfc06ee731c7a4`.
- Deployment metadata confirms SUCCESS and the exact source message for all four roles.
- Runtime files were not independently inspected through SSH: no SSH key is registered. This is a limit of this basic trial check.

Receipts: ignored `runs/cloud-dev-24d9a32-1791858388/` and `runs/autonomous-live/api-intro-24d9a32-1791859060/` in the implementation checkout.

## Local entry repair

Local-dev uses fixed App5173 and API8767. The original Compose project `capstone` and PostgreSQL volume `capstone_postgres-data` were retained. A database backup was saved before rebuilding. API and both workers use image `sha256:0fdc007d34a21332cf6efa660dd53c572c0006ae9ccf05609400e6777e398b6b`.

The earlier App proxy pointed to isolated API8890. The reported Thread therefore returned404 there, while remaining available on8767. The proxy now points to8767. Browser verification reopened `thr_4c724280ea0f1c2fc5cd`; its event cursor remains1282 and its historical reply is visible. No Thread was deleted or replaced.

## Remaining scope

Scientific explanation errors, result reuse, basic-answer latency, research/model reset, full table paging and explicit original-task followup binding remain open. All three local tasks reached a terminal reply with saved records; that does not prove that every business requirement or interpretation passed.
