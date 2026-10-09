# Business workspace and role resources verification

Date: 2026-10-09. Scope: local offline integration of Tasks 1–7.
This receipt records actual execution and controlled-fixture limits. Main
integration, canonical rebuild and independent final review are complete under
the bounded scope recorded below. No cloud deployment, acceptance tag, paid Provider request or
personal authentication configuration was used.

## Runtime proof

Two fresh Linux aarch64 images were built from the Task 6 source at `4002817`
with the Task 7 required PyPSA lock synchronization and source type corrections.
Both images were rebuilt after the final runtime-source edit.
The final integrated main checkout must still use `make capstone-local-rebuild`.

| Image | Exact image ID |
| --- | --- |
| `capstone-backend:task7` | `sha256:f5e0e91b0f0f6e6896adffab359bc43501c545b3ba9269c3f9e0d62ac8c4ea52` |
| `capstone-general-pi:task7` | `sha256:3e59a0ab18bb01abfcbad7ed6047a3283b4ab387c1855f551603d710cbb8aeee` |

The backend installer created its own Linux runtime at its final stable path.
It did not copy a macOS venv. Its installation ID is
`installs/4b2585dff0ab473489362b83333fdba0`; prepared descriptor SHA-256 is
`2b3ef407d50a81811d505d73494f5e94850431126536597b4221c00b86815867`.
The descriptor records CPython 3.12.12, Linux aarch64, pandapower 3.4.0,
MCP 2.3.0, PowerMCP 0.4.0 and PowerIO 0.11.4. The fixed sources are
PowerSkills `05bda3a51d5f1ecad888d4d4663c28478c643a7e` and
PowerMCP `63341e67ce6ae5650396ab92b2be7f86e3409da1`. Managed Pi is
0.84.4 at `b79e4cc834970cca69daebffab7df1da7d1e52c4`, with Node 24.20.0.
The native image's independent seed installation is
`installs/93babec5a73449bbb8e34bef1c238020`, descriptor SHA-256
`0cf6519b1f7eb9fe719e87e32bf1e770ec32b458951f7c49df45c221821f7806`.
Both descriptors bind the same CPython executable SHA-256
`a93dceeb5522ea1d6db88f5f56b49b714ac75279c4b1a2d69fa97244fdb01a60`.

The final fresh native image passed `test_general_pi_native.py`: **3 passed in
71.09 s**. Real SDK loading, typed skill expansion, four real MCP calls in both
native roles, literal slash input, private MCP state, protected input bytes,
isolated readiness UID/environment and cancellation cleanup were exercised.
There was no source-module injection. Cross-image historical installation
retention remains the separate Task 4 proof; this fresh test used one image.

`test_business_workspace_images.py` passed **1 test in 125.86 s**, with
**18 controlled model HTTP requests**. It started the actual hosted API, both
registered family workers, native service and a separate PostgreSQL container.
It checked native and API readiness, actual worker input-resource HTTP discovery,
accepted typed inputs, three execution roles and API/worker image equality.
All three backend roles used the exact backend image above.

Direct and delegated Pi loaded the actual PowerSkills body and invoked real
`load_network`, `get_network_info`, `audit_network` and `run_power_flow`. These
checks used the explicitly requested bundled sample, not the selected business
model. Harness loaded the original professional adapter, used production Pi
semantic dispatch, ran the Authority structural audit on the selected model,
read persisted evidence and completed with `authority_backed` admission.
Native completions had no Authority result or evidence references.

Only model HTTP response decisions were controlled. Production factories, SDK,
semantic extension, tool dispatch, Authority execution, admission and hosted
routes were not replaced. Synthetic native Provider configuration and worker
`models.json` were test-owned. A container-local HTTP proxy kept the Kernel's
loopback transport requirement intact. The test proves composition and real
tools; it does not prove real model selection or answer quality. Thread state and
Authority workspaces used test-owned containers. This check did not upload a
report to S3; reporting and artifact replay are covered by the offline gates.
The test removed its named containers, PostgreSQL data, runtime volume and network.

## Scenario coverage

| Scenario | Evidence and limit |
| --- | --- |
| Ordinary and unrelated weather | Nine matrix tests check empty context and no Domain Pack preparation under controlled semantic decisions. No live weather source is claimed. |
| Business weather, selected object and mixed goals | Matrix and delegated-runtime tests bind only the relevant goal to the selected public object; other goals have empty business context. |
| Historical object, revision change and retry | Intent-runtime, business-context and native-resource tests preserve frozen snapshots, explicit public versions, role revisions and source identities; unknown refs fail. |
| Missing material and ambiguous reference | Public catalog states no full model tables; bounded projection and clarification tests fail closed. A fixture material proves contract validation, not exported model data. |
| Real skill and MCP use | Fresh native image and combined hosted image checks above. Native observations remain external; professional evidence crosses the Authority contract. |
| Unknown slash and mode changes | App tests require a literal-text choice and retain incompatible skill/draft state. Native text disables command/template expansion. |
| Mobile draft and panel layout | Task 6 used real Chromium at 390×844 with a populated UI fixture; this proves UI state/layout, not installed readiness. Current component tests cover next-draft editing and uncertain receipt recovery. |
| New and previous Threads | Task 7 checks that global App tool preferences survive creation of a new Thread and return to the previous Thread, within the mounted App. Existing draft storage is unchanged. |

