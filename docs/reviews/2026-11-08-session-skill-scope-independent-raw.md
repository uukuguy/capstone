# 独立评审报告：会话技能作用域（IG1）与"自由探索 / 按需帮助"设计

## 0. 评审对象、依据与限制

| 项 | 内容 |
| --- | --- |
| 基线 | `2badb1ee` |
| 被审实现 | `406c7d7b`（运行时 + App + 文档） |
| 文档头 | `d69c01a5` |
| 唯一依据 | 附件 `review-source-bundle.md`（207,532 字节，SHA256 `b64aa349…d81c96`），含六技能基线、`AGENTS.md`、框架架构、两份设计、实施计划、实现者报告、完整 diff、六个消费者文件带行号片段 |
| 评审角色 | 未参与本模块实现 |
| 未执行 | 未访问 MCP/业务源/互联网/主机仓库；未调用其他模型或代理；未修改实现、未部署、未运行 CI 或全量测试；仓库内测试未运行 |
| 已完成 | 附件全文分段阅读；纯本地有界语义复现（`repro/check.py`，内嵌被审纯函数源码 + 与 `thread_input.py:103` 同构的通行判定） |

行号约定：消费者文件行号取自附件给出的带行号片段；新增文件行号按 diff hunk 计数（新增文件 hunk 均自 1 开始，可信）。

**本报告不采纳实现者报告中的正确性结论。** 报告中"122 项 Python 通过、101 项 App 通过、镜像 `e68b1f92…`、两轮真实执行、PG 恢复"等均为人工陈述，既非当前运行观测，也不能替代代码判断；下文只把它当作"声称已覆盖的范围"用于定位验收缺口。

### 已核对的正确要点（先说清楚哪些站得住）

1. **能力目录 / 会话偏好 / 实际使用三者的记录确实分离**：目录在 `thread_input_catalog.py:43` 内联生成，偏好落在 Thread 行 `session_skills`，使用记录仍是 `investigation-skills.mjs:31-36` 的指令级 `capstone-skill-activity/1`。三者不共用字段，不存在"一次自动选择被写成用户偏好"的路径。
2. **授权不被偏好扩大**：`session_skill_preferences.py:26-36` 只接受 `role ∈ {direct_pi, delegated_pi}`、必须与当前 `runtime_mode` 推导出的角色一致、必须 `ready is True` 且 `version` 精确匹配；偏好文档只保留 `{id, version, role}`，不接受端点、路径等私有字段（`checked_preferences` 用"键集合严格相等"实现）。这是本包最扎实的部分。
3. **CAS 与幂等**：PG 侧先按 `idempotency_key` 命中即回放回执，再 `SELECT … FOR UPDATE` 锁 Thread 行、锁后重查幂等键，然后在锁内比较 `expected_revision` 并写事件 + 更新行（`thread_service.py:3560-3581`、`2917-2941`）。行锁 + 锁内比较等价于 CAS，未发现"丢失更新"路径。
4. **在途指令冻结**：`attempt.submission` 在准入时固化，测试断言第二轮把会话配置清到 revision 2 后，第一轮 attempt 仍持 revision 1（`test_session_skill_preferences.py`）。
5. **普通文本不会被偏好改写成技能调用**：`delegated_runtime.py:214` 的 `selected_input` 仍只取显式 `skill_invocation`，测试断言 `input.kind == 'text'`。

以下缺陷不影响上述结论，但 1、2 之外的部分存在阻断级问题。

---

## 一、确认缺陷

### D1（阻断，高）遗留输入 / 控制指令的"旧契约通行"被会话偏好条件化

