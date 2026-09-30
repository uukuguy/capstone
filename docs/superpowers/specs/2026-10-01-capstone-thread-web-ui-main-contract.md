# Capstone Thread Web UI 主合同

**状态：** Approved primary contract

**适用范围：** Capstone Web Thread 的右侧对话区、状态反馈、Composer、助手回答和工具活动展示。

**生效日期：** 2026-10-01

**上位约束：** 本合同只规定 Web presentation 和交互方式，不改变
capstone-thread/1、ThreadSnapshot、EventPage、CommandEnvelope、Capstone Harness、
Domain Pack、Authority 或当前运行证据准入契约。旧的 Thread/TUI/CLI 状态语义继续以
既有设计合同为准；本合同覆盖 Web 对话表面的视觉和交互细节。

**参考：**

- docs/superpowers/specs/2026-09-30-capstone-ui-ux-design.md
- docs/superpowers/specs/2026-09-30-capstone-ui-wireframes.md
- docs/superpowers/specs/2026-09-30-capstone-ui-ux-review.md
- assistant-ui ChatGPT example: https://www.assistant-ui.com/examples/chatgpt
- assistant-ui Perplexity example: https://www.assistant-ui.com/examples/perplexity
- assistant-ui LangGraph example: https://www.assistant-ui.com/examples/stockbroker

## 1. 产品判断

当前 Thread 已具备真实发送、Harness 执行、工具事件、最终回答和 IEEE-39 模型联动能力，
但界面仍处于调试投影阶段。截图暴露出以下必须修正的问题：

1. 字体整体过大，标题、用户气泡和助手正文同时抢占空间，核心回答密度过低。
2. 原始 Markdown（##、表格分隔线）直接展示，回答不可读。
3. 空闲提示、accepted 回执、Harness 标识、工具完成列表形成重复状态层。
4. 工具活动只显示 tool completed，无法判断执行了什么能力、属于哪个阶段。
5. 消息容器边框和留白过重，像调试面板，不像成熟对话产品。
6. Composer 是普通表单，尚未形成固定底部、可持续追问的 AI 对话输入区。

因此，下一阶段不是继续堆叠状态卡，而是以 assistant-ui 的成熟 Thread 骨架为基础，
重做信息层级、字体密度、Markdown 内容层和运行反馈。

## 1.1 主流对话界面从哪里继承

本项目不另起一套聊天框视觉语言。对话区默认沿用 assistant-ui 官方 GPT、Perplexity、Grok、
Claude 和 Gemini 示例已经验证的主流模式；Capstone 只增加领域所需的模型上下文、工具活动、
结果卡片和证据入口。官方示例明确展示了以下模式：

- GPT：居中空状态、固定底部 Composer、用户消息操作栏、助手 Copy/反馈/重新生成操作栏。
- Perplexity：紧凑阅读宽度、模式/模型选择器、粘性 follow-up Composer。
- Grok：pill Composer、附件入口、模型下拉、输入为空/有文本/运行中时动态切换尾部动作、
  消息计时提示和 hover 操作栏。
- Claude：无头像、轻量用户气泡、扁平 Composer、hover/focus 才出现的小图标操作栏。
- Gemini：头像-free 助手 Markdown、右侧灰色用户气泡、单行 Composer 和 disabled/ready/stop
  三态发送按钮。

因此，以下做法被禁止：为 Capstone 自创一套厚重的消息卡、永久显示大头像、把每个工具事件做成
独立大卡片、用大块页签代替 Composer 内的模式选择、用文字按钮代替精致图标操作。

## 2. 不可违反的架构边界

- CapstoneThreadClient、ThreadProjectionStore 和 typed public events 是状态真相。
- @assistant-ui/react 只负责对话交互骨架、Composer 状态和消息渲染生命周期。
- 前端不得从助手 prose 推导模型、拓扑、结果数值或证据状态。
- 工具活动必须来自 Harness public projection；不得直接透传 Pi/DSH 原生事件。
- 结果卡片和证据引用必须来自当前 Run 的 admitted projection。
- Markdown renderer 只渲染受控文本，不开放任意 HTML。
- UI 视觉变化不得创建、修改或隐式重试 Thread、Turn、Attempt。

## 3. 目标界面结构