Public context is currently identity, public version and bounded history. Limits
are 24 KiB context text, 16 objects, eight materials, 4 MiB per material and
16 MiB material total. The complete Pi request retains its 256 KiB limit. These
are validation ceilings, not a claim that full network exports are available.
The default federated dialogue has no assembled Case execution service. Its
unavailable Case operation is truthful; the independent Case module and `/old`
entry were not expanded.

## Offline gates and corrections

The initial full gate run passed doctor, grid-agent (**928 passed, 2 skipped**),
grid-simulator (**204 passed, 2 skipped**), Pi grid tools, capstone-agent
(**1091 passed, 56 skipped**) and Model Capability SPI (**13 passed**).
The App gate then reported **383 passed, one failure**. Its old fixture returned
a snapshot from `/models`, which correctly froze the new state-aware controls.
The corrected fixture returns 404 for the optional workspace and waits for
usable controls. An initial proposed Thread-ID preference map was wrong: the
owning M4 product record specifies global App preferences across conversation
changes. That production change was withdrawn. The existing preference scope
and original cross-conversation assertion are retained, with an extra assertion
when returning to the previous Thread. Final App results are recorded below.
The corrected focused suite passed **five tests**; the final full App suite
passed **384 tests in 36 files**, and its TypeScript/Vite build passed.

The original `pypsa-agent/uv.lock` failed `uv lock --check` because it omitted
the new capstone-agent jsonschema/referencing dependencies. Required transitive
entries were synchronized without expanding dependency versions. All ten
actual Python project locks then passed `uv lock --check`.

The resumed gate stopped at the simulator protected-tree baseline. Task 5's
reviewed Authority bridge in `c9f9756` changed that tree from
`84372c336073a9a950073bc6820e1ec93af33429` to
`044e6155cc62094a9770c95a78652a9db5c32843`. The protection manifest was
synchronized to that reviewed tree; the checker and other protected entries
were unchanged. The focused protection check passed.

Isolated PostgreSQL, intent snapshot and typed input tests passed **61 tests in
4.09 s**. The scenario matrix passed **9 tests in 0.20 s**.

The canonical source type gate found 12 errors in new interfaces and normalized
container types. The fix adds existing catalog/family methods to `ThreadService`,
narrows the already normalized BusinessContext and prepared application, and
types checked JSON mappings. No `Any` or type-ignore rule was added. A follow-up
identified one related context-list append and was corrected in the same scope.
The final source type gate passed with **zero errors and warnings**. Directly
affected tests passed **192 tests, six optional skips**; the final router check
passed **20 tests**.

All `make test` subtargets completed across the initial and resumed runs. The
remaining suites include App 384, Kernel 567, pandapower pack 111, inventory
service/pack 11/132, PyPSA modeling/authority/sector 48, capacity 1, operations 5,
registered PyPSA cases 7, PyPSA application 41 and workbench 156 passed tests.
CLI end-to-end passed **39 tests**, and actual registered worker checks passed
**three tests**. `make validate` passed offline **7/7**, scripted core **10/10**,
scripted full **8/8** and capability matrix **24/24**. Application instantiation
passed **2/2**, including report and context-replay checks. Validation types,
application/package boundaries, protected paths, source setup, App build and
the four Pi input-capture success/failure checks passed. `make test-packages`
passed isolated installed-package smoke, actual HTTP Authority, PyPSA handoff,
operations/planning and npm/grid-agent configuration checks.

## Warnings and dependency risk

Warnings remain visible. Existing causes include pandapower legacy
`tap_dependency_table`, NumPy matrix deprecation, estimation
`SettingWithCopyWarning`, deprecated `in1d`, Python 3.14 boolean inversion and
the existing GeoAccessor registration warning. Starlette/httpx TestClient emits
its existing deprecation. Build logs also show optional numba absence,
`node-domexception` deprecation and npm install-script allow-list notices.
PyPSA also emits its objective-constant FutureWarning. The App build retains its
large-chunk and ineffective-dynamic-import notices. Pyright's update notice is a
tool notice. No broad warning filter or unrelated
dependency upgrade was added. The installer still suppresses successful child
stderr; Task 3's Minor finding remains open.

