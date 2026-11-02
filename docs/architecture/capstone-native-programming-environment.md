# 原生隔离编程环境

Application 可将通用分析与文件工作交给隔离 Pi 执行器。本页说明该执行器的基础编程环境；
它不定义专业 Domain Pack 工具，也不授予 Authority、网络或文件访问权限。

## 清单与锁

以下文件是环境的 owning source：

- [native-analysis.json](../../configs/runtime/native-analysis.json)：Python 根依赖、导入名、能力分类、Debian 工具及版本检查方式。
- [native-analysis.lock.txt](../../configs/runtime/native-analysis.lock.txt)：实际解析的 Python 版本和发行包 SHA-256；不是浮动安装列表。
- [锁生成器](../../tools/lock_native_analysis.py)：读取清单，复用 [共享依赖锁](../../configs/runtime/power-samples.lock.json) 的已有约束，为 Python 3.12 解析兼容结果。
- [镜像定义](../../deploy/general-pi.Dockerfile)：使用锁及哈希检查安装 wheel，安装清单中的 CLI，并执行真实 smoke。

从仓库根更新清单与锁：

```sh
python tools/lock_native_analysis.py
```

检查解析差异、共享版本及新增传递依赖后，再通过统一入口构建验证：

```sh
make capstone-local-rebuild
```

锁文件头记录清单和共享约束的摘要。更新清单或约束后须重新生成锁；不得手改解析版本或跳过哈希检查。
Debian 工具来自固定基础镜像配置的发行版仓库，实际 CLI 版本写入构建收据；Python 锁不等同于 Debian 仓库快照锁。
新增 npm/npx 来自同一固定 Node stage，tsc/tsx 复用 Pi 已固定的依赖，不另下载一套 Node 工具链。
新环境安装层位于受管资源 seed 层之后，并使用 wheel 缓存，避免无关变更重新下载大型注册资源。

## 基础 Python 与受管 MCP

清单中的包安装到隔离镜像的默认 Python，供已授权的原生编程任务使用：

| 类别 | 主要库或工具 |
| --- | --- |
| 数据、统计与轻量建模 | numpy、pandas、SciPy、statsmodels、scikit-learn |
| 图表与图像 | matplotlib、seaborn、Plotly、Pillow，中文字体 |
| 表格、列存储与查询 | openpyxl、xlsxwriter、pyarrow、DuckDB |
| 文档与 HTML | pypdf、pdfplumber、python-docx、python-pptx、BeautifulSoup、lxml、Jinja2 |
| 通用处理 | requests、httpx、PyYAML、tabulate |
| CLI | rg、jq、unzip、zip、pdftotext、pdftoppm；保留 git、curl、Node、uv，并提供 npm/npx、tsc/tsx |

具体版本及完整根列表以清单、锁和构建收据为准。
受管 skills/MCP 继续使用自己的固定安装、解释器、资源版本及既有库存；不能因基础 Python 已有某个包，
就声称 MCP 已加载或获得其权限。共享依赖锁只提供版本约束，不把其中的专业仿真包安装为基础分析根依赖。
不预装模型权重或大型训练栈。通用计算和文件观察不会自动成为 Authority 结果或模拟器证据。

## 构建检查与收据

[native_analysis_smoke.py](../../tools/native_analysis_smoke.py) 在镜像构建时执行真实分类检查：
CSV、统计与回归、中文图表、内嵌交互 HTML、图像、两种 Excel 写入、Parquet、SQL、PDF、Word、
PowerPoint、HTML 解析、HTTP 客户端构造、YAML、表格文本、压缩与检索 CLI、PDF CLI，以及 JavaScript/TypeScript。
检查使用内部小样本，不调用 Provider，也不向外部服务器发送请求。

只有全部检查成功，脚本才原子写入 `/opt/general/runtime-environment.json`。
其 schema 为 `capstone-native-environment/1`，包含 Python 身份、实际包版本、提取后的 CLI 版本、
通过的能力 ID，以及清单和锁的摘要；不包含路径、环境变量、凭据或完整命令 banner。
测试可用 `--inventory-output`、`--manifest`、`--lock` 指定临时位置；检查失败不会发布成功收据。

[native_environment.py](../../packages/capstone-agent/src/capstone_agent/native_environment.py)
校验收据并供宿主在构造执行器时读取，形成简短环境上下文。缺少收据时不注入虚构清单；
无效收据明确拒绝。收据属于执行配置身份，任务不需每轮重复运行 pip、包导入清单或子进程来探测环境。

源码中存在 smoke 或离线测试通过，不代表某个镜像已经验证。只有该镜像的实际构建门禁成功、
收据存在且相应阶段验证通过，才可报告该镜像可用。部署和验证状态仍按
[开发与发布生命周期](capstone-development-lifecycle.md)记录。

## 支持边界与缺口处理

文档库提供基础读写、提取和组合，不承诺任意 PDF/Office 格式、复杂排版、OCR、浏览器打印或商业软件级保真。
PDF smoke 验证基础文件读写和 CLI 栅格化；Word/PowerPoint smoke 验证文本往返，不是排版验收。
中文绘图检查不证明模型具有视觉输入能力；图像读取被所选模型省略时，不得声称已完成视觉检查。
文件可打开、图表可渲染也不证明业务数字、单位、分母或因果判断正确，仍须独立内容检查。

预装 HTTP 库、curl、npm 等不改变 Application 的联网开关、工具授权或隔离网络策略。
启用某个 skill/MCP 也不能绕过原始资料只读、私有工作区或 Authority 边界。
处理大文件继续使用版本化资源和有界按需读取；包的可用性不扩大任务上下文容量。

任务遇到缺包或不兼容时应记录真实缺口，选择已有能力或由操作者升级统一清单、锁和镜像。
不得静默在任务内临时安装依赖，代替受管资源或已接受的配置版本；不得修改原始只读资料来使脚本通过。

## 已修复的容器导入回归

新旧研究 policy 校验曾从 `native_task_context` 导入 `enterprise_application`，
后者依赖完整 Application/Kernel 装配；精简隔离镜像未复制该模块，导致真实任务启动失败。
现在新旧 policy 文本由 `native_task_context` 的共享常量提供，校验路径不再依赖该装配导入。
[回归测试](../../packages/capstone-agent/tests/test_enterprise_research_pack.py)
显式阻断这些导入；最终 Docker 构建还实际执行旧 legacy 与新 split context 校验。
这修复的是隔离镜像的依赖边界，不通过复制完整专业运行时来掩盖缺失模块。
