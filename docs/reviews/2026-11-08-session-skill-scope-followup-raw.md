# 会话技能作用域：R1–R5 修正独立复审

结论：**REQUEST CHANGES**。
R1、R2、R5 的代码级修正基本成立并有可复现证据；R3、R4 的界面恢复路径成立。
但 R1 的**决定性执行点**（原生 SDK 侧技能发布）不在所给源码内，无法据此宣称“排除已实际限制 native 加载”；
另有 4 项可从完整源码证明的行为缺口（其中 2 项为合同/健壮性，2 项为用户可见的错误归类与文案）。
本轮未修改运行代码、未安装依赖、未运行测试套件、未使用网关/外网/子代理。

## 1. 复审来源、范围与方法

- 唯一被审材料：用户上传的会话材料（约 805 KB，10900 行），内容为 Dockerfile、计划、设计合同、
  实现源码、定向测试、前端组件与测试，以及上一轮独立评审文本。
- 方法：`wc`/`rg` 定位章节后分段读取；在隔离工作区把 `session_skill_preferences.py` 原样抽出，
  配一个仅含 `limits.context_references`/`require_capacity` 的最小桩模块，做纯函数探针（不联网、不装包）。
- 明确未覆盖：完整 Python/前端测试套件、真实 PostgreSQL、浏览器实页、真实模型执行、CI 与部署。
- 判断原则：只写能从所给完整源码证明的行为（含函数级探针）；源码缺失处以“未知”标注，不用推断补位。

## 2. R1–R5 处置结论与证据

| 项 | 状态 | 证据（所给源码行号） |
| --- | --- | --- |
| R1 排除进入执行合同 | **部分解决（执行链证明到 store 边界，SDK 边界未知）** | 见 2.1 |
| R2 内容身份固定 | **已解决（含 1 项硬化缺口）** | 见 2.2 |
| R3 失效偏好的针对性恢复说明 | **已解决（文案层）；服务端拒绝码回传未验证** | 见 2.3 |
| R4 冲突后显式重新同步 | **已解决（含 1 项建议）** | 见 2.4 |
| R5 已接纳草稿比较含排除字段 | **已解决** | 见 2.5 |

### 2.1 R1：排除信息确实进了 direct/delegated 两条路径

已证明的传递链（同一份源码、单一路径）：

1. 输入构造：`threadInput.ts`（10448、10454）把 `excluded_session_skills` 放进 `InputSubmission`，
   仅在有值时携带；`validSkillExclusions` 做去重/长度校验。
2. 发送：`CapstoneAssistantThread.tsx:9224` 的 `metadata` 携带条件已包含
   `inputDraft.excluded_session_skills?.length`，修掉了上一轮“只有排除、没有其它显式输入时 metadata 丢失”的
   direct 模式确定路径；对应测试 `CapstoneAssistantThread.test.tsx:5431–5435` 覆盖 pi_reference。
3. 准入冻结：`thread_input.py:5138–5147` 在 `revision` 为真或载荷含排除字段时调用
   `freeze_preferences`，冲突（显式技能=`skill_invocation` 且被排除）立即
   `InputRejected('session_skill_selection_conflict')`。
4. 提示词：`session_skill_preferences.py:96–106` 当 `skills` 与 `excluded` 同时为空才返回空串；
   探针 A 复现：冻结值 `{revision:1, skills:[], excluded:['method']}` 时 `method_guidance` 仍非空且含 `method`
   ——上一轮“排除后提示为 `''`”的问题消失。
5. 任务文档：`delegated_runtime.py:577–584` 用 `execution_scope(submission)` 生成 `skill_scope`
   （`capstone-session-skill-scope/1`，含 revision/skills/excluded），`pi_delegation.py:4090–4097、4136–4138`
   校验并序列化；`PiTaskRequest.from_document → to_document` 往返保真（测试 5403）。
6. 原生加载前：`native_resources.py:3790–3798` 在 `task_config` 里调用 `scoped_skill_names`，
   用当前接受的资源声明把排除 ID 映射为 native 名并与 `allowedSkills` 求差；探针 H 复现
   `allowed=['sample','gateway']` + 排除 `method` → `['gateway']`。
   同时 `scoped_skill_names:148–149` 对“显式选择被排除”在原生边界再次拒绝（探针 I →
   `session_skill_selection_conflict`），不只依赖准入。

**仍未闭合的部分（证据缺口，不是已证明缺陷）**

- `resources/general-sdk.mjs` 未包含在材料中。`allowedSkills` 是否真被 SDK 用于**技能发布/加载**，
  还是仅作为工具层提示，无法从所给源码证明；`native_resources.task_config` 仍把完整 settings
  （含被排除技能目录）交给原生侧，`test_native_skill_scope_enforcement` 只断言了
  `allowedSkills` 列表（5364–5366），没有任何断言覆盖“被排除方法在原生侧不可加载”。
  因此上一轮 R1 的核心要求“在原生加载边界执行，不能只靠提示”目前只证明到 store 计算层。
