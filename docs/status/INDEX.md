# docs/status INDEX

## Active

dev默认开发集成主线和main发布主线均启用轻量保护：PR与两平台Actions检查、0审批，禁止强推和删除；main副本为发布快照。详见[组织设计](../superpowers/specs/2026-10-11-dev-integration-design.md)、[实施计划](../superpowers/plans/2026-10-11-dev-integration.md)和[版本台账](VERSION-CONTROL.md)。

[迭代门禁与旧 CLI 退出计划](../superpowers/plans/2026-10-11-retire-grid-cli.md)：513a35e已实现并审查门禁拆分；PR #10两平台CI通过，约32/26分钟并已合入main。用户已撤销grid-agent CLI兼容要求；共用运行模块迁移尚未完成。

[正式回答与运行窗口本地验收](../reviews/2026-10-11-task-answer-local-dev.md)：2473e48已在local-dev规范重建，三角色同源、注册案例和浏览器检查通过；PR #9已通过精确双平台CI并合并，人工回答验收及云发布单列。

[任务理解与正式回答实施清单](../superpowers/plans/2026-10-11-task-answer-closure.md)：契约、识别、领域覆盖与实际应用验收分别留存；当前源码2473e48，本地技术验收通过，主线集成及人工产品验收另列。

[研究模型演进计划](../superpowers/plans/2026-10-11-research-model-evolution.md)：本地技术基线B2已登记；feat/research-model从接受的dev50d8ebc建立，R1尚无代码；R0受控实验保留参考。R1研究模型、R2多轮连续性、R3自主推演、R4能力补齐、R5应用验收。未部署。

