# Workstream B Final Review Fix Report

## Outcome

- Status: **DONE**
- Final release-source revision: `e41783558afb57eb04ad04562c7d9b0fe6e6bf0b`
- Release-source tree SHA-256: `9ff57149f3f03f7b3e223768738ca24bea9906b4427269e95709432600410ad9`
- Release policy SHA-256: `efe8fc8e8ec02eee00ecb94d0b4e939985acf5c5ed4ac3ec76722dd813da4114`
- Final climb run: `runs/climb/20260828T111922Z-b-h005`
- Live closure SHA-256: `5049c057d9ca3283661465f57b0626da95dd79e562e71d73385c86b7261cb247`
- Final result: `100/100`, `release_ready=true`, no release blockers, session phase `complete`
- Provider validation: not run (not authorized and not required)

Every original and re-review finding was treated as a binding requirement. Each review-round regression reproduced the reviewed failure before production code changed, remained in the suite, and passed before the repository gates. The final score comes from a fixed-policy live closure that reran all nine gates at the clean source revision; same-user HMAC receipts are integrity snapshots only and are not the release trust root.

## Original Finding Closure Matrix

| Finding | Commit(s) | Closure | Focused regression / evidence |
| --- | --- | --- | --- |
| I-1 | `c5305c6` | Python publishes both secret-name controls and the grid wrapper translates the value into every generic spawn path, including the default extension. | `test_pi_launch_translates_custom_secret_name_for_generic_spawn_paths`; Node `default extension spawn removes a custom provider secret name` proves `LLM_ACCESS` is absent from the child environment. |
| I-2 | `1af029b`, `fefe949`, `ea10df5` | Source setup uses frozen `npm ci` for both packages and the grid lock resolves the local owning package plus exact `pi-ai@0.80.6`; published tarballs retain exact installable `0.1.0`. | Clean no-`node_modules` setup checks every installed package against the lock and lock byte identity; the independent two-tarball installed-product gate also passed. |
| I-3 | `837b570`, `ea10df5` | `PiExtensionLocator` accepts only a verified source package or project-local installed npm package and rejects arbitrary env/repository fallbacks and symlinked package components. | Locator negatives plus the non-repository artifact gate run installed `grid-agent doctor`, offline envelope generation, extension loading, guide descriptor registration, and resource loading. |
| I-4 | `3434fb4`, `24fdc18`, `d59cb9a` | Kernel persistence stays neutral and policy-injectable; grid wrappers inject and runtime-validate legacy grid schema/producer identities, preserving compatible bytes/hashes while rejecting hash-correct foreign events. | Neutral kernel schema tests; grid native/imported model, reader, replay, and service foreign-identity negatives; independent kernel suite `121 passed`. |
| I-5 | `0d862de`, `d59cb9a` | Production implementation imports owning namespaces; compatibility shims remain only at exact public shim modules. | Full-production-tree checker, exact shim exemptions, non-CLI negative fixture, and regression caught/fixed for the legacy trajectory importer. |
| I-6 | `08f7b99`, `98e9ca3`, `c146f55`, `5ef46c5`, `e417835` | The exact eight-field Task 7 API remains public; the production descriptor authoritatively binds catalog, guide, workspace, turn, context, trajectory, acknowledgement, and runtime identity. Unsafe `question_id` input still receives the exact single-JSON stdout error contract. Valid IDs get exclusive invocation directories, while the lease authority securely opens/creates `.grid-agent/run-leases` from the trusted project dirfd, so active/sequential reuse, symlinks, and exchanges fail closed without stale or external evidence writes. | Descriptor/no-legacy tests, parameterized CLI invalid-ID envelope tests, exact successful stdout bytes, workspace parent/leaf symlink and exchange-race tests, same-process/cross-process lease tests, and scripted-Pi integration tests. |
| I-7 | `3fe07f2`, `5f54b38` | Python authority walks from a trusted root dirfd using per-segment no-follow opens and same-fd read/fstat/digest/named binding. Node binds the guide index digest/root in the descriptor and validates index and resource bodies with no-follow handles, same-fd reads, inode/root binding, and protocol/schema/resource checks. | Python leaf/parent symlink, cross-run, and exchange-race tests; Node index/resource leaf/parent symlink, index inode exchange, fake-root, and malformed mapping tests. |
| I-8 | `9715cc7`, `e11b9db` | No score carries stale or cross-revision results. The final closure reruns every score/prerequisite gate at one clean revision. | Missing/wrong-revision receipt regressions plus live `rerun-all-gates-v1` closure at `e417835`. |
| I-9 | `9715cc7`, `e11b9db` | Receipt paths/digests/no-follow containment remain protected, but same-user HMAC is explicitly only an integrity check. Final trust comes from a fixed command/pathspec/weight/prerequisite policy included in the release digest and an execute-all closure with read-only output chain. | Dirty source/config, command weakening, path narrowing, weight/prerequisite/order mutation, same-user re-signing, manual closure, output/tree/revision/digest, and symlink/path forgery negatives. |
| I-10 | `9715cc7`, `e11b9db` | Product compatibility is the focused `make validate` gate and receives 20 points only after the same live closure has passed `make doctor`, `make test`, and `make test-e2e`. The evaluator does not execute caller-selected commands or accept carry-forward evidence. | Fixed nine-gate order regression; final manifest links the product output and all three live prerequisites with policy/tree/stdout/stderr/output/closure digests. |
| I-11 | `069095a`, `fefe949` | A versioned exception records the still-present 2 High/2 Moderate findings, attack surface, mitigations, owner, upgrade trigger, target secure Pi release, and expiry `2026-09-30`. The deterministic gate checks the pin, both locks, and the actual installed graph. | Risk tests reject expiry, pin/lock/installed-graph drift, and a worsened declared baseline; source setup proves the checked graph is the supported graph. No claim is made that existing vulnerabilities disappeared or that the static gate discovers future advisories. |
| M-1 | `1c95a18` | Generic subprocesses have bounded timeout/output defaults and hard maxima, kill on violation, cap stdout/stderr, and return structured transport errors. | Generic Node hang/timeout and oversized-output regressions; exact grid request compatibility remains unchanged. |
| M-2 | `a14d60c` | Simulator contract tests narrow nested schema objects before indexing. | Pyright over every Python file changed since `b31bc3e`: `0 errors, 0 warnings`; `py_compile` also passed. |

