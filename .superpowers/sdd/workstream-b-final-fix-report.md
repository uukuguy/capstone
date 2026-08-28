# Workstream B Final Review Fix Report

## Outcome

- Status: **DONE**
- Final release-source revision: `c146f5564220f622fedbbddd35b13696333d7534`
- Release-source tree SHA-256: `47fdb5d8b7df9de8fd7f624c5d55dc786eecf685853bedeccb47e4da14d8da20`
- Final climb run: `runs/climb/20260828T092537Z-b-h005`
- Final result: `100/100`, `release_ready=true`, no release blockers, session phase `complete`
- Provider validation: not run (not authorized and not required)

Every final-review finding was treated as a binding requirement. Each focused regression was first observed failing against the reviewed implementation, retained with the fix, and rerun before the repository gates.

## Finding Closure Matrix

| Finding | Commit | Closure | Focused regression / evidence |
| --- | --- | --- | --- |
| I-1 | `c5305c6` | Python publishes both secret-name controls and the grid wrapper translates the value into every generic spawn path, including the default extension. | `test_pi_launch_translates_custom_secret_name_for_generic_spawn_paths`; Node `default extension spawn removes a custom provider secret name` proves `LLM_ACCESS` is absent from the child environment. |
| I-2 | `1af029b` | `make setup-tools` explicitly installs the local owning Pi package after clean `npm ci`, without changing either lock; tarballs retain the exact installable `0.1.0` dependency. | `tools/test_source_setup.sh` starts without `node_modules`, checks imports and lock digests; independent dual-tarball install remains in `make test-packages`. |
| I-3 | `837b570` | `PiExtensionLocator` accepts only a verified source package or project-local installed npm package and rejects arbitrary env/repository fallbacks and symlinked package components. | Four locator tests plus the non-repository artifact gate run installed `grid-agent doctor`, offline envelope generation, extension loading, and descriptor registration. |
| I-4 | `3434fb4` | Kernel/generic persistence defaults are neutral and injectable; grid wrappers inject the legacy `grid-*` schemas/producer, preserving compatibility bytes and hashes. Kernel tests import only owning namespaces. | Neutral default tests, grid compatibility event tests, generic Node boundary scan banning all `grid[-_]`, and independent kernel suite (`121 passed`). |
| I-5 | `0d862de` | Production implementation imports owning namespaces; compatibility shims remain only at the exact public shim modules. | Full-production-tree checker, exact shim exemptions, and a non-CLI negative fixture. |
| I-6 | `08f7b99`, `c146f55` | The exact eight-field Task 7 transport API remains public; production materialization adds catalog, guide, workspace, turn, context, trajectory, acknowledgement, and runtime identity. Descriptor mode has no legacy supplement. A cross-process `question_id` lease fails closed before overwriting evidence. Scripted production-validation fixtures consume the same authoritative descriptor. | Exact-eight-field test, enriched descriptor test, descriptor/no-legacy tests in Python and Node, same-process and cross-process lease tests, and six scripted-Pi integration regressions (`6 passed`). |
| I-7 | `3fe07f2` | Python authority walks from a trusted root dirfd with per-segment no-follow opens, reads/fstats/digests the same fd, then verifies the named binding. Node guide uses per-component `O_NOFOLLOW` handles, same-fd reads and before/after fstat plus final named inode binding, without a realpath-then-reopen sequence. | Python leaf/parent symlink, cross-run, and deterministic exchange-race tests; Node leaf/parent symlink and binding tests. |
| I-8 | `9715cc7` | Carry-forward now requires the same release-source revision/tree binding; the final revision uses fresh receipts for every non-focused score. | Missing/wrong-revision carry-forward regressions and the five final non-focused receipts listed below. |
| I-9 | `9715cc7` | Receipts bind exact content-addressed paths, no-follow regular containment, clean source/tree digest, output digest, canonical receipt digest, HMAC key identity/signature, command, revision and rc. Manifest propagation retains all bindings. | Unsigned/manual JSON, receipt/output tamper, digest mismatch, leaf/parent symlink, dirty source and manifest-field regressions; local key is ignored, mode `0600`, and never appears in commands/logs. |
| I-10 | `9715cc7` | Evaluator executes only focused `make validate`; product compatibility scores 20 only with valid same-revision `doctor`, `test`, and `test-e2e` prerequisite receipts. Final manifest links focused output and all prerequisites. | Missing prerequisite returns zero; three trusted prerequisites score 20 without evaluator re-execution. Final run proves the complete chain. |
| I-11 | `069095a` | A versioned, expiring risk exception records the still-present 2 High/2 Moderate findings, attack surface, mitigations, owner, trigger, target upgrade and absolute expiry `2026-09-30`. The deterministic gate pins the vulnerable versions and rejects expiry or worsened risk. | `tools/tests/test_runtime_risk_exception.py`; `make test` and `make validate` both report the accepted bounded baseline. RUNBOOK and architecture docs reference the exception without claiming remediation. |
| M-1 | `1c95a18` | Generic subprocesses use bounded timeout/output defaults and hard maxima, kill on violation, cap stdout/stderr bytes, and return structured transport errors. Normal gridctl transport remains unchanged. | Node hang/timeout and oversized-output regressions plus the exact grid request compatibility test. |
| M-2 | `a14d60c` | Simulator contract tests narrow nested schema objects before indexing. | Pyright over every Python file modified since `b31bc3e`: `0 errors, 0 warnings`; `py_compile` also passed. |