- 位置：`packages/capstone-agent/src/capstone_agent/thread_input.py:103-104`（判定），`:118-133`（进入 `validate_submission` 后的取值与冻结）
- 触发条件：线程 `session_skills.revision > 0` 或 `skills` 非空，且收到的 `send_auto/send_ordinary/send_professional/send_control` 命令 payload 不含 `input/context_selection/resource_profile/context_product_refs/deep_research/llm_profile_id/excluded_session_skills` 任一键（旧版客户端、或 `send_control` 这类非输入型 payload）。
- 复现（`repro/check.py` A/B/C）：
  - 无偏好线程：仍 `return None, None`，走旧契约（True）。
  - 含偏好线程：不再走旧契约（False），流程进入 `validate_submission`；`payload['text']` 不存在 → `KeyError` → `InputRejected('input_invalid')` → 整条命令被拒。
  - 若 payload 恰好带 `text`，则会被"静默升级"为完整类型化提交（含冻结偏好与 `resource_profiles` 全表），行为与旧契约不同。
- 后果：一旦会话里保存过任一方法偏好，旧客户端/控制类命令在该线程上从"通行"变成"被拒或语义改变"。第 104 行注释"Existing clients retain their accepted legacy contract"在含偏好线程上已不成立。这是既有指令通道的回归，且属权限外的行为变化（偏好不应改变命令通行性）。
- 修正建议：把旧契约短路与偏好解耦——仅在"payload 不含类型化键"时保持 `return None, None` 不变，把冻结只挂在"存在 `input`（或 `text`）的命令"上；`send_control` 单独显式排除。补充"含偏好线程 + 遗留 payload / `send_control`"的用例。

### D2（阻断，高）偏好不可用时整条指令被拒，且只给出内部代码，缺"重选"通道

- 位置：`session_skill_preferences.py:33-34`（`session_skill_unavailable`）、`:49-58`（冻结失败）、`thread_input.py:125-132`（整体拒绝）
- 触发条件（均已被代码证实会阻断）：技能被停用/下架、版本被替换（`repro/check.py` G）、`runtime_mode` 从 `capstone` 切到 `pi_reference`（角色从 `delegated_pi` 变 `direct_pi`）、目录中该资源 `ready` 变 False。
- 后果：用户在该线程上**任何**消息都发不出去，返回的是 `session_skill_unavailable` 这类内部字符串，没有把"哪一条偏好失效、如何清除"作为结构化信息返回；设计中"新指令发现旧版本不可用时**明确提示重选**"只做到"拒绝"，没做到"提示重选"。这与"用户自由探索"直接冲突：一个可选的方法偏好把整个会话变成不可用状态。
- 修正建议：拒绝回执携带类型化原因（失效技能 id、当前偏好 revision），App 侧提供一键"清除失效项并继续发送"（原文保留在草稿/待重试命令中）；或对"本轮排除"失效采取忽略策略（见 D3），只对"实际被引用的偏好"硬失败。

### D3（中）本轮排除只按输入目录校验，服务端按快照校验，可发出后被整条拒绝

- 位置：`packages/capstone-app/src/threadInput.ts:31`（`inputDraftError` 只读 `catalog.session_skills`）、`ThreadCommandMenu.tsx:119-120`（排除项列表同样来自目录）、`thread_input.py:128-132`、`session_skill_preferences.py:51-55`
- 触发条件：另一标签页/另一设备改了偏好；或目录抓取之后偏好被改；或用户先清空偏好、草稿里仍留着 `excluded_session_skills`（`repro/check.py` E）。
- 后果：前端校验通过 → 发送 → `skill_exclusion_invalid` → 整条指令被拒，用户输入丢失在这次往返里。同一权威状态存在两份来源（目录副本 vs 快照），而校验用的是副本。
- 修正建议：前端同时以 `snapshot.sessionSkills`（权威）校验；`session_skills.revision` 变化时按设计"失效排除可清除，不静默变成另一种选择"主动清理并提示；服务端对"不在当前偏好内的排除 id"改为忽略（排除项只做收窄，不存在即无效果），仅在真正无法满足时硬失败。

### D4（中）保存冲突后组件不重新同步修订，重试必然再次冲突

