# Workstream B Final Review Fix Report

## Outcome

- Status: **DONE**
- Final release-source revision: `ea10df5a143eed6c11e3542618bb68fc42f792e2`
- Release-source tree SHA-256: `84b7dba2d69a00c4e87ca49b3f092091a7e920541eded47f59c6f16f6dca4c57`
- Release policy SHA-256: `efe8fc8e8ec02eee00ecb94d0b4e939985acf5c5ed4ac3ec76722dd813da4114`
- Final climb run: `runs/climb/20260828T104349Z-b-h005`
- Live closure SHA-256: `8f5924f291540374271362cc3fe8a76e80416694c4d0ffe8a0fbb0ee2596f6e1`
- Final result: `100/100`, `release_ready=true`, no release blockers, session phase `complete`
- Provider validation: not run (not authorized and not required)

Every original and re-review finding was treated as a binding requirement. Each second-round regression reproduced the reviewed failure before production code changed, remained in the suite, and passed before the repository gates. The final score comes from a fixed-policy live closure that reran all nine gates at the clean source revision; same-user HMAC receipts are integrity snapshots only and are not the release trust root.

## Original Finding Closure Matrix

| Finding | Commit(s) | Closure | Focused regression / evidence |
| --- | --- | --- | --- |
| I-1 | `c5305c6` | Python publishes both secret-name controls and the grid wrapper translates the value into every generic spawn path, including the default extension. | `test_pi_launch_translates_custom_secret_name_for_generic_spawn_paths`; Node `default extension spawn removes a custom provider secret name` proves `LLM_ACCESS` is absent from the child environment. |
| I-2 | `1af029b`, `fefe949`, `ea10df5` | Source setup uses frozen `npm ci` for both packages and the grid lock resolves the local owning package plus exact `pi-ai@0.80.6`; published tarballs retain exact installable `0.1.0`. | Clean no-`node_modules` setup checks every installed package against the lock and lock byte identity; the independent two-tarball installed-product gate also passed. |
| I-3 | `837b570`, `ea10df5` | `PiExtensionLocator` accepts only a verified source package or project-local installed npm package and rejects arbitrary env/repository fallbacks and symlinked package components. | Locator negatives plus the non-repository artifact gate run installed `grid-agent doctor`, offline envelope generation, extension loading, guide descriptor registration, and resource loading. |
| I-4 | `3434fb4`, `24fdc18`, `d59cb9a` | Kernel persistence stays neutral and policy-injectable; grid wrappers inject and runtime-validate legacy grid schema/producer identities, preserving compatible bytes/hashes while rejecting hash-correct foreign events. | Neutral kernel schema tests; grid native/imported model, reader, replay, and service foreign-identity negatives; independent kernel suite `121 passed`. |
| I-5 | `0d862de`, `d59cb9a` | Production implementation imports owning namespaces; compatibility shims remain only at exact public shim modules. | Full-production-tree checker, exact shim exemptions, non-CLI negative fixture, and regression caught/fixed for the legacy trajectory importer. |
| I-6 | `08f7b99`, `98e9ca3`, `c146f55` | The exact eight-field Task 7 API remains public; the production descriptor authoritatively binds catalog, guide, workspace, turn, context, trajectory, acknowledgement, and runtime identity. `question_id` is a bounded portable basename and each ID has one exclusive invocation directory, so active or sequential reuse fails closed without admitting stale evidence. | Descriptor/no-legacy tests, unsafe ID matrix, existing leaf/parent symlink tests, sequential stale-evidence test, same-process/cross-process lease tests, and scripted-Pi integration tests. |
| I-7 | `3fe07f2`, `5f54b38` | Python authority walks from a trusted root dirfd using per-segment no-follow opens and same-fd read/fstat/digest/named binding. Node binds the guide index digest/root in the descriptor and validates index and resource bodies with no-follow handles, same-fd reads, inode/root binding, and protocol/schema/resource checks. | Python leaf/parent symlink, cross-run, and exchange-race tests; Node index/resource leaf/parent symlink, index inode exchange, fake-root, and malformed mapping tests. |
| I-8 | `9715cc7`, `e11b9db` | No score carries stale or cross-revision results. The final closure reruns every score/prerequisite gate at one clean revision. | Missing/wrong-revision receipt regressions plus live `rerun-all-gates-v1` closure at `ea10df5`. |
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

## Final Live Closure Evidence

The immutable closure is `runs/climb/20260828T104349Z-b-h005/release-closure.json`. All commands returned `0`; every row is `closure-passed` and binds the same source revision, source tree, policy digest, stdout digest, stderr digest, and output digest.