## Re-review Closure Matrix

| Re-review finding | RED reproduced | Fix / acceptance |
| --- | --- | --- |
| Important 1 / I-2 | Clean source installed `pi-ai@0.80.10` while the reviewed lock required `0.80.6`. | `fefe949` converted source setup to frozen local-file locks and added exact actual-versus-lock graph verification; source and tarball gates pass without lock mutation. |
| Important 2 / I-4 | A hash-correct `foreign-product/9.9` event entered the grid trusted prefix. | `24fdc18` added fail-closed native/imported grid policy validators while retaining neutral injection; `d59cb9a` restored the owning import boundary. |
| Important 3 / I-6 | `../outside-runs`, absolute IDs, symlink targets, and sequential reuse escaped or inherited stale evidence. | `98e9ca3` added strict basename/length/character validation plus exclusive no-follow invocation roots and retained cross-process leases. |
| Important 4 / I-7 | Replacing the guide index after startup exposed an outside resource. | `5f54b38` descriptor-binds index digest/root and performs startup and execute-time no-follow, same-fd, named-binding validation; fake roots and replacement races fail closed. |
| Important 5 / I-9 | The repository user could read the HMAC key, re-sign a forged result, or weaken excluded gate policy. | `e11b9db` includes the complete scoring config/policy in the release digest and makes B-H005 rerun a fixed allowlist of all gates. HMAC is no longer described or consumed as an independent trust root. |
| Minor 1 | State/report claimed release readiness based on the earlier receipt-only chain. | This final state commit replaces the claim with the successful live-closure evidence and records the exact remaining Pi/security limitations. |

