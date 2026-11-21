# 持续任务上下文实施计划

目标是从自由 Instruction 到主会话自主交付，全程保持任务事实、用户指导和恢复位置。设计见[系统设计](../specs/2026-11-21-continuous-task-context-design.md)。技术基础为 Python、PostgreSQL、原生 Pi 执行器和现有 TypeScript App。

工作包 1–4 分别经 PR190–193 和 PR195 合入 dev。Mission 受检源码 `c91304d1` 通过真实混合和受控部分交付。工具配备已在隔离工作区验证预装使用、自主安装与无权限时继续独立工作。Goal 跨轮产物复盘修复和主会话呈现分别通过 PR196、PR197 合入。各项实施及 local-dev 验证进度见[版本台账](../../status/VERSION-CONTROL.md#功能包前沿)。

PR199 合入 Goal 历史产物续接。受检源码 `eea759ba` 的真实三步 Goal 自主完成，最终下载摘要匹配。PR200 合入显式 Mission 入口修复。PR203 修复 Goal 规划器自行增加派生数值条件的问题。受检源码 `65a8d56d` 规范重建后，真实同题 Instruction、三步 Goal、Mission 均交付，三份下载摘要一致。合入 `e959a65c` 的运行代码与受检候选一致。

每包先复用现有回归测试并记录基线，在对应模块补一个能复现缺口的失败用例，再实现、跑直接消费者的定向检查和真实入口，分别登记已实现、已验证及已合入。每包通过临时分支 PR 进入 dev。历史数据保持可读。部署单独记录。

| 工作包及依赖 | 负责人、实现入口与步骤 | 完成证据 |
| --- | --- | --- |
| 1　持久上下文，首包 | capstone-agent。在 native_task_context.py、task_handoff.py 及 Work/Attempt 的 PostgreSQL 事务中梳理现有字段。补全可选目标、原消息引用和中间恢复点。把版本与操作身份绑定到保存和消费。 | 从自由讨论开始，接受新增约束，旧会话刷新后读回同一版本；重复写入、旧版更新、空目标和旧记录均有测试。 |
| 2　Instruction 压缩与续作，依赖 1 | capstone-agent 与 Pi。沿实际原生执行器的压缩回调保存来源边界，装配下一轮时重载有效约束。扩展 task_handoff.py 的运行中恢复，区分接管、派生与回看。 | 真实长指令连续压缩两次，工具发出后中断，在新会话按原约束交付。核对调用次数、原文件摘要、晚到回执、两会话争用和目标授权缺失。 |
| 3　Goal 自主推进，依赖 1、2 | capstone-agent。在 goal_mode.py、session_goal_plan.py、goal_continuation.py 修改指导接纳、旁支暂停和归档。复用命令版本保护。扩展 test_goal_mode.py 与 test_session_goal_plan.py。 | 真实多轮 Goal 中插入改方向、缩边界、增校验的同一条消息；查询进度、插入独立指令、刷新、恢复并自主归档。旧复盘不得关闭新版本。验证完整及部分交付。 |
| 4　Mission 编排，依赖 3 | capstone-control 与 capstone-agent。在 mission.py、mission_reviews.py、mission_origin.py 记录组织者独自执行或各子委派的机制、依赖、授权及回执；将有效指导传播至受影响的委派。 | 同一任务分别走无子会话 Mission 和混合 Instruction/Goal 子会话 Mission。真实注入一个局部阻塞，独立子任务仍交付。核对汇总、恢复和用户停止后无新派发。 |
| 5　工具配备，依赖 1，随 4 联验 | capstone-agent。在 mission_equipment.py 和现有 managed-resource 入口核查已装、用户配置、自主安装三条路径，复用目录、授权、版本和回执。 | 用户已装工具直接使用；获授权时自动安装加载并实际使用；缺少授权时仅受影响步骤报告缺口。重试沿用原请求身份。 |
| 6　主会话全局呈现，随 1–5 分段交付 | capstone-app。沿 goalMode.ts、missions.ts、processCompactions.ts 和原会话组件扩展有界投影。把当前任务、旁支、指导影响、交付与校验接入原入口。 | 真实桌面和窄屏复用原标签页，从自由问答到刷新、查进展、指导、下载均可在主会话完成。检查旧会话阅读、输入草稿和操作焦点。 |

## local-dev 系统实施验收

- [ ] 以相同业务任务分别明确发起 Instruction、Goal 和 Mission。比对顶层机制、原始产物、已验证来源、用户最新指导与终态说明。验证过程中用户无需例行确认。
- [ ] 本机规范重建后复验 API、worker、App 的实际入口。记录源码、请求身份、实测耗时、回执、文件摘要及未满足项；凭据留在后端。

当前实施范围为 local-dev。Railway 已废弃。云端部署和用户试用属于独立发布工作。

实际 local-dev 已从 `7404a5cf` 规范重建，API 和 worker 同镜像并就绪。真实 Provider 的同题三入口均完成，三份下载文件逐字节一致。验收回执保存在 `runs/continuous-task-context/local-dev-7404a5cf/`。

PR207 修复接管保留和指导受短暂行锁影响的问题，并在接管续作入队时唤醒 worker。受检候选 `0c01a89d` 的常规和受控双行锁链路均真实通过，两个目标会话都读回了原任务的保存结果。

实际 local-dev 的合入版 `6dde7eae` 也通过受控双行锁接管。保留与指导在解锁后分别获准，指导只接纳一次。续作读回原任务的确切标记。回执保存在 `runs/continuous-task-context/local-dev-6dde7eae/`。

首个可执行切片为工作包 1 的“空目标自由 Instruction → 用户补充边界 → 关键点保存 → 刷新读回”。从该切片确定可复用的数据字段与最小迁移范围。