| File | Purpose |
| --- | --- |
| [项目推进控制全景](PROJECT-OVERVIEW.html) | 每次更新调用 ui-ux-pro-max 并重新排版验收；默认一屏，图标与标题同排，四环境绑定实际来源；demo 紧急修复直连已验收主线来源。Pi 包含业务数据共享，已合并分支退出主图。 |
| [线上到本地的功能范围核对](DEPLOYMENT-FUNCTION-SCOPE.md) | 功能与分支归属；近期需求遗漏核对和统一前端命令设计范围；现用执行账本仍必要，旧存储优化实验归档。 |
| [Git 分支清理记录](GIT-BRANCH-CLEANUP.md) | PR #6/#9/#10/#11合并后关闭分支名；本地目录、精确归档引用和日志保留；旧存储及R0实验未提交记录保留。 |
| `CURRENT-STATE.md` | Structural project snapshot. |
| [多线版本控制](VERSION-CONTROL.md) | dev保存当前控制记录，main保存发布快照；PR #9/#10/#11已集成，B2本地技术标签已推送，Research Model实施分支已建立；local-dev候选与精确来源见台账；授权Provider整体回归仍失败，PR #13修复复测中，demo/云端ed2524f，禁止提前人工交接。 |
| [GitHub Issues 与后台 AI 修复设计](../superpowers/specs/2026-10-10-github-issue-automation-design.md) | 已授权命令驱动实施：截图/短句反馈，默认 cloud-demo；当前 AI 会话中文处理，定时/无人值守与额外模型调用延期。 |
| [GitHub Issue automation plan](../superpowers/plans/2026-10-10-github-issue-automation.md) | 命令驱动工具已合入 main；小石 App 和独立发布已核对，后续准备 PR 待集成；无无人值守或额外模型调用。 |
| [并行开发运行准备](../superpowers/plans/2026-10-10-parallel-development-readiness.md) | 基础包已合并并关闭分支；当前计划同步了回答增强/Pi 归属、持续 PR 授权和独立发布验收；控制图与实际执行文件双向对齐。 |
| [Issue 工具验收](../reviews/2026-10-10-issue-workflow.md) | 源码审查、测试及真实 App 沙箱检查范围；区分已集成工具、待配置身份和未修复产品反馈。 |
| [Issue 处理规程](../architecture/capstone-issue-workflow.md) | 统一规范：当前 AI 会话按命令处理反馈、中文沟通、专用分支、双线验收及发布状态；不启用无人值守。 |
| [2026-10-11 Issue processing](../reviews/2026-10-11-issue-processing.md) | 独立App身份已核对；#1/#5待发布验收，#2/#3回答包处理中，#4受控诊断后等待一个触发信息；保持Issue打开，无云发布或付费模型调用。 |
| [Baseline alignment plan](../superpowers/plans/2026-10-10-version-baseline-alignment.md) | Preserve experimental development, restore minimal demo foundation and verify local-only alignment. |
| [Baseline alignment verification](../reviews/2026-10-10-version-baseline-alignment.md) | Main and isolated local-demo alignment passes full/local gates; six role identities match; experimental branches and user data retained; cloud unchanged. |
| `KNOWN-ISSUES.md` | Open answer-quality and startup/recovery issues; accepted branch policy and local baseline alignment, with cloud rollback retained. |
| [Demo outcomes and failure diagnostics](../superpowers/specs/2026-10-10-demo-outcome-and-diagnostics-design.md) | Approved design, implemented on main and demo baseline; remote acceptance pending. |
| [Demo outcome repair plan](../superpowers/plans/2026-10-10-demo-outcome-and-diagnostics.md) | Incident implementation and two-baseline verification; remote release remains gated. |
| [Demo outcome repair verification](../reviews/2026-10-10-demo-n1-repair-verification.md) | Confirmed defect, tested repair sources, local rebuild and explicit remote acceptance limits. |
| [Demo N−1 repair release](../reviews/2026-10-10-demo-n1-release.md) | Withdrawn 2ea2266 release and verified rollback to ed2524f; image identities, registered cases and retained evidence. |
| [Framework answer correction and local demo](../reviews/2026-10-10-framework-answer-local-demo.md) | Infrastructure and evidence-preservation checks pass; manual goal-based answer acceptance fails. Concise conclusions, scenario relevance and response scale require design. |
| [Shared intent and goal-answer draft](../superpowers/specs/2026-10-10-shared-intent-and-goal-answer-design.md) | 同一回答增强包；稳定源码接入核对已补，实施契约待收口。旧防护复用；来源接纳与普通/专业路由均不证明用户目标完成。 |
| [Business workspace and agent resources](../superpowers/specs/2026-10-09-business-workspace-agent-resources-design.md) | Pi 实验分支拥有既有角色/skills/MCP 原型及完整业务上下文与数据共享的剩余设计；计划 Tasks8–9 已对应落实，未宣称新功能完成。 |
| [Business workspace verification](../reviews/2026-10-09-business-workspace-resources-verification.md) | Offline gates, actual SDK/MCP/Authority integration, retained-resource checks and explicit acceptance limits. |
| [Intent/context local verification](../reviews/2026-10-08-intent-context-local-verification.md) | Semantic node, shared history and real Pi loopback evidence; actual model answer acceptance remains open. |
| [Common execution projection](../reviews/2026-10-08-execution-context-projection.md) | Shared ordinary/business boundary and general evaluation; diagnostic prose does not enter execution context. |
| [Conversation context design](../superpowers/specs/2026-10-08-capstone-conversation-context-design.md) | Active ordinary-answer design: shared dialogue, native Pi configuration and semantic request understanding; keyword routing rejected. |
| [Intent/context implementation plan](../superpowers/plans/2026-10-08-capstone-intent-context.md) | Approved design execution: interchangeable intent node, shared history, Pi adapter, hosted wiring and actual answer acceptance. |
| [Pi reference isolation design](../superpowers/specs/2026-10-08-pi-reference-isolation-design.md) | Deferred CONV-04 draft; actual Capstone ordinary-answer assessment and acceptance must precede review or implementation. |
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

- [Deployment answer acceptance repair](../superpowers/plans/2026-10-11-deployment-answer-acceptance.md): active priority; overall and update sample sets, captured real Provider failures, preacceptance repair and strict handoff states.
- [Deployment samples](../../validation/deployment/README.md): durable8-case/10-turn overall corpus and separate repair-specific criteria. Exact local-dev51f4715 passes real Provider10-turn screening and independent business review; three captured-proposal review probes and running/completed window checks pass separately. Latest outage Thread uses complete checks; filtered branch uses original failed-artifact replay and focused negatives. Historical failures retained. Await human verification; PR13 remains draft and no new baseline. Local checks do not wait for CI.

- [Autonomous research experiment](../superpowers/plans/2026-10-11-autonomous-research-experiment.md): user-approved experimental branch; two-layer knowledge/workflow/verification plus research nodes, IEEE39 four-case corpus, not deployed.
- [Asterion P7 reference](../reviews/2026-10-11-asterion-p7-reference.md): local source and recorded public results; reusable research mechanisms, Capstone boundary adaptations and evidence limits.

- [Task understanding and formal answer implementation](../superpowers/plans/2026-10-11-task-answer-closure.md): approved package implementation; contract, recognition, Pack coverage and actual local-dev acceptance remain distinct gates.

