# Main/dev convergence verification

Status: both product PRs merged after Linux/macOS checks passed. Local-dev rebuilt and verified.

## Accepted scope

The user selected `f209fb18d7abb122b689e1b1a52c54fa13bf5371` for the main release baseline.
It includes the phase-complete conversation application and verified PyPSA fixes.
PR #30 merged as `cf72393bd6377d1de11d02a93728cdaa746a75d4` after Linux/macOS
release run 38861900687 passed. The merge tree matches f209fb1 exactly. The release
branch is closed. The existing e2eaee2 user package is not replaced.

PR #31 merged into dev as `db16718445fb33ea242310076dd068b90b1996a6` after
Linux/macOS run 38865540607 passed. Its merge tree matches the tested source
exactly. The former Pi branch is closed; its detached worktree and data remain.
The tested source is
`abf2f797c98f953a402aa25597018d6d5dfea0af`. Native/delegated execution and versioned
resources are implemented. The unified continuous loop, model-optional v2 protocol
and new workbench remain design work. Pi is the executor ecosystem, not a permanent
product branch.

## Local evidence

All `check-pr` targets completed across the initial run and focused continuations.
The remaining existing CLI and Makefile entry tests also completed with exit 0,
covering the additional `make test` targets.
`check-integration` completed with exit 0. Counts include:

| Scope | Result |
| --- | --- |
| Formal pandapower application | 938 passed, 3 skipped |
| Existing CLI | 997 passed, 3 skipped |
| Simulator | 244 passed, 2 skipped |
| Backend after timeout fix | 1304 passed, 65 skipped |
| App | 512 passed |
| Kernel | 628 passed |
| Domain Pack | 143 passed |
| Generic tools | 82 passed |
| Deployment entry contracts | 61 passed |
| Installation and data compatibility | 207 passed |
| Registered resource/build regression | 17 passed |
| Workbench | 156 passed |
| E2E | 39 passed |
| Registered workers | 3 passed |

The offline/scripted validation and application-instantiation suites passed.
The published pandapower coverage check reports 24/24. These checks do not establish
new Provider answer quality, cloud acceptance or completion of the enterprise design.

## Failures investigated

- The macOS proxy affected local HTTP fixtures. Process-scoped `NO_PROXY` and
  `no_proxy` for localhost restored the expected direct connection.
- Inherited `GRID_AGENT_LLM_PROVIDER` and `GRID_AGENT_LLM_MODEL` changed the
  missing-key test's precondition. Unsetting those two variables for the test
  process restored the intended missing-key check. Credentials were not printed.
- The data descriptor rejected the registered capstone-pi resource link. Commit
  `46a1bf74` admits only its exact registered target, hashes its identity and content,
  and keeps filesystem/archive descriptors consistent. Unsafe links remain rejected.
  The expanded digest is not evidence that an old data format is compatible.
- A test wrote a receipt non-atomically while the consumer polled it. Its fixture
  now uses atomic publication, matching the actual host. Production admission was
  not relaxed.

## Local candidate environment

The canonical rebuild passed at abf2f797. The first attempt stopped at Docker Hub
authentication before replacing services. Existing process-scoped proxy settings
restored access on the second attempt. API, both workers and general-pi are healthy.
API and both workers share image
`sha256:d6acc8c04b04f9153d59bffa41c8a223119bfe24d2edadb1a117fe30136e2fd1`.
Each backend role matches 1139 shipped files against the candidate source. The
image label remains development; the receipt uses file digests, not that label.
App5173 reports abf2f797, dirty=false, local-dev, and loads the existing Thread.
All five existing volume identities match before/after. Counts remain 769 Threads,
815 attempts, 120476 events, 40 sessions and 156 session artifacts. Doctor passed.
Receipt: `.capstone-agent/convergence-local-identity.json` (ignored operator evidence).

The first PR #31 macOS run exposed HTTP timeout misclassification. Commit abf2f797
preserves TimeoutError for both HTTP timeouts and the total deadline, with parent
checkpoint precedence and unknown remote state unchanged. Four deterministic
regressions first failed; 65 delegation tests and 1304 backend tests then passed.
Independent review found no required changes. The fresh exact-head CI run 38865540607 passed on both platforms.

## Integration and control

Both PRs merged through the normal protected-branch process, without bypass.
The root checkout is on dev. The release and Pi branches are closed locally and
remotely. Recovery ref `refs/archive/20261016/feat-pi-skills-integration` retains
abf2f797. The pre-convergence stash and worktree data remain intact.

The register and graph show the accepted main baseline, the dev integration,
and exact deployment sources separately. Control-only updates do not rebuild or
relabel the verified local runtime. App source is abf2f797; repository revision
tracks the dev checkout. The new enterprise design remains pending implementation.

No Provider call, cloud deployment or user-installation replacement is authorized
by this verification record. Existing deployment sources remain separately recorded.
