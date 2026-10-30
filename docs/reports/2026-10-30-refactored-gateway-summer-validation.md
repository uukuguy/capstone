# 重构网关轻量链迎峰度夏验证

2026-10-30，按用户要求连接本地研发18003，容器通过host.docker.internal访问。认证仅存受保护连接文件；原连接备份保留。MCP发现67工具。使用Vivaldi现有标签页新会话thr_69e78549c02807d98f91，DeepSeek Flash，深度思考关闭，默认调用池关闭。采用2026-10-27同题提示，日期口径保持原对比任务。

端到端执行完成653.895秒：86次模型响应、131次工具调用、0池事件。首次CSV约326.195秒，最终16页PPTX首次发布约540.047秒。PPTX399982字节，下载SHA256 cf336302a8ff666cb8d2fdaf122791650209455bba9799f116d7b5b1c761e73a，ZIP完整，16页。核心CSV582数据行、10列，下载hash校验通过。证据在忽略目录runs/refactored-gateway-summer-20261030/，含全分页事件、摘要、文件及描述符。

网关工具发现、只读取数、分析、保存和下载交付链路通过；不代表所有结论业务接受或性能接受。年度缺口明确：2026/2023不可得，以2025与2024的6/15—7/13对齐29天；2025后续窗口、南网及台风影响缺口保留。执行发现量测字段为文本，显式CAST AS REAL重算峰值；气象-999剔除。此前discover_gateway旧名直接调用未获准，新发布工具名称应以本次发现为准，客户端任务实际成功使用data_gateway_discover_gateway。

仍需优化：11次工具搜索、46次只读SQL、39次bash，86模型响应；报告生成出现多个临时两页PPTX，存在重复试制成本。当前总时长高于先前512秒，不能宣称提速。区域代表站不是面平均，相关不能作为因果，旱涝等级缺常年基准。正式业务结论仍需用户审阅接受。

企业数据研究分析模式继续暂缓，先处理本轮验证反馈。

## 追加：网关差异及诊断接入核查

两个实例真实MCP对照：本地联调18001，实例3db5bb96-2c27-4d97-8584-346bc4a18656，55工具；本地研发18003，实例9afa2e62-3914-47a9-aa71-c6e13be743d9，67工具。研发握手identity仍声明schema_version=1，但去掉data_source，增加data_environment=historical；Capstone严格v1解析因缺data_source丢弃整个identity。这解释了实例名退化为地址。建议网关明确版本兼容性或恢复v1必要字段；客户端也应保留已验证的实例名称，不让可选显示信息拖垮身份展示。对照证据runs/refactored-gateway-comparison-20261030/comparison.json。

研发新增12个语义工具（operation series/statistics、measurement history、source series/statistics等），旧55工具全部保留。不能从工具数量差异直接推断154秒耗时增量；本轮主要用了46次原始只读SQL，未做同数据同路径控制试验。

Capstone确定缺陷：general_pi_server.py实际gateway.bind仅传task_id/parent_attempt_id/allowed_tools，没有diagnostics；底层meta支持不能证明实际绑定已完成。须从可信Work/Attempt绑定稳定研究task_id和每轮run/trace，不得用每次新native task_id冒充稳定研究任务。完成后再核对网关request/span日志。当前gateway_only不算联合验收通过。

PPT验收纠正：包内0原生图表、5图片，不能据此声称图表质量通过或完全没有图表。需检查5图片内容及所有页面渲染；现有验证仅证明文件可下载、ZIP完整、16页，报告质量未接受。

## 带关联重跑：LLM41异常（执行中）

会话thr_dfa20d8487ecbbe8476a。应用runtime_action记录一次模型started到response_completed(error_code=model_transport)间隔300.130342秒。Provider relay同任务日志：HTTP200、982响应字节、300.186秒、stream_done=false、finish_reason=null。随后已完成42次模型响应，后续调用继续。此300秒明确属于模型流异常区间，不能归因网关数据库查询。尚未验证上游为何截断；不凭HTTP200当成功。异常及恢复应在用户执行记录中显式表达。

带关联完整重跑结束969.479923秒，81模型响应、244工具开始事件；其中LLM41异常300.130342秒，其余约669.35秒，接近前轮653.895秒。产物迎峰度夏运行特征研究.pptx675126字节，ZIP通过，15页、7张图片；CSV及完整分页事件保留runs/correlated-summer-20261030/。不能把总增量归因网关。模型自述因同比偏离>15%剔除5省，缺少独立口径证据，不接受该统计排除规则，报告质量验收未通过。需依据真实来源和质量标记修订，保留原全量结果与敏感性对照。

## 独立目视检查：修订版仍未接受

已下载修订PPTX，SHA256 901bb5e44c8542ff7b21d5e1b415e0ae1874776edb912ea7196ba453bdacef55。解包图片revised-media/image1.png实际目视：仅2025红线可见，图例2024两条曲线未正常显示；底部红色说明与图例重叠。同月日横轴替换不代表曲线内容有效，模型结构/像素方差自检不足。需继续通用图表可见性和交付证据改进，不能称完整视觉验收通过。

应用数据库连接超时栈来自产品目录GET -> product_index -> snapshot -> interrupt_expired_attempts -> _connect。当前连接状态仅5后台/1active，未证明泄漏；不能无依据改连接池或增大超时。需要复现目录/事件并发访问与后台写入情况下的连接建立和扫描开销。