| File | Purpose |
| --- | --- |
| [Ordinary conversation local verification](../reviews/2026-10-08-ordinary-conversation-local-verification.md) | Empty-tool Capstone session, exact selection, loopback Pi RPC, real local capability prompt, current-source rebuild and complete offline release gate; external Provider and remote acceptance not tested. |
| [Capstone conversation completion](../superpowers/plans/2026-10-07-capstone-conversation-completion.md) | Active delivery worklist for gaps in the approved Thread/Harness/Web conversation contracts; CONV-01 covers one-time history folding and individual toggles. |
| [Opened grid models and current model](../superpowers/specs/2026-10-08-thread-open-models-design.md) | CONV-06 approved design: persistent nonempty model collection, current pointer, compact control and atomic close; locally implemented and verified. |
| [Opened models local verification](../reviews/2026-10-08-thread-opened-models-local-verification.md) | Durable model controls, closed-model historical replay, zero-tool access and instruction timestamps/grouping; independent review and cloud acceptance pending. |
| [Model work resume](../superpowers/specs/2026-10-08-thread-model-work-resume-design.md) | Approved continuation rule: stable member identities, saved per-model Context, separate historical views and restored camera; supersedes fresh Context on every switch. |
| [Model work resume plan](../superpowers/plans/2026-10-08-thread-model-work-resume.md) | CONV-06 continuity implementation and local acceptance plan. |
| [Model work resume verification](../reviews/2026-10-08-thread-model-work-resume-local-verification.md) | Local saved Context continuity, scoped follow-up history and actual browser camera/member checks; remote acceptance pending. |
| [Instruction model label verification](../reviews/2026-10-08-instruction-model-label-local-verification.md) | Instruction-owned model short names beside timestamps; historical association and responsive actual-entry checks. |
| [Folded answer cue verification](../reviews/2026-10-08-folded-answer-cue-local-verification.md) | Muted preview text and down/up toggle arrows with unchanged control geometry on desktop/mobile/landscape. |
| [Return current task verification](../reviews/2026-10-08-return-current-task-local-verification.md) | Explicit topology return restores current task and locates its own instruction while retaining draft, focus and folding. |
| [Thread history folding local verification](../reviews/2026-10-07-thread-history-folding-local-verification.md) | Revised history actions, new-answer full display, scroll/draft/copy checks and local acceptance; independent review and cloud release remain pending. |
| [Thread settings and instruction focus](../reviews/2026-10-07-thread-settings-and-instruction-focus-local-verification.md) | Unified useful Settings, subtle folded states and top/bottom instruction focus; current local browser/tests evidence and review/release limits. |
| [Thread system notices](../reviews/2026-10-07-thread-system-notices-local-verification.md) | Message-area errors and recovery, preserved reading focus and drafts; local checks with bounded client-notice limits. |
| [Distinct notices and global history anchors](../reviews/2026-10-08-thread-notice-and-global-anchor-local-verification.md) | Neutral system notices, stable consecutive history actions, no-op preservation and instruction/window-boundary checks; local acceptance only. |
| [Answer icon beside CAPSTONE](../reviews/2026-10-08-thread-answer-header-icon-local-verification.md) | Compact shared label/icon row, hover hints, retained mobile target and stable instruction/focus checks; local acceptance only. |
| [Compact grid-tool settings](../reviews/2026-10-07-thread-compact-grid-settings-local-verification.md) | Flat history/tool sections and public tool names; local UI checks, with unsupported all-off runtime explicitly blocked. |
| [Stable answer toggle](../reviews/2026-10-07-thread-stable-answer-toggle-local-verification.md) | Same-position collapse/expand, retained control focus and corrected final-reply scroll bound; supersedes forced instruction navigation. |
| [Registered tool/history menu correction](../reviews/2026-10-08-thread-tool-menu-local-verification.md) | All registered tool groups visible with compatibility reasons; two history actions without redundant heading/hint rows. |
| [M1–M11 status audit](../reviews/2026-10-07-capstone-m1-m11-status-audit.md) | Bounded milestone closures, deferred successor work and review-record limits; M6 must not be reopened from stale checkboxes. |
| [Capstone core evolution discussion](../superpowers/specs/2026-10-07-capstone-core-evolution-discussion.md) | Secondary research notebook; resume on user request or offer a reminder at an important boundary. Its open questions do not set delivery order. |
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

- [Domain Pack diff and content audit](../reviews/2026-10-11-domain-pack-sample-contamination.md): scope/completion/evidence repairs, generic instruction cleanup and continuous-overview repair; 8-case/10-turn overall and separate repair criteria under deployed verification.