## Third-round Regression Closure

| Regression | RED reproduced | Fix / acceptance |
| --- | --- | --- |
| A — invalid-ID CLI envelope | Traversal, absolute, separator, and 129-character IDs exited before the unified handler with zero stdout lines and a raw validation exception. | `5ef46c5` moves request construction inside the unified handler. Five parameterized cases now emit exactly one parseable JSON line with exact `question_id`/`answer_output` keys, preserve the supplied ID, put the explicit limitation in `answer_output`, keep diagnostics on stderr, and emit no traceback. The normal successful stdout byte string remains exact. |
| B — lease-root symlink/race | A symlinked `.grid-agent` caused lease directories/files to be written outside the project; deterministic `.grid-agent` and `run-leases` exchanges after open were accepted. | `e417835` opens the trusted project root, creates/opens both components relative to dirfds with `O_NOFOLLOW`, retains the same fds, and verifies named device/inode bindings before use. Parent/leaf symlinks and both exchange races fail closed with zero external-target changes; active and sequential lease semantics remain unchanged. |

## Final Live Closure Evidence

The immutable closure is `runs/climb/20260828T111922Z-b-h005/release-closure.json`. All commands returned `0`; every row is `closure-passed` and binds the same source revision, source tree, policy digest, stdout digest, stderr digest, and output digest.

| Order | Gate | Fixed command | Output SHA-256 |
| --- | --- | --- | --- |
| 1 | kernel_independence | `uv run --project packages/grid-agent pytest packages/capability-agent-kernel/tests -q` | `e01e2d004c79500b2849751803aa41081edf3e7c02424992d6133cec92c496af` |
| 2 | domain_ownership | `make test-domain-package` | `8e7db299c6ff6e15a212a608f8621a06c4a5596ab4853e79272ad99482a1ff01` |
| 3 | pi_tool_generalization | `npm test --prefix packages/pi-capability-tools` | `27ef5e26c7b54d9e64eb0beaf13deaf9076e9a43d4d77f6b8bbbe6a634d3750c` |
| 4 | application_thinness | `make check-package-boundaries` | `5df3cdd24bfc9087dcb1c685555c03e48182dfcb10d50e1113750c455c1c1cfe` |
| 5 | distribution_integrity | `make test-packages` | `84221fce52cca86ce792a6006319b96e7ebb577c94792fb1ffae9884facdb95d` |
| 6 | doctor | `make doctor` | `4b7dbae74aec7fa9c9208a72a1fe122ef2ad7f94e7320dd69b9203e889ded41e` |
| 7 | test | `make test` | `6a2705a1c0611a60996de17fbe71fc0a8a69876410ba58b0db6158d6ba347d97` |
| 8 | test-e2e | `make test-e2e` | `11ffc01f60fc8b5d0d1791b8c27f863e62c170d2395daeb749729d6e0f374675` |
| 9 | product_compatibility | `make validate` | `07b4715ff1f8bf567ff43f8c0e5b11730f58cf5e13a807cc6f349c49cc65a7b8` |

## Same-revision Integrity Receipts

Eight fresh receipts were also generated under `runs/climb/gate-receipts/e41783558afb57eb04ad04562c7d9b0fe6e6bf0b/`. They bind tree `9ff57149...`, policy `efe8fc8e...`, exact command/output/revision, and HMAC key id `db094ffbb5d61d633ceb3f1d`; their declared trust scope is `same-user HMAC integrity only; not a release trust root`.

