# docs/status INDEX

## Active

| File | Purpose |
| --- | --- |
| `CURRENT-STATE.md` | Structural project snapshot. |
| [多线版本控制](VERSION-CONTROL.md) | 固定分支、公共修复、基线与标签规范、环境台账及 GitHub Issues 反馈流程；历史浏览待建 Issue，云端未更新；持续维护。 |
| [GitHub Issues 与后台 AI 修复设计](../superpowers/specs/2026-10-10-github-issue-automation-design.md) | 已授权实施：截图/短句反馈，默认 cloud-demo；中文自动沟通、命令/定时后台修复、双线验证和发布边界；在专用分支开发。 |
| [GitHub Issue automation plan](../superpowers/plans/2026-10-10-github-issue-automation.md) | Authorized implementation: controlled intake, Chinese communication, background repair-to-PR and shared lifecycle validation. |
| [Baseline alignment plan](../superpowers/plans/2026-10-10-version-baseline-alignment.md) | Preserve experimental development, restore minimal demo foundation and verify local-only alignment. |
| [Baseline alignment verification](../reviews/2026-10-10-version-baseline-alignment.md) | Main and isolated local-demo alignment passes full/local gates; six role identities match; experimental branches and user data retained; cloud unchanged. |
| `KNOWN-ISSUES.md` | Open answer-quality and startup/recovery issues; accepted branch policy and local baseline alignment, with cloud rollback retained. |
| [Demo sleep and App version acceptance](../reviews/2026-10-08-demo-sleep-and-app-version.md) | Accepted ed2524f/demo tag; exact cloud promotion, preserved history, per-page idle recovery and explicit live-traffic cold-timing limits. |
| [Cloud-dev App version acceptance](../reviews/2026-10-08-cloud-dev-app-version.md) | Accepted ed2524f/cloud tag; visible exact build identity, local dirty metadata, runtime alignment and release gates. |
| [Cloud-dev automatic sleep acceptance](../reviews/2026-10-08-cloud-dev-automatic-sleep.md) | Accepted 8b88af9/tag: real sleep with an open idle page, 20s first entry, 11s recovery, preserved workspace and small retained resource cost; demo unchanged. |
| `JOURNAL.md` | Append-only durable event log. |
| `RESUME-NEXT-SESSION.md` | Current recovery baton. |
| `INDEX.md` | This discovery index. |
| `DECISIONS.md` | Active architectural decisions, including PyPSA pack boundaries and the multi-binding direction. |
| `climb/research-tree.md` | Generated Workstream C inventory reference-domain scoring summary; resume-load. |
| `climb/session-state.json` | Active Workstream C hypothesis and deterministic next action. |
| `c2-github-repository-intelligence-candidate.md` | 🟡 historical GitHub C.2 candidate; PyPSA pack selection now governs the next approved design direction. |
| `2026-09-05-capstone-design-code-review.md` | Optimization evidence baseline R01–R13; current remediation status belongs to the canonical plan. |
| `2026-09-22-capstone-review.md` | 企业业务能力包视角的历史评审基线；后续修复和验收见优化计划。 |
| `2026-09-22-capstone-opensource-research.md` | 企业业务 API/framework 的历史选型研究；HTTP 测试实验已完成，其他候选仍待独立决策。 |
| `capstone-scope-cleanup-backlog.md` | 超纲实现清理候选、实际位置与风险；静态产物缺口已由7e9b10c补齐，当前不执行删除。 |
| `2026-10-01-capstone-m5-verification.md` | M5 provider-free 双 Authority 验证、完整 release 门禁与 clean-wheel 工件闭包。 |

## External execution anchors

