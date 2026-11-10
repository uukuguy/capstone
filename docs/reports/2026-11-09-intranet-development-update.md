# Intranet development update

## 2026-11-10 DKY3: template library and service-bus records

The user requested local-dev and dky3-dev. Both now use exact tested source
`eb481485bb21ce0b36d7fdd8ba53f0218e5be9ab`. No other stage changed. DKY3's four
roles are healthy; API/worker image1582f4266b7d, native3f84382d948c,
App405f4258bfda. Existing data, protected configuration, model default and gateway
selection remain. Backup: `private/backups/deploy-eb481485/`.

Real task89.41s, one current-call source attempt, actual State Grid template
generation, four download hashes, two PDF pages and process-title refresh pass.
See [the service-bus deployment report](2026-11-10-service-bus-execution-records.md)
and [public receipt](receipts/2026-11-10-dky3-dev-eb481485.json).
Acceptance tag: `dky3-dev-20261110-1729-eb481485`. Not merged into dev; no new CI.
The earlier failed75cb9790 trial below remains historical evidence.

## DKY3 follow-up: 75cb9790

The user requested the latest candidate on dky3-dev only. All four application
roles now use source `75cb97905963cb3a5d310bf0c28d261ef9f4fe8f`.
API and worker share image `86c64080d3ae`; native uses `58792bafa510`.
Readiness, four role health checks, source file hashes and the served App identity
passed. App asset is `index-CW2nEMew.js`, labelled dky3-dev.
The previous images and a database/configuration backup remain available under
`private/backups/deploy-75cb9790/`. Existing data, defaults and gateway stay intact.

Real file-task verification did not pass: the existing dsv4 Provider returned
headers but no body for 90 seconds, then raised ReadTimeout. The public task
check reached its 120-second limit. Cancellation was accepted for verification
thread `thr_7ef7854940035b421f96`; no further model trial was started.
No file download acceptance, browser acceptance or acceptance tag is claimed.
The browser connection was unavailable. Beijing-query convergence remains open.
Private receipts: `.capstone-agent/dky3-75cb9790/`.

Builds reused the installed dependency images. Backend/native layer counts are
154/47 versus inherited 146/37; grouped source copies remain in use. This remote
candidate build is not a clean-image or cache-efficiency acceptance. No local
Docker build, CI, push, merge or other environment update was performed.

## Earlier paired update

Selected source: `4a63874096f3346ee0f9a35b4c6725c9cf7eed76`.
This is the tested local candidate, not an integrated dev or release baseline.
The user requested deployment to intranet-dev and dky3-dev.

Both installations retain their own volumes, gateway configuration, model
selection and credentials. Database dumps and previous configuration are in
each installation's `private/backups/deploy-4a638740/`. The previous image tags
`df4ddf61` remain available for rollback. No CI, push, merge or cloud/demo update
was started.

App builds use the exact selected commit, same-origin API and separate
`intranet-dev` / `dky3-dev` identities. Dependencies have no lockfile changes
from df4ddf61. Remote amd64 builds reuse the installed dependency images and
copy the selected packages, configuration, report tools and templates. Native
resources are dereferenced before packaging. The neutral execution queue is
included. An initial intranet executor health failure was corrected before
the successful task check. No data volume was replaced.

Intranet API/worker image: `1505ca2277ecf57233d85d85c1562e044c16603de205b1414cd6e6ee4f2935b2`.
Intranet executor image: `0b6cf818b5964077a52b3fa925658bbf455b4373322e0bc9d78a4bafc466fd2d`.
DKY3 API/worker image: `d902d6a758a80464b3d93ff4782626307435022de32144856eb56c37209aad3f`.
DKY3 executor image: `65ec073fe85b262b7f8c68680bf20d120c2651c2ea2041f6d274b9d1e43e4275`.
Each stage checks API and worker equality; different builds retain the same source.

Intranet readiness and a real short task passed (8.83 seconds). A real file
task passed (19.24 seconds); downloaded bytes equal `4a638740` plus newline,
with SHA-256 `ae11f254eba1b3036825a6e1c990ec353d8bd1555a644b5d62ffbeba06c0d10b`.
Thread `thr_62fd9f587c678bc397a8` restored through the public snapshot API.
DKY3 readiness and all four role health checks passed. Its real file task
completed in 39.61 seconds, thread `thr_3ad22e5065a017bd4b64`. Downloaded bytes
and SHA-256 match the same expected file. Public snapshot restoration passed.
Both served App bundles contain the exact source and their own environment label.
Local `make doctor` and `git diff --check` passed.

Private logs and bounded task receipts: `.capstone-agent/deploy-20261109/`.
Browser connection was unavailable. No browser refresh or visual acceptance,
complex grid-task acceptance, full template-library acceptance or acceptance tag
is claimed. Local experimental text-pool enablement is not promoted by this update.

## DKY3 default model:16804

User selected intranet-dsv4-16804 at http://192.168.72.69:16804/v1.
The private profile is mounted read-only into API,worker and executor.
The old mount path was missing/replaced during concurrent runtime changes;
a separate dky3-default-16804.json now supplies the selected default.
Existing explicit session selections remain frozen. No other stage changed.

Final configuration uses CAPSTONE_WORKBENCH_LLM_PROFILES with a private
/run/capstone-private mount, rather than replacing image-owned configuration.
Replacing image configuration failed the catalog identity check; final containers
retain image inputs. Four roles are healthy and public input-catalog reports
default_profile_id=intranet-dsv4-16804. No new model request was made.