Fresh npm build output reported three affected packages. A read-only audit of
the first image's Pi workspace, with the same pinned Pi dependencies as the final
image, reported **14 affected packages**
(one Critical, ten High, three Moderate); `--omit=dev` reported **five**
(one Critical, four High). Audit counts can change as advisories change.
The historical zero-advisory remediation record and passing offline runtime-risk
gate do not mean that this image has zero current advisories.

| Installed dependency | Advisory and available repair | Current application scope |
| --- | --- | --- |
| `shell-quote` 1.10.0, via `@anthropic-ai/sandbox-runtime` | [GHSA-pqg4-j6r4-53mv](https://github.com/advisories/GHSA-pqg4-j6r4-53mv), patched in 1.11.0 | Requires a comment token followed by a token with a line terminator, then shell execution. This dependency belongs to the disabled sandbox example; the selected extensions do not load it. Current-path exploitability was not established. |
| `brace-expansion` 5.0.9, via coding-agent/minimatch | [Nested-recursion DoS](https://github.com/advisories/GHSA-qhr7-859c-m2p7); the audit also reports related CPU/recursion advisories. 5.0.12 covers the reported ranges. | Model-scope and resource filter patterns come from protected operator settings, not task parameters. Native tasks have isolated UIDs and finite deadlines. Those limits do not prove synchronous recursion is safe. |
| `undici` 8.9.0, via coding-agent | [Decompression DoS](https://github.com/advisories/GHSA-3xpg-4rpp-hhhm), patched in 8.10.2; npm suggests 8.11.2 for the dependency | Pi uses EnvHttpProxyAgent, Client/Pool and global fetch. The advisory requires the decompress interceptor; no such interceptor, BalancedPool, retry/cache/dump interceptor was found in this path. Current deepseek/relay use SSE. Other registered Provider transports need separate assessment. |
| `node-forge` 1.4.0 and `undici` 6.28.0, via Gondolin example | [RSA verification issue](https://github.com/advisories/GHSA-86w9-cpqp-85rv); npm reports no automatic Gondolin repair | The Gondolin example extension is not selected. Its RSA/HTTP paths were not part of this execution. |

These scope conclusions are inferences from the exact installed source and
selected configuration, not exploit tests or a security clearance. The listed
dependencies were already in the fixed Pi baseline. They remain unmodified and
unresolved. Final review must assess this record independently. Full audit JSON
and installed dependency paths are retained in the ignored Task 7 evidence folder.

## Delivery limits

Root owns independent Task 7/whole-branch review, local main integration,
canonical main rebuild, exact running image identity and App readiness. No main
service or user data was changed by this worker. Paid Provider validation,
cloud-dev/demo deployment, promotion and acceptance tags were skipped. They are
not prerequisites for this local offline implementation receipt.

## Final review fixes: retained professional resources

The I1 fix adds a private accepted professional selection to the existing
submission snapshot. It retains guide bytes/hash, skill/version, binding,
native content identity, installation ID, descriptor hash and profile revision.
The worker sends this only through its authenticated catalog endpoint.
Admission rejects client-supplied private fields. Public catalog, snapshot,
events, history, intent and accepted-context projections omit these bytes.

Application preparation uses the accepted selection before normal Kernel
composition and Authority model binding. It derives an immutable Domain Pack
provisioner with only the three existing backend settings. A/B contexts have
separate cache identities and leases. Retained installation inspection and
current role revocation checks are separate; moving the current pointer does
not select B for an accepted A task.

The final real retained-runtime test passed **1 test in 189.35 s**. It accepts A,
publishes a distinct B installation before the first claim, starts and retries
A, starts a newly accepted B, and restores A with a new owner from serialized
private selection. The standard application preparer/model binder, production
session builder and real Authority structural audit verify each installation
and model revision. It checks materialized guide bytes and an actual missing
retained directory. Its Pi RPC client only records launch configuration; the
separate combined image test covers the real SDK loop. Four existing pandapower
legacy tap-table warnings remain.

Focused checks passed **140 tests**, with one opt-in image test skipped and the
existing Starlette/httpx warning. These include PostgreSQL service recreation
before first start and retry, current revocation, private-field forgery and
projection, and A/B cache pin/release/close isolation. Normal preparation and
Domain provisioning passed **19 tests**. Source types and `make doctor` passed.

M1 is fixed: native-name slash lookup preserves exact binding/version and
refuses same-name ambiguity; the picker shows original name, version and source.
The affected App tests passed **8 tests**, and its build passed with its
existing notices. M2 is fixed: image cleanup now attempts all exact owned names,
keeps bounded errors, preserves a primary failure, and verifies removal.
M3 remains open: captured installer stderr still lacks bounded sanitized
operator diagnostics. This fix does not clear the dependency advisories above.

Both images were rebuilt after the final runtime-source change:

| Image | Exact image ID |
| --- | --- |
| `capstone-backend:final-resource-fixes` | `sha256:97654214807c10ecae7958701f15dd9f73ff63f778f49a5e7a69648115076f8b` |
| `capstone-general-pi:final-resource-fixes` | `sha256:76ea9966f2229f27f9707df8b4eca6e1cea0ec326de15acbb871f5c8eb421325` |

The backend installation is `installs/a4809f34616841f78746ab52037672a9`,
descriptor SHA-256
`0ce2779aa8a073d99e55fb02f6e33fb0cd04bc1b63df73b74efbe1d1187dcba0`.
The native seed installation is `installs/d94af151ac06469082f1f0d9f84c897f`,
descriptor SHA-256
`72b2d80d9b63b3e322529e0f81a455bc88a0fd01d4e6f3b85680f36342938cfd`.

The first two combined runs failed at worker startup because the closed
executor-discovery validator rejected the new native name and description.
A focused regression reproduced the failure. The validator now permits only
these bounded optional fields and still rejects unknown/private fields.
Discovery and delegation checks passed **84 tests**. Both failed runs verified
cleanup, and the images above include the correction.

The final combined image check passed **2 tests in 104.75 s**, including cleanup
behavior and direct Pi, delegated Pi and Harness execution. Its real SDK made
**18 controlled Provider requests**; the Harness path ran the real Authority
structural audit and evidence flow. The runtime image IDs match the table above.
The test-owned containers, retained-resource volume and network were verified
absent after completion. The independent PostgreSQL fixture was also removed.
The ignored evidence log is
`.superpowers/sdd/business-workspace/final-fix-combined-final.log`.

The professional retention claim requires the old managed installation at its
stable path. Same-host/same-image process and ledger restart are covered.
Backend images currently carry their own runtime; replacing an image without
retaining A produces an explicit unavailable result. This work adds no backend
volume or automatic migration and does not claim seamless cross-backend-image
recovery. The earlier native-Pi cross-image retention proof remains separate.
No active installation cleanup was added.

## Main integration and actual App verification

The full branch review approved `a1e086a` after I1, M1 and M2 were resolved.
No Critical or Important finding remains. M3 installer diagnostics and the
upstream dependency debt above remain deferred. Main was fast-forwarded without
overwriting the seven pre-existing modified paths or existing runtime data.

The first main App check found a mobile layout defect: the skills panel opened
above an overflow-hidden thread boundary, which clipped its heading and close
button. Follow-up `7fda5e9` limits all input panels to the measured available
thread space. The fix passed independent review, **385 App tests in 36 files**,
TypeScript and the production build. The existing build warnings remain.

The final `make capstone-local-rebuild` ran from main at `7fda5e9` and exited
zero. Its log is `/tmp/capstone-business-workspace-main-final-rebuild.log`.
The final runtime identities are:

| Runtime | Exact image ID |
| --- | --- |
| API, pandapower worker and PyPSA worker | `sha256:85f8c9ca57a086ec38a5fae922b4392051f2e439e17063c760813cb781e471f9` |
| Native Pi executor | `sha256:8b3b8908f4bfa93f6d1bf00d1fc970d890acbfc915420793312f96edae8da74d` |

All four services reported healthy. API `/health/ready` returned `ready` at
`http://127.0.0.1:8767`; the App was reachable at
`http://192.168.2.5:5173/`. Main `make doctor` passed. The merged input-control
check passed **16 tests in three files** before the layout fix; the final fix's
complete App suite covers that change. No paid Provider request was sent.

Actual Chromium checks used a new test Thread, `thr_382bc11e0b3c2b792aa7`, at
1280×820 and 390×844. The live catalog returned both delegated and professional
skills in Capstone mode, and the native skill in Pi mode. Context showed the
selected IEEE-39 identity and the truthful absence of complete network tables.
An explicit include choice and draft survived mode changes and page reload.
An incompatible skill remained visible, with a reason and disabled submission.
`/skills` plus Enter opened the picker without submitting a task. The final
page had zero console errors or warnings.

After removing temporary browser probe styles by reload, the final mobile
panel started at y=363.515 inside the thread's y=355.515 boundary. Its close
button passed a center-point hit test and an actual click. The same check
passed with an incompatibility warning present. Document width equalled the
390px viewport. Desktop skills/context layout remained usable. Screenshots
and snapshots are retained under ignored
`output/playwright/business-workspace-main/`; the named test browser was closed.

These actual main checks prove readiness and UI integration. Actual execution
with controlled model responses and real sample tools is the separate fresh
image proof above. Live model answer quality, complete business model exports,
cloud deployment and Case module expansion remain outside this acceptance.
