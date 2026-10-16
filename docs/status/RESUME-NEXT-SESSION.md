# Live Session Checkpoint

> Updated: 2026-10-16. Active-session recovery record.

## Accepted state

- Work identity slice055a335f local rebuild and integration now passed. API/dual workers share4a4c6fb7 image,1145 Git files/link targets match; ready/App055a335f and browser entry verified. Receipt runs/work-research-identity/local-identity.json. No Provider call. Commit report/control and open PR; verify both CI platforms before integration. Do not rerun old62f verification script (it compares stale source and dereferences links).
- ACTIVE IMPLEMENTATION: root branch feat/work-research-identity from dev d8e96652; code055a335f committed. Task 2 first slice adds WorkBinding/TaskContext, Work-owned AttemptResearch storage and Harness projection; not production Claim/Profile/v2/frontend. Report2026-10-16-work-research-identity.md and plan/register/control changes are uncommitted. Existing recovery JOURNAL/checkpoint edits must be preserved.
- Validation:44 identity/research tests;118 related suites before additional review tests; pyright3 source files zero errors. Full backend1332 passed/65 skipped with NO_PROXY/no_proxy=127.0.0.1,localhost. Initial5 HTTP test failures came from macOS system proxies (urllib detects them despite no proxy env vars);23 relay/server tests pass with bypass. Logs /tmp/capstone-work-identity-tests-clean.log and /tmp/capstone-work-identity-tests.log.
- Independent reviewer /root/review_pi_alignment found no blockers; requested negative and modelA→modelB/cross-run tests added. Canonical local rebuild running:session82555, log/tmp/capstone-work-identity-rebuild.log. Source055a335f. After rebuild verify actual file/image identity, ready and existing App; no Provider call or new UI acceptance. Then commit report/control, PR todev with dual-platform gates, integrate and sync app branches. Keep graph focused on new Work slice; retire old62f source card into history once no deployment references it. Do not claim allTask2 done.

- Latest dev:d8e96652, PR #40 accepted after CI38891823780 on both platforms. d4600ddc is now an actual dev-control graph node linked fromd8fe6e27, not merely a HEAD badge. Both application branches synchronized; Task 2 remains next. Prior control heads below are historical.
- Latest dev head:d4600ddc (PR #39, CI38890686246 Linux/macOS passed). Both preparation branches follow it. Historical control34cf695e and product integrated8fe6e27 now have explicit historical/milestone labels. The regenerated dev graph shows current HEADs separately. Task 2 remains next; no runtime change.
- Latest control update: PR #38 merged as261bbb07 after Linux/macOS CI38889782634 passed. Root and both application preparation branches now follow this dev head. AGENTS.md owns standing control requirements; the dev overview is regenerated after synchronization. Older34cf695e below is the preceding accepted control point.
- Root dev is34cf695e, including control PR #37 (Linux/macOS CI38886499201 passed). Product PR #36 merged asd8fe6e27 after CI38881419651 passed both platforms at711f06a8. Both merge trees match their tested heads.
- Task 1 execution seam and existing baseline are accepted. Implementation62f44366 provides final-argument provider admission;14 real SDK checks,57 tool checks,101 Python checks/1 skipped, and local check-integration passed. Independent review found a provider-method race; fixed and verified.
- local-dev canonical build711f06a8 ships source62f44366. API and both workers share imageae5adedf, each1142 shipped files verified. At verification App reported62f44366/dirty=false; readiness and an existing Thread browser entry passed. Receipts: runs/shared-execution-baseline/. No external Provider calls or cloud deployment.
- The new wrapper is opt-in. Production inventory/permissions/leases and continuous execution remain Task 3 work. The current native launcher remains one-prompt/in-memory. Task 1 is not new enterprise frontend acceptance.
- Main remainscf72393b (PR #30, accepted f209fb1 scope). Pi merged viaPR #31 intodb167184 and closed; detached worktreeabf2f797 and data remain. User e2eaee2 package,19173 installation, local-demo/cloud-demo and cloud-dev retain recorded sources.

## Branch and control state

- Both application preparation branches have no independent implementation and are fast-forwarded todev34cf695e. Confirm remote push completion if interrupted. Their owning plans/control copies are identical todev.
- feat/shared-execution-baseline and docs/shared-foundation-control are closed. Preserve archive refs, the detached Pi worktree and all existing data.
- The graph has16 nodes/22 edges;1280/1920 checks found no overlap, crossings, through-card paths or horizontal overflow. Shared foundation source sits right ofdev; centre occupied lanes and keep both sides visually balanced. Source edges remain exact.
- Ordinary control merges remain in history; the graph highlights product merged8fe6e27 and actual runtime source62f44366. Do not rebuild runtime or relabel it for control-only changes.
- Local JOURNAL/checkpoint edits are recovery records; stage only task-owned paths.

## Next implementation

- Active package: shared-agent. Canonical plan: docs/superpowers/plans/2026-10-16-enterprise-unified-execution.md, Task 2. Three-line sequencing: docs/superpowers/plans/2026-10-16-three-line-delivery.md.
- Deliver model-independent WorkBinding/TaskContext and Profile assembly through the existing Thread ledger. Task 2 includes v2 negotiation, object CAS, storage and minimum frontend adaptation. No fake default model for model-free tasks.
- Current AttemptResearch restores by thread/model. Work ownership requires explicit links without deleting/moving historical records. Existing ApplicationProfile/DomainRuntimeProfile assume professional components; professional checks stay in professional assembly.
- Actual integration points: thread_protocol.py; thread_service.py (memory and Postgres); thread_http.py; thread_application.py; attempt_research.py; kernel_pi_session.py; Kernel application/domain profiles; App threadProtocol.ts and existing transport/store/entry components. Read owning contracts before edits.
- Task 3 owns complete production tool inventory wrapping, authorization/lease/goal admission, persistent action receipts and continuous Pi integration.
- First visible milestone must provide URL, exact source, Profile/input prerequisites, expected result/source display and refresh/reconnect checks. Preserve conversation and professional entry behavior. Both application lines remain A1/B1 preparation until their specific dependencies run.
- Demo1/Demo2 are external examples, not built-in metrics, fixed workflows, special data APIs or required new solvers. Missing optional inputs/checks only block dependent work. Preserve Authority evidence and required persistence boundaries.

## Recovery references

- Reports: docs/reviews/2026-10-16-shared-execution-baseline.md and docs/reviews/2026-10-16-main-dev-convergence-verification.md.
- Original work backup: /tmp/capstone-pre-convergence-root-work.tar.gz. Recovery stash:a91a148494f520e973f5d63158916b42a5df6773. Preserve both and all var/data volumes.
- Git HTTP proxy may be needed:http://127.0.0.1:7897, HTTP/1.1, gh credential helper. Normal gh API works. Never force-push or bypass checks.
