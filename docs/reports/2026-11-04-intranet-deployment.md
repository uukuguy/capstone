# Intranet deployment acceptance

Dev `6c55e6eed7c7988ef14baa9959dd9cd65e6d410e` is the running intranet source.
Annotated tag `intranet-20261104-1053-6c55e6ee` points at that commit.
This is an internal development install. It is not a main promotion, a cloud-dev
or cloud-demo update, or full release acceptance. main remains `0b68c607`.

## Exact runtime source

Target: `capstone-intranet`, `/home/dmdba/capstone-intranet`,
http://192.168.72.63:5173/.

Images were built linux/amd64 from the git archive of that commit, plus the
six verified PyPSA model files staged into the build context. The native image
was imported as one layer after the OCI export exceeded Docker's layer limit.
The imported runtime configuration keeps the allowlisted environment, working
directory, command and ports. The local import check matched that configuration
and the source revision label.

| Role | Exact image ID |
| --- | --- |
| API and native worker | `sha256:d501f06021260c778d6afc7e91c9588d88ef090d810600b243c815b2a784386d` |
| Native executor | `sha256:e4eb33b6a105962184ea009542f70519295513f1404f9368e7642bec0e841917` |
| App | `sha256:be7cda39292077a3720faa0784cd7ca6bb650a2efdc2c802fc193f6371b42b25` |

API and worker use the same image. The served App references
`/assets/index-BWRM_Df8.js` and `/assets/index-DCfrdKJ1.css`.
Transfer archive SHA-256: `0ff9d69c5a87f10c7db9d625a7cb1f8a41a06d1e0cc38287e7762052f3dd8d88`.

## Data and activation

PostgreSQL and the object store stayed on `capstone-intranet-postgres:20261101`
and `capstone-intranet-objects:20261101`. Volumes were not removed.
The ledger backup is `private/backups/pre-6c55e6ee/ledger.dump`.
The previous environment and Compose files are in `private/backups/release-6c55e6ee/`.
Rollback images `25c71f85` remain on the host.
Both resource-management flags in the runtime file are `0`. The API and executor
see `CAPSTONE_RESOURCE_MANAGEMENT_ENABLED=0`. Native attempt slots are `1`.
The executor permission profile is `intranet`. Secret values were not displayed,
and Provider credentials were not changed.

Activation recreated API, native worker, native executor and App with project
`capstone-intranet`, `--no-build` and `--pull never`. All four are healthy.
`/health/ready` returns `{"status":"ready"}`.

## Real acceptance

Thread: `thr_e62c227c65f77ecebe76`.

- First attempt `attempt_e35829259f4b0e99` completed in about 28.0 seconds and saved `deployment_check.csv`.
- That same 28-byte artifact was published twice with one SHA-256. The continuation did not replace it.
- Continuation `attempt_c36f812356aad3be` completed in about 50.8 seconds and read the saved file.
- CSV rows are `name,value` and `release,6c55e6ee`. SHA-256 `2768941343fc416a853150b53375eac4a42c7dc67705a728bde8e0d89446a300`.
- A later snapshot fetch returned the same thread and event sequence. A second download matched the first bytes.
- The input catalog reports resource management disabled.
- No `attempt_failed` event was recorded. This receipt does not claim a zero-error tool log or a browser visual pass.

The existing Vivaldi tab was not driven. HTTP checks used a direct connection with the proxy disabled.
The CSV holds a supplied release string. It is not Authority or business evidence.
No historical summer case was replayed. Professional solver profiles, cloud-dev and cloud-demo were not changed.

Evidence: `runs/intranet-release-20261104/`. Image staging: `.capstone-agent/intranet-6c55e6ee/`.

## Deployment identities

Checked at 2026-11-04 10:53 CST. API, worker, executor and App were healthy.

## Version label correction

The first App image omitted `build-revision.txt` and `build-environment.json`.
Its page showed `环境未配置 · v0.1.0 · 开发版`. That image remains on the host as
`capstone-intranet-app:6c55e6ee-blank-version`, id
`sha256:be7cda39292077a3720faa0784cd7ca6bb650a2efdc2c802fc193f6371b42b25`.

A second App,
`sha256:a1955fb9c66b8aed0564f9982608d096927cf9f13a0cc455b1abcc570aac493b`,
used a same-origin `local-dev` receipt. Production rewrote that label, so the
page showed `user-local · v0.1.0 · 6c55e6e`. Served script
`/assets/index-D_Yih8OK.js`. That image remains
`capstone-intranet-app:6c55e6ee-user-local`.

The running App is now
`sha256:ff9eb45691051585ecb802d5f58877940a8e2788556f0935d664f8fc1a27d060`,
container `fd8db3e281b5b9b9f583e6b89266d2617199073252e6536fe1aea3aa1cb3afc0`.
The receipt environment is `intranet-dev`. A fresh page shows
`intranet-dev · v0.1.0 · 6c55e6e`. Served script `/assets/index-oaLTgvHT.js`.
The local Vite page shows `local-dev · v0.1.0 · 6c55e6e` for the same
repository commit. API, worker, executor, database and volumes were not
recreated. The acceptance tag still names the first App image.

## HTML table preview

At 2026-11-04 16:44 CST the App was replaced again. The running image is
`sha256:c0cacc597a79e68e7ee4e172d0a3fe505864ced60b4297c2f73e26a820515569`,
container `547c1ba551e8547cae17bda562e613ae36c2a66f4d7c8e92ce3cccd0d9137bd0`.
Served script `/assets/index-D6zsKizj.js`. The page label stays
`intranet-dev · v0.1.0 · 6c55e6e`. Wide HTML tables scroll inside the preview.
Archive SHA-256 `9bbb66a5433854b3ff983e209e9b297765b592fd5f8e8a6a66cbd8bea96a2270`,
path `/home/dmdba/capstone-intranet/releases/6c55e6ee/app-table.tar.gz`.
The previous App remains `capstone-intranet-app:6c55e6ee-before-table`.
API, worker, executor, database and volumes were not recreated.

| Container | ID | Image |
| --- | --- | --- |
| `/capstone-intranet-api-1` | `3cabff2264c6e6014dd80339d2f717447abd8fe643ba454760fa0e8c215c437a` | `sha256:d501f06021260c778d6afc7e91c9588d88ef090d810600b243c815b2a784386d` |
| `/capstone-intranet-worker-native-1` | `bcdc1968d8a15315628da791345b1fe638fe8141e2ac129c8fcc1f936a9ce5f4` | `sha256:d501f06021260c778d6afc7e91c9588d88ef090d810600b243c815b2a784386d` |
| `/capstone-intranet-general-pi-1` | `76e224cbd8c60b5edf19633db6df7eabd1018dc59f147bebeb14131815768d1d` | `sha256:e4eb33b6a105962184ea009542f70519295513f1404f9368e7642bec0e841917` |
| `/capstone-intranet-app-1` | `fb95cd0d70b27c2d9939b57b5f2509cc07d4a0629cb423a0fa947f47323b1360` | `sha256:be7cda39292077a3720faa0784cd7ca6bb650a2efdc2c802fc193f6371b42b25` |
