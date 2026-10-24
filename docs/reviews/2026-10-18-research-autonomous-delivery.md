# Enterprise research 自主交付验证

状态：实现与本地验证中，尚未通过自主业务验收。

02:01更新：自然反馈续跑1f495c20在4分53秒正常完成(event486)。生成118513字节report.html，7张内嵌SVG、6表，无外部引用；下载副本哈希296de42cccd9155fa54223a79867e48a86604e587736d8a4c82f3473a7125dfe与服务器一致。真实右侧预览已打开；主要输出、13项支撑、1项复算及15项过程文件按持久用途分组。生成过程自行复核并修正图表及归因表述，无外部逐步修复指令。该结果证明界面上传→普通请求→失败保留→自然继续→报告产出链路，尚不代表初轮稳定完成、数值全面复核或后续修订验收。指令悬浮预览增加真实状态/耗时，18项专项通过；过程文件误自动打开已改为仅主要输出自动打开。

01:55更新：界面首轮 attempt_5e24cf0335026e99 在189秒后失败，私有固定原因码 model_turn_incomplete，11项计算/原始数据文件保留但没有报告。不得称为超时或已交付。经页面发送自然反馈“刚才还没有看到报告，请继续完成，先给我一版能看的。”，attempt_1f495c208c93955b 正在执行。后续诊断须区分模型停止原因与宿主协议故障。

新增资源边界决策：企业文件上传与模型上下文容量分离。原文件作为持久会话资源保存，使用有版本和哈希的引用；任务上下文构建负责按需读取、解析、分块、检索、计算和摘要。上传容量由企业配置与存储传输能力决定，不能等同单轮模型输入上限。禁止静默截断后声称完整读取。当前实现仍把文件base64装入任务提交，并共用8MiB上限与4文件限制；前端参数修复不代表此架构问题已解决。后续需在现有私有资源授权及Pi工作区协议下实现受控按需取用，不暴露对象存储凭据或宿主路径。

用户确认：研究推进、检查、修订及交付属于 enterprise-research ApplicationProfile 与 Domain Pack 的通用能力。用户提供业务目标和反馈，不能要求用户编写操作步骤。此前人工补充校核指令所得报告保留，但不能作为自主组织验收。

本轮沿既有 research ledger、Pi action/observation 循环和独立研究 Pack 实施：

- Pack 方法增加目标驱动、自查、局部修订、文件用途和继续工作规则；不含电价、新能源或特定样例公式。
- 执行器接收可选 capstone-workspace-products/1 声明，真实文件哈希绑定 primary/support/reproduction 用途；不制造文件、不认定任务接受、不改变失败状态。声明错误不阻断执行，缓存字节码不发布，主要输出优先于收集数量上限。
- 前端消费持久化用途，主要输出直接显示，支撑、复算及未分类过程文件折叠。旧文件不按扩展名伪造用途。
- 已发现并修复 Pi 研究进展事件漏投影：后端已有 task_progress，前端此前仅读取专业 tool_completed。现在读取公开、成功的原生进展事件；底层调用默认折叠。没有可读历史时明确缺失，不补写历史。

验证：后端用途和原执行器/Pack 测试先失败后通过；用途专项5项通过，原执行器与Pack14项通过；制品/普通对话20项通过、13项独立PG参数跳过。App成果相关27项通过，进展与用途19项通过，TypeScript通过。

会话 thr_3545c43330f56760f358 通过 API 上传，仅用于机制调试，不能作为真实用户操作验收。其执行因 Pi 镜像遗漏 native_product_roles.py 而在收集文件时失败，未保存报告；不计验收通过。已修复显式 COPY，并增加镜像构建时导入检查。

本地规范重建通过，API/worker 镜像 sha256:a9ed9d26b6ae9d782779f4f73502c3ca1344d7f635e7be76b2b656c08795667a。真实容器制品收集器导入通过。未合并，云端及用户试用环境不变。

真实界面验收：thr_01d2a7e97b3e1afb3227。从新建会话菜单创建研究会话，上传控件逐份选择四份原始资料。操作发现前端旧512KiB限制，与后端8MiB协议不一致；现改为读取服务器公布的资料范围。重传后界面确认4份资料均选中。01:44左右发送单条普通业务请求，attempt_5e24cf0335026e99 正在执行，已产生真实 agent_task_progress 事件。上传截图 /tmp/research-ui-uploaded-inputs.png；状态脚本 /tmp/research-ui-status.py。报告与后续修订尚未验收。

用户明确允许初稿不完美，并通过多次自然、非严格、指出具体要点的反馈修订。不得将验收改成一次完美交付，也不得由外部助手输入计算和修复步骤冒充用户。标题栏入口改为轻量“任务成果”；成果区优先打开真实任务交付或已声明主要成果，支撑和过程材料折叠，不按文件名编造角色。相关前端29项通过，TypeScript通过；后端收集与服务25项通过。

用户追加确认：允许可定制的通用研究任务提示。模板属于 ApplicationProfile 所选研究 Pack 的任务入口资源，说明目标、资料、口径、期望制品、关注事项与交付要求；用户可修改，版本与采用文本随任务输入保留。模板不编排固定工具顺序，也不替代执行中检查和恢复。当前原始请求验收不在途中注入额外模板，避免混淆验收条件。模板入口尚未实现。
# 02:37 local follow-through

Actual UI natural feedback revision completed: attempt_4ea5fe090ec00e15, event818, about165s. The user-level request asked for an executive summary, priority provinces, qualified maintenance suggestions and retained charts. No procedural repair prompt was sent. Report125187bytes, SHA25647cf7e165e1bb797303b6a746870f40a8c2d5c28f9048cf5ffcb512b277e2add; all7inlineSVG match prior bytes. UI adopted task deliveryv1(event820); reload restores its preview and dependency and updates the session title(event821).

The first revision submission was rejected: four input files exhausted a shared count and their bytes were charged to the512KiB product budget. Selected product count/bytes now remain separate from uploads, under the existing total native byte bound. This interim repair does not implement GB resources. API/worker image3f6b5431b57c rebuilt through the canonical entrypoint and ready. Backend23passed/5PostgreSQLskipped. Frontend17work-execution tests pass, including rejection retaining draft and notice instead of reconnecting. Typecheck/diffcheck pass.

UI reading repairs: product padding16px/18px; summary expansion retained actual y341.640625; file group entries11px/18px; side-sheet record body13px/1.65, metadata11px and code12px. Actual browser screenshot /tmp/research-execution-details-readable.png inspected. No merge or cloud/user-trial update. GBresource handling, cross-profile acceptance and broader integration remain open.