- `ThreadCommandMenu.tsx`（计划 217 行声称在此加入本轮排除）与 `threadWorkProtocol.ts`
  （`buildSendMessageCommand`）都不在材料内。本轮排除是否**存在用户可达控件**、命令 payload 是否
  真的透传该字段，属于未知；现有前端测试是直接写 `sessionStorage` 草稿绕过控件。

### 2.2 R2：选择时内容身份已固定，旧指令按自身冻结目录恢复

- 保存时固定：`revise_preferences:43–55` 用 `_available` 取当前 `loaded_identity` 与
  `catalog_revision` 并回写；客户端自带 `loaded_identity` 且与当前不同则 `session_skill_content_changed`
  （探针 D 复现，说明无法把任意身份钉进偏好）。
- 准入时核对：`freeze_preferences:66–75` 对每个未排除技能重新取当前身份并比较，不同即拒绝
  （探针 C：同标签 1.0 + 内容 a→b → `session_skill_content_changed`）；无关目录修订变化不替换内容
  （测试 5404–5410）。
- 加载时核对：`scoped_skill_names:142–147` 校验 `version/ready/loaded_identity` 一致，否则拒绝。
- 旧三字段偏好：`freeze:69–70` 要求重新选择；被排除时允许通过（测试 5346–5348），与设计
  “旧方法可读可移除、不自动确认当前内容”一致。
- 旧指令恢复：`execution_scope:123–137` 对无身份的旧冻结项**只**用 `submission['resource_profiles']`
  （该指令自身的目录快照，`thread_input.py:5058–5060` 落盘）解析，不回退当前会话目录，符合
  “旧指令只可从自身已冻结的目录恢复内容身份”。

**硬化缺口（见问题 3.1）**：`revise_preferences` 把“缺 `loaded_identity`”当作“按当前内容重新绑定”。

### 2.3 R3：文案层已补齐

`threadFeedback.ts:10350–10355` 新增
`session_skill_unavailable`、`session_skill_content_changed`、`session_skill_reselect_required`、
`session_skill_content_unavailable`、`session_skill_selection_conflict`、`skill_exclusion_invalid`
六条，均含“未执行/输入内容已保留/重选或排除”要素；`threadFeedback.test.ts:10146` 对其中四条做断言。
草稿保留路径成立：发送失败只抛出 `CommandRejectedError`，输入框文本不走清空分支
（`CapstoneAssistantThread.tsx:9208–9231`）。

未知：`admission_submission` 返回的 `(None, code)` 如何成为命令回执的 `rejection`（`thread_service.py`
不在材料内，且材料中没有任何调用点），因此“服务端确实回传这些码”未验证。

### 2.4 R4：有显式重新同步，且不静默改写旧选择

`SessionSkillSettings.tsx`（9307–9344）新增 `onReload` 与“读取最新配置”按钮：冲突后只报错，
必须用户点击才 `setDraft(latest.skills)/setRevision(latest.revision)`，保存按钮仍用本地 revision，
不会把旧选择偷偷 rebase 到新修订；组件测试（9352–9374）覆盖“冲突 → 未自动 reload → 显式 reload →
再次提交使用 revision=2”。另补 Escape 关闭、焦点回触发器、外部点击关闭。父级 `onReload`
（10012–10018）先 `refreshWorkSnapshot` 再读 `inputCatalog`，返回最新 `sessionSkills`。

建议（非阻断）：reload 直接覆盖本地未保存勾选、未展示“本地选择 vs 最新配置”差异；上一轮建议保留
本地选择与差异，当前实现选的是“清空重选”。

### 2.5 R5：已接纳草稿比较已含排除字段且与顺序无关

- 统一投影：`threadInput.ts:10463–10467` `composerSubmission` 只保留 composer 自有字段并固定键序
  （含 `excluded_session_skills`），`sessionSkills.test.ts:10104–10115` 覆盖“保留排除、剥离
  `attachment_refs`”。
- 重建侧：`ThreadWorkAdapter.tsx:9747` 用 `composerSubmission(payload)` 重建
  `acceptedDraft.submission`，不再手工挑字段，排除字段因此保留。
- 比较侧：`CapstoneAssistantThread.tsx:8724–8734` 两侧都用同一投影后 `JSON.stringify` 比较，并单独
  比较 `deep_research`（`composerSubmission` 已含该键，此处为冗余但无害），键序稳定；
  `resolvedCommand` 守卫 + `commandId` 变化才执行，保证“只清理一次”。