保留当前 App 标题栏、左侧电网模型区和右侧对话区。右侧采用四个层级：

    Thread 标题栏
      当前模型 / Run 状态 / 连接状态
    消息滚动区
      用户消息
      助手回答（Markdown）
      当前运行结果/证据摘要（有引用时显示）
      工具活动摘要（附在所属助手回答下，默认折叠）
      回答操作栏
    Composer（固定底部）
      模式选择 · 多行输入 · 发送/停止

### 3.1 右栏标题栏

- 第一行只显示 Thread 标题、当前模型短名称、连接状态和 Run 状态。
- run_id、ModelContext ID、revision 等详细信息进入诊断抽屉或复制详情，不在主标题中展开。
- 空闲只作为紧凑状态徽标，不再使用大面积说明卡。
- send_auto accepted 作为对应用户消息下的轻量 receipt，不再独立占一整行。
- 标题栏高度目标为 48–56 CSS px。

### 3.2 消息滚动区

- 消息区独立滚动，Composer 固定在右栏底部。
- 初始空 Thread 使用居中欢迎语和 Composer；有第一条用户消息后立即切换为普通消息流。
- 不使用每条消息一个大白色面板的嵌套卡片结构。
- 助手消息最大阅读宽度为右栏的 86%，用户消息最大宽度为 72%。
- 长回答不得把 Composer 推出浏览器底部。

### 3.3 工具活动

默认显示一行摘要：

    已完成 6 个步骤 · 查看运行过程

展开后显示：

    ✓ 读取当前电网模型       pandapower-static-analysis
    ✓ 获取模型约束           model.constraints.describe
    ✓ 校验证据引用           current-run admission

每一步最多展示：人类可读名称、状态、来源 Pack/能力、耗时和结果/证据入口。Attempt 运行中必须即时显示已运行时长，并随运行持续更新；Attempt 结束后保留最终运行时长。
活动摘要必须挂在产生它的助手回答下面，不能作为整个 Thread 的全局尾栏；这样多轮对话中每个专业指令都能独立展开和排错。默认只显示当前 Attempt 的最后摘要；历史工具事件通过该回答展开查看。

## 4. 字体、密度和可读性硬规范

截图中的字体巨大是本合同的明确缺陷，必须单独验收。以下尺寸均以浏览器 100% 缩放、
CSS px 为基准：

| 元素 | 目标字号 | 行高 | 备注 |
| --- | ---: | ---: | --- |
| 页面品牌/全局标题 | 16–20px | 1.2 | 不进入消息区 |
| THREAD / RUN 标签 | 10–11px | 1.2 | 等宽、字距有限 |
| 对话标题 | 18–22px | 1.25 | 禁止使用 30px 以上 |
| 用户消息 | 14px | 1.55–1.65 | 中文正文 |
| 助手正文 | 13–14px | 1.55–1.7 | 主要阅读内容，优先保证长回答密度 |
| 表格正文 | 12.5–13px | 1.5 | 允许横向滚动 |
| 工具活动 | 11–12px | 1.45 | 默认折叠 |
| receipt / metadata | 10–11px | 1.35 | 不承担正文阅读 |
| Composer 输入 | 14px | 1.55 | 多行输入 |
| 辅助提示 | 11–12px | 1.45 | 不得低于 11px |

硬性规则：

- 普通正文不得超过 14px（受控标题除外）；助手回答不得使用 display/hero 字号。
- 对话标题不得超过 22px；右栏标题与空状态标题不得同时使用大字号。
- 同一视觉层级只允许一个主标题，不得同时显示“对话 Thread”和大面积空闲标题。
- 主要消息间距 12–16px，卡片内边距 12–16px；禁止 28px 以上的默认消息留白。
- 字体权重以 400/500 为主，700 只用于标题、状态和按钮。
- 颜色必须满足正文对比度，不能用浅灰色承担主要信息。

## 5. 消息视觉合同

### 用户消息

- 右对齐，单一浅蓝/青灰气泡，圆角 16–20px。
- 不显示大头像；可保留 24px 内的轻量身份标记。
- 自动识别/专业分析以小型模式标签显示在 receipt 中，不占用气泡标题。
- 支持复制和编辑入口，但默认只在 hover/focus 时出现。

### 助手消息