## Final Trusted Receipts

All receipts are under `runs/climb/gate-receipts/c146f5564220f622fedbbddd35b13696333d7534/`, bind tree digest `47fdb5d8b7df9de8fd7f624c5d55dc786eecf685853bedeccb47e4da14d8da20`, and use attestation key id `db094ffbb5d61d633ceb3f1d`.

| Gate | Command | Receipt digest | Output SHA-256 |
| --- | --- | --- | --- |
| kernel_independence | `uv run --project packages/grid-agent pytest packages/capability-agent-kernel/tests -q` | `08a300f4e9e1361889ccd2e06e458d762820858e9541571ac12cacd0b83d953c` | `4f7bef9e451a656e5f22445c4fc84d6e8576bc847de21a06b29927ecbaa6af11` |
| domain_ownership | `make test-domain-package` | `46caf0c0d357cfa5056596820ee187a10b0a5e7e90ef7c48ba9d3b0e2507d9fa` | `1dcc70d9f511ed420adf087b63347322e33df78b92d53d4d49f4e013fd7ab037` |
| pi_tool_generalization | `npm test --prefix packages/pi-capability-tools` | `310d2b7c80068226fcd788aeafee66153684987f6374fdbe410aa86c25266a1d` | `68e20f8f66bd70c4f8c057b4bef191e03e9a859c2402dfc0af2600b75df3fecd` |
| application_thinness | `make check-package-boundaries` | `3514e16fd48afb17d89c751ebb787b853cde832286ffc0b00295f8b9e6446503` | `5e765302b10d658ad5c056dd71f78a20c1b5c8576d1614cfef1c3f63d764a66c` |
| distribution_integrity | `make test-packages` | `6f08c3515a7a7e1151f9d4f4d0f024328aaeac58376d005682aaa5fc41c2998e` | `4e9e5938a53c37ab337102a79663f1ce98519d73a34e3ce57cac0727e83b39c6` |
| doctor | `make doctor` | `31659bd6343f121a63362030646b4c997c273678ace3a5432396e2ece4ba0a5b` | `f20b63e2848db91520bb2a077a0c65a3345ed68e0c6c32f55378483ad9bdb1c2` |
| test | `make test` | `7ff6b4be04794fb5a4aaf422415d286cbb2be91bc9b66a401b7eda4f8487184c` | `24168d2a31a2d40e90855ae708a8603eb3e512228abcaec5fa3b81b0bb92adde` |
| test-e2e | `make test-e2e` | `e84c7bf5ea5848fe2892402cc103dfdf9be1116718c9e7fcdb4c138327de7b70` | `20b935d5bcc23df0b6053163176a5f23a5f55e4677580bc6011b3fb67b410755` |

The focused product gate output is `runs/climb/20260828T092537Z-b-h005/gate-output-product_compatibility.json`, command `make validate`, rc `0`, SHA-256 `5c283381b99e64448c813efd93ee621c2a01a104891186c86693fe650d1593f4`.

## Verification Summary

- `make doctor`: passed.
- `make test`: `651` grid-agent tests and `165` simulator tests passed; grid Pi Node suite `37/37`; bounded risk exception accepted.
- `make test-e2e`: `17 passed`.
- `make validate`: offline/scripted suites passed; capability matrix `24/24`, `release_ready=True`.
- Generic Pi Node suite: `13/13`.
- Independent kernel suite: `121 passed`, with no import of `grid_agent`.
- Pandapower domain package: `21 passed`.
- `tools/test_source_setup.sh`: passed from clean dependency state without lock mutation.
- `make test-packages`: four wheels and two npm tarballs installed in a non-repository project; installed CLI/extension smoke passed.
- Package-boundary checker, modified-file Pyright, `py_compile`, `git diff --check`: passed.
- `packages/capability-agent-kernel/uv.lock`: absent after all testing and receipt generation.

## Remaining Accepted Concerns

- Pi remains pinned at the reviewed version and its production dependency tree still has 2 High and 2 Moderate findings. This is an explicit bounded exception, not a remediation claim. It expires on `2026-09-30`; the owner must validate and adopt the target secure Pi release before then or the deterministic gate will fail.
- Node on macOS does not expose Python-style `openat(dirfd, ...)`. The guide reader therefore uses the smallest verifiable POSIX/macOS scheme available in Node: no-follow handles for every component, same-handle read/fstat/digest, and named inode binding. Python current-run authority uses true root-dirfd traversal.
- Upstream pandapower/pandas deprecation warnings remain non-blocking and do not alter current deterministic results.