- 测试 5436–5451 覆盖“带排除的已接纳请求 → 清理 → 后续编辑保留”。

## 3. 可从所给源码证明的问题

### 3.1 P2 保存接口接受“无内容身份”的重绑定，同标签内容变化可被静默接受

- 位置：`session_skill_preferences.py:43–55`（`revise_preferences`，判断 `if skill.get('loaded_identity') and ...`）。
- 触发：客户端对**已存在**的偏好再次保存，但请求里的技能项只有 `id/version/role`（旧App缓存包、
  脚本客户端、或任何不发送身份的调用方），而当前发布内容已更换。
- 影响：探针 E 复现——保存内容 A 后目录换成同版本内容 B，再提交 `{id,version,role}`，
  `revise_preferences` 返回 revision 2 且 `loaded_identity` 变为 B，无任何提示。即“技能升级不静默替换”
  在这条路径上仍依赖客户端自觉带上身份；服务端没有“旧ID必须带身份或显式确认”的规则。
- 建议：对已存在同 `id` 的条目，缺失 `loaded_identity` 时按“旧三字段偏好”处理——要么要求身份，
  要么要求显式 `reselection` 标记；或至少比较客户端 `catalog_revision` 与当前一致。
  当前正式面板（9326）总会带身份，故属纵深防御缺口，非现存 UI 故障。

### 3.2 P2 已接纳指令在原生边界被判内容变化时，用户得到“AI 配置未就绪”而非重选指引

- 位置：`native_resources.py:3790–3798` → `scoped_skill_names:142–147` 抛 `session_skill_content_changed`；
  `general_pi_server.py:3191–3203` 的 `except (ValueError, KeyError)` 只覆盖请求解析阶段，
  `task_config` 在受理（202）之后的执行线程内调用。
- 触发：指令准入后、原生任务开始前，该角色已接受资源快照与冻结身份不一致（重新发布/重建后重放、
  角色不匹配等）。
- 影响：该失败落在任务失败通道，`threadFeedback.ts` 的 `attemptFailureCopy`（10377–10386）
  没有 `session_skill_*` 码，`harness_failed`/`runtime_configuration_invalid` 文案是
  “AI 配置未就绪，请联系管理员”。用户看到的是配置故障，而不是 R3 承诺的“哪项方法失效、如何重选”。
- 建议：把这类身份不一致在执行前（准入/派发）转成命令拒绝并复用 R3 文案；或在
  `attemptFailureCopy` 增加 `session_skill_content_changed`/`session_skill_unavailable` 的针对性说明，
  并标注“草稿已保留、请重选方法”。

### 3.3 P2 只要存在会话偏好，缺 v2 任务合同或缺业务上下文的执行会硬失败，且归类错误

- 位置：`delegated_runtime.py:577–584`
  （`skill_scope` 非空但 `'input' not in task_fields` → `HarnessRuntimeConfigurationError`）；
  `task_fields` 只在 `context is not None` 且任务 schema 含 `capstone-pi-task/2` 时填充（563–575）；
  `pi_delegation.py:4090–4097` 亦要求 `skill_scope` 必须伴随 typed input。
- 触发：会话已保存偏好（此后每条指令都会生成 `session_skills`），而该尝试缺少业务上下文，
  或原生执行器不声明 `capstone-pi-task/2`。
- 影响：`HarnessRuntimeConfigurationError` 走 `runtime_configuration_invalid` →
  “服务的 AI 配置未就绪。请联系管理员检查配置”。这是用户无法自救的错误归类：真实原因是
  “本执行器不支持技能作用域扩展”，而合同本身允许降级（提示词层面的偏好完全可以不带 `skill_scope`）。
- 建议：按“不假设旧执行器支持该扩展”的本意，缺 v2 时**降级**为仅提示词偏好并记一条诊断事件；
  若坚持硬失败，需专用错误码与“本会话技能需要新版执行器，请移除会话技能或新建会话”的文案。

### 3.4 P3 `execution_scope` 对缺少 `excluded` 键的历史冻结值抛 `KeyError`

- 位置：`session_skill_preferences.py:137`（`'excluded': frozen['excluded']`）。
- 触发：`submission['session_skills']` 只有 `{revision, skills}`（本轮之前的实现写入的已接纳指令）。
- 影响：探针 F 复现 `KeyError: 'excluded'`；这是未分类异常，在 `_general_task` 内抛出后不可能得到
  R3 文案。是否仍有此类历史行属未知（材料未含迁移/回放数据）。
- 建议：`frozen.get('excluded') or []`，并对旧形态显式按“无排除”处理或给出可诊断的拒绝。

### 3.5 P3 排除按“已保存偏好 ID”受限，且按 native 名做集合差会牵连同名资源