- 左对齐，使用小型 Capstone 标识或状态点，不使用大头像。
- 正文采用 Markdown/GFM 渲染：标题、列表、表格、代码、引用、链接必须有明确层级。
- 助手正文使用无重边框的阅读面，必要时只保留左侧状态线或极浅背景。
- 回答底部提供：复制、重新运行、查看证据、查看运行过程。
- 回答没有文本但 Attempt 尚未终止时，显示“正在生成回答…”和活动指示。
- Attempt 失败、取消、中断时必须显示对应终态和下一步动作；不得继续显示生成中。

### Markdown 和领域内容

- 首先实现安全的 Markdown/GFM renderer。
- 表格、代码块、长引用和证据列表必须有独立视觉层级。
- 电网结果后续使用受控 ResultCard：指标、单位、模型 revision、结果来源和证据引用分开显示。
- 拓扑定位、结果表、证据回放通过显式操作联动左栏，不将大型图形塞进消息气泡。

## 5.1 消息气泡下的精致操作栏

每条消息的操作栏是必要的产品细节，不是后续可有可无的装饰：

- 用户消息：编辑、复制。
- 助手消息：复制、重新运行、赞成、反对、查看证据、查看运行过程、更多。
- 默认隐藏，hover 或键盘 focus 时淡入；不能影响消息布局高度。
- 使用统一 SVG 图标和 tooltip，禁止使用 emoji、文字堆叠或没有含义的圆点。
- 图标按钮视觉尺寸 28–32px，点击区域至少 36px；每个按钮必须有 aria-label。
- 复制后显示短暂的 Copied 状态；重新运行必须创建新的 Attempt，不得修改旧 Attempt。
- 证据和工具过程按钮只有在 projection 提供对应引用时显示；不能显示空操作按钮。
- 运行时间必须在运行中的 Attempt 下即时显示并持续更新；完成、失败、取消和中断后保留最终运行时长。首 token 时间和 token/s 可以通过 tooltip 或详情显示，默认不占用消息正文空间。

## 5.2 Composer 的主流交互细节

Composer 采用 GPT/Perplexity/Grok/Gemini 的共同模式，而不是当前的大矩形表单：

- 使用圆角 pill 或 16–24px 圆角容器、细边框或 ring，避免厚重阴影和大面积白色面板。
- 输入区是主体，按钮围绕输入区底部对齐；输入内容增加时 Composer 可增高但有最大高度。
- 左侧保留一个可扩展的加号/附件入口；当前阶段没有附件能力时可以隐藏，但不改变整体布局模式。
- 模式选择、模型信息和 Domain Pack 状态使用紧凑 pill/dropdown，不使用两个大块页签。
- 右侧主动作是图标优先：空输入为 disabled、可发送为 send、运行中为 stop；状态转换要有轻量动画。
- `data-empty` 和 `data-running` 这类状态驱动视觉切换，不能由多个互相冲突的 React 布尔值拼接。
- 输入框下方只保留一条轻量键盘提示或可靠性提示，不再占据一整行大面积空间。
- Composer 必须在空状态和已有消息状态复用同一组件，只改变位置和宽度。

## 6. Composer 合同

采用 assistant-ui 示例中的 sticky footer 和多状态 primary action 模式：

- 空闲且有文本：显示发送。
- Attempt 运行中：显示停止；普通业务发送禁用。
- Attempt 运行中仍保留草稿，不清空用户输入。
- 无文本且空闲：显示普通的空状态操作，不显示无意义的 disabled 发送按钮。
- 自动识别是默认模式；专业分析是显式模式选择，不代表前端自行完成意图分类。
- 模式选择器放在 Composer 内部，以紧凑 pill/dropdown 展示，不再使用两个大块页签。
- 多行输入默认 2–4 行，随内容扩展但不能把消息区挤出视口。
- 保留 Enter 换行、Cmd/Ctrl+Enter 发送的明确提示。
- 发送后必须立即出现用户消息和 accepted receipt；等待 Harness 时显示运行状态。

## 7. 状态层级

主界面只保留一个主要运行状态，其他状态降级到对应位置：

| 状态 | 主界面显示 | 详细信息位置 |
| --- | --- | --- |
| idle | 标题栏徽标 | 无需大卡片 |
| accepted | 用户消息下 receipt | 诊断抽屉 |
| running | Attempt 活动摘要 + 动态运行时长 + 停止 | 展开工具步骤 |
| completed | 助手回答 + 最终运行时长 + 操作栏 | 结果/证据抽屉 |
| failed | 助手错误状态 + 重试动作 | 错误详情 |
| cancelled/interrupted | 终态说明 + 新 Attempt 动作 | Attempt 详情 |
| reconnecting/resync | 顶部恢复条，冻结发送 | 连接/诊断抽屉 |

