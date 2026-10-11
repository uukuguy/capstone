# Git 分支清理记录

日期：2026-10-10。范围：分支名和引用整理；未合并代码、未修改运行来源、未删除工作区或运行数据。

清理前逐个核对 Git 祖先、worktree 状态及 PR 状态。13 个分支已合入 main；CI 和历史修复已完整纳入基础修订分支；回答修复的两个名字指向同一提交。所有已移除的本地分支都有精确归档引用；7 个干净工作区转为 detached，仍保留原目录、提交和忽略文件。

| 原分支 | 提交 | 处理 |
| --- | --- | --- |
| `feat/business-workspace-resources` | `7fda5e9` | 归档 `refs/archive/20261010/feat/business-workspace-resources`；已纳入 `main` |
| `feat/github-issue-automation` | `25e75b1` | 归档 `refs/archive/20261010/feat/github-issue-automation`；已纳入 `main` |
| `feat/lean-test-boundaries` | `6f9f73c` | 归档 `refs/archive/20261010/feat/lean-test-boundaries`；已纳入 `main` |
| `feat/m11-cloud-thread` | `e128789` | 归档 `refs/archive/20261010/feat/m11-cloud-thread`；已纳入 `main` |
| `feat/pypsa-heat` | `6f42c85` | 归档 `refs/archive/20261010/feat/pypsa-heat`；已纳入 `main` |
| `feat/pypsa-modeling` | `a70ccff` | 归档 `refs/archive/20261010/feat/pypsa-modeling`；已纳入 `main` |
| `feat/pypsa-operations` | `a8dfd8c` | 归档 `refs/archive/20261010/feat/pypsa-operations`；已纳入 `main` |
| `feat/pypsa-planning` | `dee22f4` | 归档 `refs/archive/20261010/feat/pypsa-planning`；已纳入 `main` |
| `feat/pypsa-sector` | `597b7b3` | 归档 `refs/archive/20261010/feat/pypsa-sector`；已纳入 `main` |
| `fix/baseline-contracts` | `2540bdc` | 归档 `refs/archive/20261010/fix/baseline-contracts`；已纳入 `main` |
| `fix/local-demo-secret-ignore` | `a076b04` | 归档 `refs/archive/20261010/fix/local-demo-secret-ignore`；已纳入 `main` |
| `integration/demo-baseline` | `94cb5b2` | 归档 `refs/archive/20261010/integration/demo-baseline`；已纳入 `main` |
| `release/demo-baseline-1` | `a076b04` | 归档 `refs/archive/20261010/release/demo-baseline-1`；已纳入 `main` |
| `fix/ci-portability` | `bbc8811` | 归档 `refs/archive/20261010/fix/ci-portability`；已纳入 `feat/issue-operational-readiness` |
| `fix/issue-1-history` | `f0af011` | 归档 `refs/archive/20261010/fix/issue-1-history`；已纳入 `feat/issue-operational-readiness` |
| `fix/framework-answer-chain` | `3e3bbfb` | 归档 `refs/archive/20261010/fix/framework-answer-chain`；已纳入 `fix/demo-n1-outcome` |
| `feat/multi-binding` | `f004823` | 改名为 `archive/multi-binding-notes-20261010` |
| `feat/capstone-optimization` | `1c32c0a` | 改名为 `improve/context-segment-storage` |
| `fix/demo-n1-outcome` | `3e3bbfb` | 改名为 `archive/answer-chain-unaccepted-20261010` |

远端已移除 `fix/ci-portability`、`fix/issue-1-history`（对应 PR #7/#8 均 CLOSED）和 `docs/feedback-images-20261010`（已合入 main）。保留 main 与开放 PR #6 分支。未移动或重用任何验收标签。

`improve/context-segment-storage` 有约 1,100 行已跟踪代码/测试改动及未跟踪测试，尚未提交或验收；它不是已集成历史代码的重复分支。改名时逐项核对工作区状态前后一致。multi-binding 的未提交文档和 lock 文件全部保留。

恢复归档分支示例：`git branch fix/baseline-contracts refs/archive/20261010/fix/baseline-contracts`。归档 refs 保留提交对象；常规 branch 列表不再列这些历史名。完整操作收据位于维护者本地 `runs/issue-automation-acceptance/branch-cleanup-20261010.json`。

2026-10-10 整理后的记录包含分段上下文存储；该项的状态于次日更正并归档，见下节。

## 2026-10-11：旧存储实验归档

用户要求先确认旧任务的当前适用性，再同意归档。原 OP-13 计划已明确 DEFERRED；Kernel 文件日志机制仍在，但当前 hosted Thread 历史采用数据库，不能直接将旧压力问题视为当前 demo 缺陷。

本地分支 `improve/context-segment-storage` 改名为 `archive/context-segment-storage-20261011`。HEAD 保持 `1c32c0ae35219b11c6e2213a20379f8da1845349`；原 `.worktrees/capstone-optimization` 目录、10 项工作区状态及其文件摘要逐项相同，未删除数据或代码。恢复可在该工作区另建当前 main 的新分支，经适用性审查再提取旧实现；不直接续做旧设计。

当前活动代码为 main、基础修订包、Pi/skills 实验；4 条 archive 分支保留历史和参考代码。此次未移动标签、修改云端或合并代码。收据：`runs/issue-automation-acceptance/context-archive-20261011.json`。

## 2026-10-11：合并后关闭基础包分支

PR #6 已合并到 main `c3b78bc`，精确候选 `cfd6ad6` 的源码树与合并结果相同；候选检查和合并后 local-dev 验收通过。原分支工作区干净，没有未交付改动。

关闭本地及远端 `feat/issue-operational-readiness`。保留精确归档引用 `refs/archive/20261011/feat/issue-operational-readiness` 和原工作区；工作区转为 detached `cfd6ad6`，忽略的运行文件不删除。远端删除要求分支仍指向已验收 cfd6ad6，防止误删新增改动。PR、功能增量和验收记录留在主线 c3b78bc 节点，不保留孤立开发框。

恢复：`git branch feat/issue-operational-readiness refs/archive/20261011/feat/issue-operational-readiness`。当前活动分支为 main、任务理解与回答闭环、Pi/skills；旧回答参考未合入，不作为本次已合并分支关闭。

## 2026-10-11：dev建立与已合并分支关闭

PR #9 source2473e48、PR #10 source513a35e、PR #11 sourcecfa6c1c已分别通过
精确检查并合并。关闭本地及远端对应分支名；归档引用分别为
`refs/archive/20261011/feat-task-answer-closure`、
`refs/archive/20261011/chore-iteration-gates`、
`refs/archive/20261011/docs-project-state-sync`。
原回答与门禁工作区转detached，回答工作区新增日志保留；未删除目录或忽略数据。
远端删除前核对已合并PR及仍指向精确源提交，失败先核对再重试。

dev从main723b8e8建立，文档治理PR #11合入50d8ebc；main保持发布快照。
feat/research-model从接受的dev50d8ebc建立，隔离工作区为.worktrees/research-model。
旧R0、Pi和未合入参考分支均保留，不批量重写历史或合并实验。
收据位于runs/task-answer-closure/{dev-organization-merge,research-model-branch,baseline-b2-publication}.json。