| Gate | Receipt digest | Output SHA-256 |
| --- | --- | --- |
| kernel_independence | `1f9891ab922be22f2c81d0e5df2195191dfd3098bc4936591e460045f7a6082d` | `8abb341c4b98d4c2edcbb2d89cd33a7b5958420ed4d343961c3539c86fabf7da` |
| domain_ownership | `8dc53b85f7eda7c4851d7526edc2c3334c8b168f533133dd916f626c040cf968` | `4226566629cd786ff58a6e685274bbde29f634570bb13084962ce7a60279b602` |
| pi_tool_generalization | `f9c7f8aae9910fa79199651f178e9b69a065db2e3f93e1810735465aa6ac0e2f` | `0a32d3a1ed46e34a88544b7d044b5ca93b7bd0cb66fc7c017609181eb85cd332` |
| application_thinness | `265fe2ff08991d2d1fffdb3e7d016b6741d96c068243f76f4da77b673ed2dcd5` | `5e765302b10d658ad5c056dd71f78a20c1b5c8576d1614cfef1c3f63d764a66c` |
| distribution_integrity | `52843110d8d51295072d084caa6f4aeac1b8560b573c36e1d5ee2571be5fd0c6` | `c8fc0868091b550dd0a0c094734158161feee465dee7a9a7738550ff2a7000ae` |
| doctor | `ae1fa537bc17545c65b20e0e5b56a5350a5941baf5e7f88218735175046cb170` | `f20b63e2848db91520bb2a077a0c65a3345ed68e0c6c32f55378483ad9bdb1c2` |
| test | `f67737feae1a82e349f63cfbd1a46cdde640b3e7d2ed164a224f8b53ef0747bb` | `408740027fe9b88afaa35c777aa2d1e234713fd39efa3713ae06607e747f7a71` |
| test-e2e | `3ee01551f500238b54eba228086fbe793624467afd5574404259e77706d4ab53` | `c5181f3471e13e418a7614306ea2f00a2d9451d902a6aa2d4dc996063f1566d2` |

## Verification Summary

- `make doctor`: passed.
- `make test`: `688` grid-agent tests and `165` simulator tests passed; grid Pi Node suite `43/43`; bounded risk exception accepted.
- `make test-e2e`: `17 passed`.
- `make validate`: offline/scripted suites passed; capability matrix `24/24`, `release_ready=True`.
- Generic Pi Node suite: `13/13`.
- Independent kernel suite: `121 passed`, with no `grid_agent` import.
- Pandapower Domain Pack: `21 passed`.
- Third-round focused workspace/CLI suites: `30 passed`; five invalid-ID cases and four lease-root cases were observed RED before their fixes.
- Climb adapter/closure tests: `41 passed`, including 10 live-closure adversarial cases.
- `tools/test_source_setup.sh`: clean frozen install passed, all actual versions matched the locks, exact `pi-ai@0.80.6`, lock bytes unchanged.
- `tools/test_package_artifacts.sh`: four wheels and two npm tarballs installed in a non-repository project; installed CLI/offline/extension/descriptor/resource smoke passed.
- Package-boundary checker, runtime-risk checker, modified-file Pyright, `py_compile`, and `git diff --check`: passed.
- Eight receipt commands and the subsequent nine-command live closure passed at the same source revision.
- `packages/capability-agent-kernel/uv.lock`: absent after all testing and evidence generation.

## Remaining Accepted Concerns

- Pi remains pinned at the reviewed version and its production dependency tree still has 2 High and 2 Moderate findings. This is an explicit bounded exception, not a remediation claim. It expires on `2026-09-30`; the owner must validate and adopt a secure Pi release before then or the deterministic gate will fail. The static gate detects supported-graph/pin/lock/declared-baseline drift; it does not discover a future advisory against unchanged versions.
- Node on macOS does not expose Python-style `openat(dirfd, ...)`. The guide reader uses the smallest verified POSIX/macOS Node scheme: descriptor-bound root/digest, no-follow handles for every component, same-handle read/fstat/digest, and named inode binding. Python current-run authority uses true root-dirfd traversal.
- The live closure is a reproducible local verification chain, not a claim that artifacts are unforgeable by the same OS user. A distinct CI/controller signing boundary remains the option if remote third-party attestation is later required.
- Upstream pandapower/pandas deprecation warnings remain non-blocking and do not alter current deterministic results.
