# data-gateway 本机运行协查

用户授权2026-11-05通知 data-gateway 协查。以下为只读检查，未修改、重建或
重启 data-gateway；其工作区有未提交开发，保持原样。

## 范围

Capstone local-dev 来源4ba178910b0916ec2a0f68593aa51e397ff74271。
Thread thr_f21d1c070e2f134dc389，attempt_1579b781f690006a，
提交时间2026-11-05 14:36:03UTC，任务“迎峰度夏”研究。
186次工具调用，42次错误结束，其中29次来自网关、7次组合程序、6次bash。
114次 query_source_records 最大重叠4，后半段仍有串行分页/跨对象循环。
不能把串行或全部错误归因于网关。

## 已确认运行缺陷

容器 data-gateway-capstone-gateway-1，镜像 data-gateway:0.1.0-dameng-arm64。
Compose目录：data-gateway/runtime/capstone/data-gateway-0.1.0。
discover_object_catalog 的真实返回：
`Error executing tool discover_object_catalog: No module named 'grid_database'`。

容器内只读检查：

```python
import importlib.util, importlib.metadata
assert importlib.util.find_spec('grid_database') is None
d = importlib.metadata.distribution('data-gateway')
print(sum(str(p).startswith('grid_database/') for p in d.files or []))  # 0
```

data_gateway 实际从 .venv/lib/python3.12/site-packages/data_gateway 加载；
发行包记录共37files，没有grid_database。当前宿主pyproject已包含
providers/grid-database/src/grid_database，Dockerfile也有provider COPY，
说明当前源码与正在运行的旧发行包可能不一致；具体构建来源请owner核实。
当前容器仅挂载metadata/config/state，无provider代码挂载。

## 请求标识（需owner核对原始异常）

| 工具 | request_id |
| --- | --- |
| list_metric_coverage_index | aad1757f4b25484d806280d2174ada0e |
| get_region_members | 7347cad5a2914e29a21ca7da76addff0 |
| search_data_catalog | d05dd9aa5ce045feb71e6559b98cb50d |
| execute_readonly_sql | 12edafdb90224611a242f6889df2ecaf |
| describe_source_table | 18a5fb9b0b3a465c9f64ad9c934eed09 |
| get_metric_availability | 5e2d9c3eeaf54950a237f02899cfc149 |
| query_database_series | 5dd8503f3b4e467eb463340f5f444d84 |
| find_business_objects | 832d9e87613f4a44b938786e54650ec3 |
| query_grid_weather | 5b5264e93488403db04b140b779d4fc5 |
| summarize_grid_weather_days | b94c344e8d92499eba15ee2ee2134fa2 |

以上请求多数返回internal_error；未查原始异常前，不认定全部由缺包造成。

## 请协查

1. 确认实际运行镜像的源码与wheel来源，修复缺失provider包并加发行包导入门禁。
2. 核对这些request_id原始异常，区分缺包、输入问题、配置和未实现能力。
3. 按现有运行维护约定保留配置、metadata与state；激活前检查活动请求。
4. 回复修复来源、镜像身份和受影响工具的真实检查结果。

Capstone负责组合程序的full_result变量、saveContext接口误用、结果身份及
有依赖分页与独立对象并发，不请网关猜测或改写业务查询。
本轮未探测或更新63/66。