- 位置：`packages/capstone-app/src/SessionSkillSettings.tsx:8`（`revision` 只在打开面板时从 `value` 取）、`:12`（`save()` 的 catch 只 `setError`，不回写 `revision`/`draft`）
- 触发条件：任何一次保存被 `skill_preferences_conflict` 拒绝（多标签页编辑、保存与别处修改竞争）。
- 后果：错误文案是"配置已变化，请刷新后重选"，但面板持有最新的 `value` prop 却不用；用户每次点"保存"都带着同一个陈旧 `expected_revision`，冲突无限循环，只能关闭面板再打开（复现 D：连续两次重试返回同一冲突）。组件测试 `SessionSkills.test.tsx:12-13` 恰好把"错误保留、勾选保留"固化为期望，未覆盖修订重同步。
- 修正建议：catch 中从 `value` 重新同步 `revision`（并给出"你的选择将被应用到最新修订"的明确提示，或展示差异后让用户确认），再允许重试；补一条"冲突 → 重试成功"的组件用例。

### D5（中）会话方法指引在显式选择 `harness_engine` 技能时仍被注入，指向本角色不可见的技能名

- 位置：`delegated_runtime.py:209-213`（无条件把 `method_guidance` 拼到 `instruction`）、`:226-230`（显式 `selected_input` 会把 `resource_profile` 覆盖为 `harness_engine`）
- 触发条件：`capstone` 模式 + 存在 `delegated_pi` 会话偏好 + 本轮显式选择 `harness_engine` 技能。
- 后果：执行器收到的指引里带 `delegated_pi` 侧的 `native_name` 与 `catalog_revision`，而该任务实际以 `harness_engine` 资源档案运行，`native_resources.py:269-270` 的 `allowedSkills` 不含这些名字 → 模型很可能调用 `agent_skill` 得到 `skill_not_admitted`，浪费一轮并产生"方法可用"的错误印象。这实质上让"偏好不扩大授权/不改变执行身份"在提示层被破坏（提示层宣称的能力超出授权）。
- 修正建议：仅在"实际执行角色 == 偏好角色"时注入；或在 `harness_engine` 分支按 `allowedSkills` 过滤后再注入，并显式说明"本轮以所选专业技能为准"。补一条该组合的用例。

### D6（中）严格快照解析令已持久化的会话在读取时不可恢复

- 位置：`session_skill_preferences.py:8-23`（键集合严格相等，抛 `ValueError`）、`thread_protocol.py:546-547`（`__post_init__` 内调用，未包装成 `ThreadProtocolError`）
- 触发条件：`capstone_threads.session_skills` 中出现任何额外/缺失键（未来版本加字段、人工修复行、`{}`、历史分支写入）。
- 复现（`repro/check.py` F）：`{'revision':3,'skills':[],'enabled':True}` → `skill_preferences_invalid`。
- 后果：`_snapshot_from_row` 构造快照时抛普通 `ValueError`，不是协议错误；线程变为不可读（HTTP 层会落到 500 一类），且没有"降级为 revision 0 + 隔离"的自愈路径。一个可选偏好字段的格式演化会把整个会话卡死。同一包内其它校验（如 `session_type`）用的是 `ThreadProtocolError`，错误分类不一致。
- 修正建议：读取路径用 `ThreadProtocolError`（或专门的 `SnapshotCorrupt`），并支持显式隔离/重置（保留原始字节与原因，供人工恢复），不要在只读路径抛裸 `ValueError`。

### D7（低-中）服务端接受"永不生效"的会话偏好，目录/偏好/实际使用对同一状态给出不同含义

- 位置：`session_skill_preferences.py:61-76`（`apply_preferences` 只校验归档/run/target/payload 与可用性）、`thread_service.py:1442-1457` 与 `2917-2941`（不校验线程是否具备原生执行）、`ThreadWorkAdapter.tsx:635`（`nativeChat && snapshot` 才渲染设置）
- 触发条件：在无原生执行（例如专业/grid 会话）或运行模式与本偏好角色不匹配的线程上提交 `set_session_skills`；或用户切换运行模式后偏好仍在。
- 后果：偏好被持久化并在目录中显示为"已启用"，但执行路径从不消费它；`session_skills_changed` 事件照样刷新界面。三件事（可用目录、会话偏好、实际使用）在数据上分离，却在语义上互相矛盾。
- 修正建议：在准入处拒绝不具备该原生角色的线程（回执写明原因），或持久化 `applicable:false + reason` 并在界面标注"当前会话不会应用"。