- 位置：`session_skill_preferences.py:63`（`set(excluded) <= {已保存偏好 id}`，探针 B →
  `skill_exclusion_invalid`）；`scoped_skill_names:150–152` 用 `native_name` 集合求差。
- 影响一：目录中可用但未保存为偏好的方法无法被“本轮排除”，只能先保存再排除；设计文案
  “本轮排除优先于会话偏好”未说明该限制。
- 影响二：探针 H 复现——若两个技能声明共用同一 `native_name`，排除其一会把另一个也从
  `allowedSkills` 移除（多排除，不是漏排除）。
- 建议：合同明确“排除仅作用于会话偏好条目”；`blocked` 改为按声明自身身份（id+version+identity）
  精确匹配，或在 `confirm_loaded` 阶段保证 `native_name` 唯一。

### 3.6 P3 新增原生镜像依赖已随镜像分发，但缺少构建期导入冒烟

- 位置：`deploy/general-pi.Dockerfile:161` 新增 `COPY ... session_skill_preferences.py`；
  指纹清单 `general_pi_server.py:3469` 已包含该模块（与 `native_resources.py` 并列），
  `tools/tests/test_image_layer_order.py:15–40` 会因缺失 COPY 而失败。
  依赖闭包可核对：该模块只 import `copy/json` 与 `.application_capacity`（第 55 行已 COPY）。
- 缺口：镜像内的 `RUN python -c "from capstone_agent.general_pi_executor ..."`（第 172 行）不导入
  新模块，也没有其它构建期断言；若该模块语法/导入或 `limits.context_references` 缺失，
  只会在真实任务 `task_config`（`native_resources.py:3790`）时首次暴露。
- 建议：把 `python -c 'import capstone_agent.session_skill_preferences'`（或一次
  `scoped_skill_names` 纯函数调用）加入该 RUN；成本近零，能把“新原生依赖坏了”变成构建失败。

## 4. 三类概念是否被正确区分

- **会话偏好**：独立于目标与活动，存 `snapshot.session_skills`（revision+skills），
  仅 `set_session_skills` 命令（`apply_preferences:78–94`，严格校验 target/payload/revision）可改；
  在途指令冻结不受后续修改影响（测试 `test_frozen_instruction_survives_disable_and_catalog_change`）。
- **当前显式调用**：`input.kind='skill_invocation'` + `resource_profile`，只在 `validate_submission`
  内解析角色/版本/ready，不写回会话配置；与排除冲突时准入与原生边界各拒绝一次（3.1、2.1）。
- **实际方法使用**：设计与计划要求“加载/应用声明/核验归属具体指令”，`skill_activity.py` 已进镜像
  （Dockerfile:60），但该文件及活动写入点不在材料内，本轮**无法**验证“偏好/显式选择不会自动生成为
  实际使用记录”，也无法验证“会话累计不推导每轮已执行”。属未知，不作结论。

## 5. 与上一轮结论的差异

- 撤回上一轮 R1 中“direct 模式排除字段在发送前丢失”的确定性：`9224` 条件已含排除字段，并有
  direct 模式测试。
- 撤回“排除后提示为空”：`method_guidance` 现在依据 `skills` 或 `excluded` 任一非空输出。
- R2 的“同标签内容替换可静默接受”在主路径上已不成立（准入/加载均比较身份）；
  仅在 3.1 的“客户端不带身份重存”路径上仍成立。
- R5 的“恢复比较遗漏排除字段”已不成立（统一投影 + 固定键序 + 一次性清理测试）。
- 上一轮 REQUEST CHANGES 的其余保留项（IG2–IG4 设计准备度、实页验收、CI 未授权）本轮未触及。

## 6. 结论与放行条件

**REQUEST CHANGES。** R1、R2、R5 的实现方向正确且代码级证据成立，但 IG1 仍不能关闭：

1. 补齐 R1 的决定性证据：或提供 `resources/general-sdk.mjs` 中 `allowedSkills` 的实际使用点，
   或补一条断言“被排除方法在原生发布/加载面不可达”（当前只有列表断言）。
2. 补齐 `ThreadCommandMenu.tsx` 与 `threadWorkProtocol.ts`（或说明为何不可提供），
   以证明本轮排除在界面可达且命令 payload 透传；否则 R1 的“界面排除本身得到保障”仍无证据。
3. 修 3.1（无身份重存的静默重绑定）与 3.4（`KeyError`），二者都是低成本的合同收紧。
4. 改 3.2/3.3 的错误归类与文案，避免把“技能作用域不兼容/内容变化”报成“AI 配置未就绪”。
5. 可选但建议：3.6 的构建期导入冒烟、3.5 的 `native_name` 精确匹配。

未运行 CI、全量测试、浏览器或真实模型执行；本轮不构成接受，也不授权 push、合并或部署。
