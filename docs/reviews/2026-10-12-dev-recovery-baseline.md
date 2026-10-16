# dev恢复基线与实验分支适配

状态：PR #14精确候选bc08169两平台CI通过，已合入dev6ff7094。
两实验分支已适配并推送；local-dev同源重建。新真实专项首次失败，未授予验收标签。
本记录不构成云端发布、整体业务验收或研究模型功能实现声明。

## 接受范围

恢复c3b78bc业务执行，保留独立且无工具的普通/专业LLM路由；补回最新三动作
9px运行短窗、完整窗口160px滚动、普通无业务工具轻量回答和最终消息隔离。
不恢复任务编译、覆盖核验、回答重写、冻结复用或预热。

产品82b243c的两轮真实专项、运行身份及浏览器已验，见
[选择性补回报告](2026-10-12-selective-ui-and-answer-restoration.md)。
当前bc08169另修正装配期间过早读取Provider配置的问题；未改分类策略、提示、
业务执行或答案收集。实际识别时才解析配置；无配置不触发关键词回退。

## 本地与远端检查

| 检查 | 已确认结果 |
| --- | --- |
| App及类型 | 新鲜380项App测试通过；bc08169类型检查0错误 |
| 集成 | 39项E2E、3项注册worker；离线7、静态核心10、静态完整8、应用实例2全部通过；能力矩阵24/24 |
| Provider延迟读取 | 原有失败用例及新增工厂时机断言先RED；pandapower/路由7、PyPSA5、路由单测4通过 |
| 独立审查 | 17debfb产品与82b243c一致；bc08169修正审查通过，无新增阻断 |
| 原远端失败 | 38179898843两平台均失败于两项无凭据装配检查；保留，不改记为通过 |
| 当前远端检查 | 38181053709，精确bc08169；Linux/macOS均通过，合并6ff7094 |
| 新鲜集成 | dev-baseline-bc-integration.log通过；检查时产品树与bc08169、6ff7094一致 |
| 本地来源 | API及两worker共506项分别匹配6ff7094；相同image90d9dd6d，App干净6ff7094 |
| 控制图 | 7节点、四环境来源、真实dev到两实施分支的来源边、桌面/390px布局检查通过 |

原始收据在忽略目录runs/task-answer-closure/：dev-baseline-check.log、
dev-baseline-integration.log、lazy-router-red.log、lazy-router-unit-red.log、
lazy-router-green.log、lazy-router-pypsa.log、lazy-router-types.log及
dev-baseline-pending-control-browser.log。

## 分支适配范围

Pi分支保留原实验功能，在独立工作区合入新基线并适配接口；不将其代码带入dev。
原749e0b8有archive/pi-before-dev-baseline-20261012恢复引用。
Research Model分支尚无R1代码；对齐新基线并更新任务、证据与消息边界依赖，
不依赖撤回的编译与覆盖模块。原50d8ebc有archive/research-before-dev-baseline-20261012引用。
R0实验bf678f2保持原样，其受控计算收据不改写为新基线上的研究能力验收。

最终Pi38e19db、Research Model2b0b0a5均已推送，固定合并基点为6ff7094。
见[Pi适配](2026-10-12-pi-dev-baseline-adaptation.md)及
[Research Model适配](2026-10-12-research-baseline-adaptation.md)。

## 新源真实专项及独立复核

provider-dev-baseline/provider-205eadfce559493e.json的首次两轮专项失败，保留原始收据。
普通请求被LLM分到professional，fallback=false，9.043s后capability_required；
没有业务工具、结果或证据。不能将其解释为普通问题需要业务能力。
线路停运轮41.349s完成，正式中文969字与最后真实assistant消息一致；
过程消息未进入正式回答。该项仅验证消息隔离，不认证全部数值表述。

未改代码或提示，随后三个直接路由探测均选ordinary，分别854/1205/859ms。
独立API单项重试provider-dev-baseline-recheck/provider-a08d62358bdc4d8e.json
走ordinary，105字、6.440s、零工具/结果/证据；实际general-task使用deepseek-flash、
thinking off。独立审查核对原始事件和运行配置。重试通过不能覆盖首次失败，
不宣称误路由已修复或路由可靠性已验收。

## 保留问题

负荷场景结果接纳失败、AC回答中的设备身份错误及电网概况的专业链耗时仍开放。
原七轮整体失败收据保留；此次专项通过不能替代整体验收。
Issue #2/#3保持开放。main、local-demo及两云端环境不随此次开发基线更新。
后续研究节点涉及已知缺陷时须单独修复或明确阻断，不能将失败结果用作结论证据。