### D8（低）PG 与内存适配器回执不一致

- 位置：`thread_service.py:2936-2937`（PG 用 `{**parsed, 'run_id': snapshot.run.run_id}` 生成回执）对比 `:1452-1453`（内存直接用 `parsed`）
- 触发条件：命令 `run_id` 为 `None` 或与当前 run 不同（后者已被 `apply_preferences:64-65` 拒绝，但拒绝回执的 `run_id` 会被 PG 覆盖为当前 run）。
- 后果：同一命令在两个适配器下产生不同的回执文档；契约测试或客户端若比较回执字段会分叉，且 PG 回执掩盖了 `run_mismatch` 的原始 run 身份。
- 修正建议：两个适配器用同一构造方式生成回执，`run_id` 一律取命令原始值（或统一规定为服务端当前 run 并同步内存实现）。

### D9（低）冻结产物加入 submission 后未再计入容量

- 位置：`thread_input.py:89-90`（`validate_submission` 末尾按 `command_bytes` 规范化并截断校验）→ `:128` 在其**之后**追加 `session_skills`
- 触发条件：偏好数量与 id 长度接近上限（`context_references` 上限，单值 ≤256 字符）。
- 后果：`submission`（进而 `submission_snapshot` jsonb）可超出声明的命令容量；容量账目与实际载荷不一致。
- 修正建议：追加后重新做 `require_capacity('command_bytes', …)` 与规范化。

### D10（低）偏好文档缺少设计要求的"配置修订"和"启用/停用状态"

- 位置：`session_skill_preferences.py:43-46`（持久化只保留 `{revision, skills:[{id,version,role}]}`）
- 触发条件：任何一次保存。
- 后果：设计（`2026-11-08-adaptive-investigation-guidance-design.md` 技能作用域第 2 条）要求保存"技能 ID、选定版本、配置修订和启用/停用状态"，实现只保存前两项 + 自身修订：无法区分"从未选择"与"明确停用"，也看不出该偏好是在哪个目录/配置修订下通过校验的（只有冻结时的 `catalog_revision` 临时出现在指令侧）。这与 D6 的严格解析叠加后，后续加字段还会破坏旧行读取。
- 修正建议：要么补 `enabled` 与 `admitted_catalog_revision`（并让 `checked_preferences` 对未知附加字段保持可读），要么显式收窄设计文本，承认"删除即停用、目录修订只记在指令快照"。

---

## 二、设计待澄清

这些不是 IG1 的实现缺陷，而是设计文本本身尚不足以支撑机械可判定的实现（`AGENTS.md` 要求版本、归属、引用检查在代码中判定，而非依赖模型解释）。

**Q1（IG3）建议从哪来、走什么通道。** 设计说"取得有用发现后按需提供最多三项建议"且"不新增强制推荐模型调用"。但"建议"必须由某次模型输出产生：是助手消息里的结构块、独立成果、还是执行记录字段？没有类型化载体就没有"建议"这一对象，IG3 的"用户发送才执行/过期不误用"无从实现。需明确：生成时机（同一轮内联 vs 单独调用）、载体 schema、上限三条的强制位置。

**Q2（IG3）"范围修订"的键是什么。** 设计说"旧建议绑定范围修订，变化后标记失效"。候选键至少有五类：`model_context.selection_revision`、`attempt_id`、`session_skills.revision`、结果投影版本、IG4 的调查修订。不定一个（或一组有序）键，"失效"就只能是模型判断。同时要定义失效的**比较规则**（严格不等即失效？仅范围收窄也算？）和失效后的界面状态。

