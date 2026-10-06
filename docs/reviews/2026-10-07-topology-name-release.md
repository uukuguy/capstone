# Topology name release

The user authorizes cloud-development verification and promotion to demo.
The released source is `c1c900a5d170af949514cbed180c5f30856be2f3`.
The [repair report](2026-10-06-network-element-name-consistency.md) records
the cause, authority naming changes and display rules.

## Behavior

Pandapower diagrams use the same names as semantic tool records. IEEE-39
internal bus IDs `10` and `12` display model names `11` and `13`. Internal
IDs, endpoints and calculation indexes remain unchanged. The App uses lowercase
`bus`, `line` and `trafo` prefixes for both model families. PyPSA links use
`link`. Canvas text, titles and hover status use the same display name.

## Local acceptance

`make doctor`, `make test`, `make test-e2e`, `make validate`, type checks and
package-boundary checks passed. Full gates ran at the protection-baseline
revision `69033d2`; the final App-only hover repair passed all 278 App tests
and its production build. Two read-only code reviews found no blockers.

The final `make capstone-local-rebuild` passed with API and both workers on
`sha256:8b824048488a739c6b20afe6c94aeaf494d7b76d5116d2322c3d967f6600b052`.
Actual local browser checks verified canonical names and hover status, PyPSA
display prefixes, reload and the 390-pixel layout. No Provider calls ran.

## Stage acceptance

Cloud-development and demo accepted `c1c900a` after source identity, public API,
actual browser, registered cases, reports and evidence checks. Demo uses the
same committed archive that passed cloud-development verification. All eight
deployments below report `SUCCESS`. No Provider calls ran.

| Role | Cloud-development deployment | Demo deployment |
| --- | --- | --- |
| API | `a18e9071-cf66-4749-a677-58562ecd387c` | `e1cc5a94-1700-47d8-8603-9f625f8fd60e` |
| pandapower worker | `a4b6785d-cb45-4a7d-8d38-504ea07dc022` | `504a337f-cb58-4274-bcb5-34bcc766a3d7` |
| PyPSA worker | `dd76e366-f508-4c83-b0c1-64c325c53e00` | `5e0f4dc0-c53b-4fd2-bcc7-c93f46d5b391` |
| App | `61b10f19-9f04-4d67-9b36-081ee13970e4` | `ae649096-c8c6-4827-8a84-52c20a532ab5` |

In each stage, API and both workers match 344 backend source files and the
local runtime contract and logical artifact hashes. App health and its selected
API origin pass. Authority diagrams return IEEE-39 bus names `11` and `13` for
internal IDs `10` and `12`; SciGRID returns 585 buses and 948 branches with model
names. Actual browser checks verify visible names, matching hover status,
PyPSA prefixes, Thread reload and the 390-pixel layout.

Both registered pandapower and PyPSA scripted cases complete their three
instructions, generate reports and replay their current-run evidence. Public
demo credentials still reject Provider mode. Reports and results from the
previous release retain their hashes and evidence remains readable. After
verification, both stages have zero active attempts, legacy sessions and
worker contexts. Test browser sessions are closed.

- [Cloud-development App](https://capstone-app-production-83ef.up.railway.app/)
- [Demo App](https://capstone-app-production-975e.up.railway.app/)

Both stages retain their existing isolated infrastructure and credentials.
No history, results or evidence are rewritten. Rollback targets and private
receipts are under `runs/topology-names-release-20261007/`.

The local release tag `demo-20261007-topology-names-c1c900a` points to the
released source. Source upload uses that committed archive. No `git push`
ran: the existing cloud-development `main` hooks would cause duplicate
deployments during this explicit rollout. Demo has no repository trigger.

## Verification recovery

The first `make validate` run rejected the old protected simulator tree digest.
The reviewed simulator tree was committed first, then its single digest was
updated. Eight gate tests and `make validate` passed. Other protected paths and
digests remain unchanged.

Early browser checks used visibility tests on zero-height SVG lines and counted
hidden diagrams from retained case panels. The final driver reads attached
bus symbols, uses the active canvas and verifies visible labels. Failure logs
are retained. The hover-status defect found through actual screenshots was
reproduced by both model-family tests before repair.

The first cloud App bundle check accepted only single and double quotes. The
deployed build uses backticks for string literals. The check now accepts all
three forms; actual browser checks passed before that check was corrected.
The first failure log is retained. This required no product redeployment.