| File | Purpose |
| --- | --- |
| [Capstone core evolution discussion](../superpowers/specs/2026-10-07-capstone-core-evolution-discussion.md) | Active long-term notebook for professional conversation, practical grid work, and continued Skill/tool integration; proposals and open questions are not an approved implementation plan. |
| [Thread client recovery design](../superpowers/specs/2026-10-05-thread-client-recovery-design.md) | Approved draft/receipt recovery and Context-bound rollback verification; cloud-dev acceptance precedes manual review and demo promotion. |
| [Network element name consistency](../reviews/2026-10-06-network-element-name-consistency.md) | Shared pandapower diagram/tool names, PyPSA name checks and visible type prefixes; local acceptance and historical replay limits. |
| [Topology name release](../reviews/2026-10-07-topology-name-release.md) | Exact-source cloud-dev and demo release checks for canonical names, display prefixes and hover status. |
| [Thread client recovery plan](../superpowers/plans/2026-10-05-thread-client-recovery.md) | Active local repair and cloud-dev acceptance work; demo deployment waits for manual acceptance. |
| [Thread recovery verification](../reviews/2026-10-06-thread-client-recovery-and-cloud-dev-verification.md) | Draft/receipt recovery, lease/configuration diagnostics and a1f028d cloud-dev evidence; normal Provider configuration blocks manual acceptance. |
| [Harness local verification](../reviews/2026-10-06-harness-provider-configuration-local-verification.md) | Shared188abe3 Provider configuration, adapter ownership guards and passing local App/release checks. |
| [Harness cloud-dev verification](../reviews/2026-10-06-harness-cloud-dev-verification.md) | All four services run188abe3; Provider-free checks pass, while missing worker credentials block ordinary AI conversation and manual acceptance. |
| [Thread session management plan](../superpowers/plans/2026-10-06-thread-session-management.md) | User-requested session controls, recovery and bounded conversation history; local App acceptance precedes cloud-dev. |
| [Thread session management verification](../reviews/2026-10-06-thread-session-management-verification.md) | Local and a2dbb5d cloud-dev acceptance for session controls, drafts and actual deployment recovery; ordinary Provider conversation and human demo approval remain blocked. |
| [Direct Thread entry and cloud Provider recovery](../reviews/2026-10-06-open-thread-and-cloud-provider-verification.md) | Current no-login entry, header correction and real PyPSA handoff/admission repair; local-first acceptance and cloud-dev Provider recovery evidence. |
| [Capstone optimization plan](../superpowers/plans/2026-09-05-capstone-optimization.md) | Canonical delivery record, including completed reviewed A–E work; strict JSON extension and OP13 deferred, no automatic C.2 or cleanup. |
| [Framework guide historical plan](../superpowers/plans/2026-08-31-capstone-framework-guide.md) | Completed architecture, bilingual README, and agent-contract documentation work. |
| [PyPSA pack and multi-binding design](../superpowers/specs/2026-09-25-pypsa-multibinding-domain-packs-design.md) | Approved four-pack boundaries, Network model reference, and multi-binding contract. |
| [Multi-binding implementation plan](../superpowers/plans/2026-09-25-multi-binding-application-implementation.md) | First code work package and later PyPSA activation order. |
| [PyPSA model-library design](../superpowers/specs/2026-09-26-pypsa-model-library-and-business-cases-design.md) | Official model asset boundary, runnable case scope, and presentation contract. |
| [PyPSA model-library implementation plan](../superpowers/plans/2026-09-26-pypsa-model-library-and-cases.md) | Local model library and scripted-case acceptance; container and frontend work remains deferred. |
| [Capstone framework](../architecture/capstone-framework.md) | Layer contracts, current-run evidence and guide-access assurance boundaries. |
| [Agent interaction discussion record](../superpowers/specs/2026-09-29-agent-interaction-discussion.md) | 🟡 Active discussion record for capstone-agent/harness, Thread/Run/Turn/Case, Pi/DSH runtime paths, model context, events, and three-pane App redesign; not an approved implementation spec. |
| [Web Thread UI primary contract](../superpowers/specs/2026-10-01-capstone-thread-web-ui-main-contract.md) | Approved Web conversation contract: typography density, assistant-ui structure, Markdown answers, activity summaries, Composer behavior, and visual acceptance gates. |
| [M6 Harness and Case design](../superpowers/specs/2026-10-02-capstone-m6-harness-case-design.md) | Approved Harness ownership, sequential Case execution, recovery, and public projection boundaries. |
| [M6 Harness and Case implementation plan](../superpowers/plans/2026-10-02-capstone-m6-harness-case.md) | Task-by-task implementation and verification plan; the lightweight Task 9 boundary closeout is recorded in the current-state and resume documents. |
| [M9 PyPSA result/Web projection](../superpowers/plans/2026-10-04-capstone-m9-pypsa-result-web.md) | PyPSA power-operation result projection into the shared Thread/Web contract; topology-specific presentation remains deferred. |
| [M10 PyPSA topology provider](../superpowers/plans/2026-10-04-capstone-m10-pypsa-topology-provider.md) | Registered-model topology projection into the unified Thread model pane. |

## Climb storage and configuration

| Path | Purpose |
| --- | --- |
| `climb/config.yaml` | Versioned Workstream C scoring policy, protected-path baseline, gate weights, and release closure. |
| `climb/session-target.md` | Machine-readable 100% Workstream C inventory reference-domain target. |
| `climb/hypotheses.yaml` | Append-only Workstream C inventory hypothesis state. |
| `climb/runs.csv` | Append-only Workstream C local score ledger. |
| `climb/calibration.json` | Local/online calibration state. |
| `climb/pending-lb.json` | Pending external score state; empty for local-gate mode. |
| `climb/adjudicator-log.md` | Append-only hypothesis decision record. |
| `climb/research-tree.json` | Machine-readable generated research tree. |
| `climb/_archive/2026-08-28-workstream-b-package-extraction/` | Completed Workstream B package extraction climb snapshot. |
| `climb/_archive/2026-08-18-full-capability/` | Completed 2026-08-18 full-capability climb session snapshot. |