**Q3（IG4）调查状态由谁持有、如何与指令绑定。** 设计说"复用既有任务/研究记录，不创建平行账本"，但没说是 `Work`、研究任务图，还是新的调查记录；也没定义"同一调查跨指令延续 / 同会话其他问题不自动继承"的判定是显式绑定（用户点"继续该调查"）还是模型判断。若是后者，与"机械可判定"的总体要求存在张力。另需规定 `session_skills.revision`（会话级）与调查修订（调查级）两个独立修订的先后与冲突处理。

**Q4（IG2）欢迎页的"已知授权与连接信息"从哪读。** 现有 `input_catalog_document` 依赖 `ThreadSnapshot`（`thread_input_catalog.py:43`），而欢迎页处于 Thread 之前。需要 pre-thread 的只读投影（授权范围、已连接服务、可用技能角色的"是否存在"），否则"不自动扫描业务数据、不虚构可用范围"无法同时满足。另需定义示例来源（服务端目录 vs 静态）与"点击填草稿、保留已有草稿"的写入契约（当前草稿在受理边界被整体重置，没有"仅当为空才写入"的接口）。

**Q5 版本冻结的语义必须是内容派生。** `investigation-skills.mjs:6-7,27` 的版本是任务开始时的文件 sha256，并与任务内重读值比较——它能发现**任务内**内容变化，**不能**发现"偏好冻结之后、任务开始之前"内容被替换。因此跨指令的"精确版本与内容冻结"完全依赖目录里 `resource.version` 是否为内容派生值；若它是标签（如 `v1`），则"技能升级不静默替换"不成立。需在目录契约中承诺（或改为冻结内容哈希并在加载时比对）。

**Q6 "停用"的产品含义。** 删除即停用（当前实现）与"显式停用并保留审计"是两种不同保证，会影响 IG4 的"方向切换"叙述与用户预期。需二选一并写进设计。

**Q7 拒绝原因与"等待应用"状态。** 设计说"执行中修改显示已应用或等待应用"，但会话偏好是会话级、只影响下一指令，不存在"等待"态；而 D2/D3 的拒绝原因需要与界面文案一一映射。需定义：哪些修订冲突是"已应用"、哪些是"将应用于下一条指令"、哪些是"需要用户重选"。

**Q8 多标签页/多设备一致性。** `session_skills_changed` 已进入 `WORK_REFRESH_EVENTS`（`threadProjectionStore.ts:18`），但**输入目录**里的 `session_skills`（`thread_input_catalog.py:43`）是否随事件重取，包内没有证据：`ThreadWorkAdapter.tsx:640` 保存后只 `refreshWorkSnapshot()`。请明确目录刷新路径，并考虑把偏好修订作为目录内的独立字段，供 CAS 提示使用。

---

## 三、验收缺口

以下均不是"报告说通过、我判定失败"，而是"从代码与测试清单看，要求的场景没有被验证"。

| 编号 | 缺口 | 依据 |
| --- | --- | --- |
| G1 | 无条件化遗留契约的用例：无"含偏好线程 + 遗留 payload"、无 `send_control` 用例 | `thread_input.py:103`；`test_session_skill_preferences.py` 只发带 `input` 的命令 |
| G2 | 前端：保存冲突后的修订重同步、保存后输入目录 `session_skills` 刷新、排除项随修订失效清理，均无测试 | `SessionSkillSettings.tsx:8,12`；`SessionSkills.test.tsx` 只断言错误保留 |
| G3 | 运行模式切换（`capstone`↔`pi_reference`）导致偏好不可用的端到端用例缺失；`run_mismatch`/`thread_archived`/`skill_preferences_target_mismatch` 的界面映射未验证 | `session_skill_preferences.py:62-69`；`ThreadWorkAdapter.tsx:638` 只映射 `skill_preferences_conflict` |
| G4 | `harness_engine` 显式技能 + 会话偏好组合下的指引注入未覆盖（现有原生用例只覆盖 `pi_reference` 文本输入） | `delegated_runtime.py:209-230` |
| G5 | 拒绝码 → 用户文案映射仅实现了一条；其余 4 类用户会看到内部字符串 | 同 G3 |
| G6 | 冻结后容量核算与"最大偏好数"边界无测试 | `thread_input.py:89-90,128` |
| G7 | "实际使用记录引用所用会话配置修订"无字段、无测试 | `investigation-skills.mjs:31-36`；设计技能作用域第 5 条 |
| G8 | PG 恢复、两轮真实执行、镜像/内容身份均为人工陈述；仓库内只有单元/组件检查，且跳过的数据库项不计通过。关闭 IG1 前需一次可复跑（可审计）的 DB 用例 | 实现者报告"定向验证"段；`2026-11-08-session-skill-scope.md` 步骤 7 已勾选但不可复跑 |
| G9 | 界面验收：浏览器未连、键盘（Escape/焦点回退）、点击外部关闭、移动端均未验证；`aria-expanded` 无 `aria-controls`，弹出层是 `<section>` 而非对话框 | `SessionSkillSettings.tsx:13-18`；CSS `position:absolute`，无遮罩逻辑 |
| G10 | IG2–IG4 的度量（首次有用发现、首次可用成果、重复取数、等待时间、准确性）无埋点定义与数据来源 | 设计"分包与验收"末段 |