禁止同时显示多个内容相同的状态卡。状态必须说明“现在能做什么”。

## 8. assistant-ui 组件映射

保持 CapstoneAssistantThread 作为 Capstone 适配层，逐步替换其内部表面：

- ThreadPrimitive.Root：右栏整体运行边界。
- ThreadPrimitive.Viewport：消息独立滚动区。
- ThreadPrimitive.ViewportFooter：固定 Composer 和底部辅助信息。
- MessagePrimitive.Root：用户/助手消息布局。
- MessagePrimitive.Parts：受控 Markdown Text renderer。
- ActionBarPrimitive：复制、重新运行、证据、工具过程等回答动作。
- ComposerPrimitive.Root/Input/Send/Cancel：输入和运行中主动作。
- AuiIf 或等价状态条件：实现互斥的发送/停止/空状态动作。

assistant-ui 的 ChatGPT/Perplexity 示例作为结构参考；Capstone 的颜色、模型上下文、
工具 provenance、证据和电网联动保持自有设计。

## 9. 实施顺序和验收门

### Phase A — 结构和密度

- 重排右栏标题、消息区、活动摘要和 sticky Composer。
- 删除大面积空闲说明卡和重复 accepted 行。
- 按本合同字号表收敛字体、内边距、消息宽度和行高。
- 验收：100% 浏览器缩放下，首屏能看到标题、至少一条完整消息和 Composer；没有垂直裁切。

### Phase B — 内容可读性

- 接入受控 Markdown/GFM renderer。
- 增加标题、列表、表格、代码块和证据引用样式。
- 验收：IEEE-39 模型说明和潮流分析结果不再显示原始 Markdown 符号。

### Phase C — 运行反馈

- 聚合 tool events 为 Attempt activity summary/stepper。
- 完成 running、completed、failed、cancelled、interrupted、reconnecting 状态。
- 运行中的 Attempt 显示动态运行时长，终态回答保留最终运行时长。
- 验收：用户能从界面判断当前阶段、来源能力、运行耗时和下一步操作。

### Phase D — 回答操作和领域卡片

- 加入复制、重新运行、证据、工具过程、拓扑定位。
- 加入受控 ResultCard、EvidenceCard 和模型/revision 标签。
- 验收：所有动作都通过已有 CommandEnvelope 或 typed projection，不能绕过 Harness。

### Phase E — 视觉验收

- 使用真实新 Thread 验收：普通问答、专业分析、长回答、工具运行、失败、取消、重试、重连。
- 测试 1200px 桌面、900px 紧凑桌面和 600px 以下单面板模式。
- 检查键盘焦点、屏幕阅读器标签、动画降级和正文对比度。
- 必须提供浏览器截图作为视觉验收证据，不以单元测试代替。

## 10. 明确不做

- 不把现有三栏 Case App 一次性重写。
- 不复制 assistant-ui 示例的品牌、产品名称、营销文案或配色；但对话布局、Composer、消息气泡、
  hover/focus 操作栏、图标按钮和状态切换必须优先沿用这些示例的成熟模式，不得另起一套。
- 不在本阶段引入任意 Generative UI；先完成受控 Markdown、工具摘要和 ResultCard。
- 不把模型隐藏思维链直接展示给用户；可展示受控阶段摘要和工具活动。
- 不为逐工具增加独立开关；能力选择仍以 Domain Pack/Profile 层级为边界。

## 11. 完成定义

本主合同只有同时满足以下条件才可声称 Web 对话 UI 完成：

1. 字体和密度通过第 4 节硬规范，截图中不再出现当前的巨大标题和巨大正文。
2. 真实助手回答以可读 Markdown/GFM 呈现。
3. 工具过程从原始事件变成可理解、可折叠、带来源的活动摘要，并附在对应助手回答下。
4. 运行中的工具过程即时可见并显示动态运行时长；完成回答保留最终运行时长。
5. Composer 固定在对话区底部，发送、停止、重试和草稿行为正确。
6. 普通问答和专业电网分析都显示正确的模型、Run、Attempt 和证据边界。
7. 视觉回归截图和 focused tests、TypeScript/build、package boundary checks 全部通过。