| Order | Gate | Fixed command | Output SHA-256 |
| --- | --- | --- | --- |
| 1 | kernel_independence | `uv run --project packages/grid-agent pytest packages/capability-agent-kernel/tests -q` | `bb38e41a7b0595646d71106860f676075ff74b03152b794171876b539be334ab` |
| 2 | domain_ownership | `make test-domain-package` | `ed3481a3149a1288ce4d39cf19cfaf74f18488ab207d00cfac06696ed1f3e899` |
| 3 | pi_tool_generalization | `npm test --prefix packages/pi-capability-tools` | `37be762e5f75cd96bcdda0dd728895236afb32f3cfd50c3e57ade5f3e3689f1e` |
| 4 | application_thinness | `make check-package-boundaries` | `5df3cdd24bfc9087dcb1c685555c03e48182dfcb10d50e1113750c455c1c1cfe` |
| 5 | distribution_integrity | `make test-packages` | `477bafac34480159738e3c3d627f14b949d8570761be0d5c7f4a247516f316a2` |
| 6 | doctor | `make doctor` | `4b7dbae74aec7fa9c9208a72a1fe122ef2ad7f94e7320dd69b9203e889ded41e` |
| 7 | test | `make test` | `543668c5cb7a737a74d8b5f05772ef6f4d6040094920b1865199c43ea2bd9321` |
| 8 | test-e2e | `make test-e2e` | `7bbfb430c3c8856d82a349aca70bd9ada6bbe02b5b7a3c804f0ed8018a584671` |
| 9 | product_compatibility | `make validate` | `07b4715ff1f8bf567ff43f8c0e5b11730f58cf5e13a807cc6f349c49cc65a7b8` |

## Same-revision Integrity Receipts

Eight fresh receipts were also generated under `runs/climb/gate-receipts/ea10df5a143eed6c11e3542618bb68fc42f792e2/`. They bind tree `84b7dba2...`, policy `efe8fc8e...`, exact command/output/revision, and HMAC key id `db094ffbb5d61d633ceb3f1d`; their declared trust scope is `same-user HMAC integrity only; not a release trust root`.

| Gate | Receipt digest | Output SHA-256 |
| --- | --- | --- |
| kernel_independence | `9228cd75a1c149ea0c4846e2bebb1cf1b54c03971190f0619f15652339a53a29` | `65f9eda6ec7b32d765f29ac4eeba9842956fc1998b100e92a483d576f76c2894` |
| domain_ownership | `4d5ee5f6e2ef4a58dd444400d84a61fb79554efca5c6f7d2c2a48da01575df64` | `07275da32e909b72a4d8f6dedd7f47a7a78141b9d841b628fbdb02cde1660583` |
| pi_tool_generalization | `0394531572074cc29a47994cd28c3cd9d7bfbffc81faf5c3151140c311792cde` | `4438d05db60e1b34cd0bd074055e18140562bff63a75555f355652771213116c` |
| application_thinness | `5d5dcd4e587b8f2ca97c5c1e13a5e4f7e826f6852e850206f2b5d9f701742e4e` | `5e765302b10d658ad5c056dd71f78a20c1b5c8576d1614cfef1c3f63d764a66c` |
| distribution_integrity | `b9fe61fd5f67b282709bc6d60b2227a06cf62792cf9c5756af3d8982f4fe3c29` | `61222f02abb732affdb42c825715a0201b6b368a6fc705dbfbef85e298a3a4bf` |
| doctor | `43ab06aa1377f55422b75e5907bd3f0e1f5b11e2be2f397173283e4784b4b891` | `f20b63e2848db91520bb2a077a0c65a3345ed68e0c6c32f55378483ad9bdb1c2` |
| test | `d0350ab68b67dd07673a845d6a25b35706a3f987f9fb46e7baa162aeae188e9c` | `e83fb93925b60d60257b9c203693cf3318e91327c93b7036a0521b0eb13f8d41` |
| test-e2e | `dd94b28733068722d76dba51bdbe86012844b9972bdeb4b5ddaea522f60d42a5` | `861055279bec213fefb7e3a4c7870a1a311d1966d766526a571715d0becad613` |

## Verification Summary

- `make doctor`: passed.
- `make test`: `679` grid-agent tests and `165` simulator tests passed; grid Pi Node suite `43/43`; bounded risk exception accepted.
- `make test-e2e`: `17 passed`.
- `make validate`: offline/scripted suites passed; capability matrix `24/24`, `release_ready=True`.
- Generic Pi Node suite: `13/13`.
- Independent kernel suite: `121 passed`, with no `grid_agent` import.
- Pandapower Domain Pack: `21 passed`.
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