---

## 四、IG2–IG4 设计准备度（不作为 IG1 缺陷）

结论：**方向一致、可复用现有记录，但三个包各自的机械可判定契约尚未成形，暂不具备直接进入实现的条件。**

| 包 | 准备度 | 主要待补 |
| --- | --- | --- |
| IG2 新会话起步帮助 | 中低 | 欢迎页的授权/连接只读投影（Q4）；示例来源与"不覆盖既有草稿"的写入契约（当前草稿在受理边界整体重置，无"仅当为空写入"接口）；"帮我找一个探索起点"与"不新增强制模型调用"的关系（点击即填草稿，还是发起一次普通指令）；手机/键盘验收清单 |
| IG3 证据绑定建议 | 低 | 建议的类型化载体与生成时机（Q1）；范围修订键与失效比较规则（Q2）；发送后如何保留建议—证据关联（否则"证据绑定"在指令落库时就丢失）；三条上限的强制点 |
| IG4 调查连续性与纠偏 | 低 | 调查状态的持有者与指令绑定规则（Q3）；"旧返回不覆盖新范围"所需的按范围修订隔离键（当前只有 attempt 级冻结，没有范围修订）；失败/空结果/覆盖不足的保留与刷新恢复契约；与 `session_skills` 两个修订的先后与 CAS |

补充：三包都依赖"目录 / 偏好 / 调查状态 / 实际使用"四分离中目前唯一缺失的一层（调查状态）。IG1 只交付了后三层中的两层半，因此 IG4 需要先补状态模型，再做交互。这属于**后续包的准备度**，不是 IG1 的缺陷。

---

## 五、结论

**REQUEST CHANGES**

- 阻断项：D1（既有输入/控制通道回归）、D2（可选偏好把整条指令变成不可发）。
- 应在合并前修掉：D3、D4、D5、D6（同一权威状态双源校验、冲突死循环、提示层越权、读取路径不可恢复）。
- 可随后收尾：D7–D10。
- 关闭 IG1 前需补齐：G1–G8（G9 界面验收按项目约定另行执行；G10 属 IG2 起步）。
- IG2–IG4 的缺失已按用户指令不计入 IG1 缺陷，仅作为设计准备度评估（第四节）。

### 复现材料与限制

- `repro/check.py`：内嵌被审 `session_skill_preferences.py` 纯函数源码（去包内相对导入）与 `thread_input.py:103` 同构的通行判定，输出 A–G 七项结果；全部为纯本地、无网络、无仓库依赖。
- 未运行仓库测试、CI、浏览器；未观测运行时；未核验镜像/内容身份。
- 附件不含 App 端 `refreshWorkSnapshot` 是否重取输入目录的实现，故 Q8 按"待澄清"处理而非缺陷；同理 `send_control` 的真实 payload 形态未在附件中出现，D1 以"代码路径必然成立 + 后果取决于 payload 是否带 `text`"表述。
