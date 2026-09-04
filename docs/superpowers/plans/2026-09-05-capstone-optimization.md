# Capstone Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` for task-by-task implementation when delegation is useful; otherwise execute inline with the same test/review gates. Steps use checkbox syntax. 本文件是唯一优化执行顺序与状态账本。

**Goal:** 闭合 Capstone 的答案与证据准入、非阻断报告、完整工程门禁、规模性能和领域扩展验证，保留首个 pandapower 应用兼容性。

**Architecture:** 保留 Kernel / Domain Pack / Application / Authority 职责。答案规则由领域策略提供，控制器负责确定性提交；展示作为可失败的派生输出。先修复保证和测试，再优化缓存与存储，最后用完整独立领域验证公共 SPI。

**Tech Stack:** 现有 Python/Pydantic、Pi JavaScript、React/TypeScript、pytest、Node test、Vitest/Playwright、uv、Make。继续使用项目锁定版本；依赖升级仅限 OP-06 的显式范围。

## 1. 状态、依据与授权边界

- 方案版本：1，2026-09-05；代码审查基线：`5a38c5b`。
- 用户已授权按本方案持续实施；机械任务交 Luna，明确实现交 Terra，复杂设计由 Astra 协调，风险变更独立复审。
- [评估记录](../../status/2026-09-05-capstone-design-code-review.md) 保存 R01–R13 证据、基线测试和限制。
- [架构总览](../../architecture/capstone-framework.md) 与仓库 `AGENTS.md` 继续约束实现。
- 当前执行包：OP-01。全方案状态：RUNNING；执行分支 feat/capstone-optimization，隔离目录 .worktrees/capstone-optimization。
- 保留当前 `Project route: direct`；本计划供直接执行与 project-state 恢复使用，不创建第二套隐藏状态系统。
- 旧 C.2 立即推进顺序被本计划替代；C.1 历史完成结论和旧 Climb 证据不改写。

## 2. Global Constraints

- grid 兼容 stdout 恰好一个 JSON 对象，仅 `question_id`、`answer_output`；诊断使用 stderr。
- `answers.jsonl` 属于应用适配器，不能成为 Kernel 通用输出协议。
- 数值、网络、排名、拓扑、故障及证据来自当前运行 `gridctl` / `grid-capability/1.0`，禁止猜测和按题捷径。
- LLM 继续返回读者文本；不恢复模型控制的答案提交工具，不开放 shell、任意文件、任意 Python、HTTP 或原始 pandapower 对象。
- Domain Pack 负责领域策略和验证；Kernel 不导入领域实现，不加入 grid 词汇判断。
- 权威证据、答案主记录、必要事务写入失败继续 fail closed；报告、缓存、预览和进度失败不能撤销已接受答案。
- 保留原有 runs、忽略的运行状态及用户 var 数据；历史 evidence/replay 原文不迁移、不重写。
- 一个应用仍仅允许一个 binding；动态插件、多域路由、写操作审批、租户治理不在本方案实现范围。
- 原有脏文件保留；只暂存任务所有路径；每个任务一个可回退提交或一组明确标识的提交。
- 不把重复重跑成功当作首次整套通过；不通过放宽断言、删测试、更新基线掩盖失败。
- 涉及 README 共享事实或命令变更时同步 `README.md` 和 `README.zh-CN.md`。
- provider/真实外部 authority 验证须有当次适用的凭据与费用授权；离线验收不偷用已有凭据。

## 3. 工作包、顺序与覆盖

OP 编号是唯一任务标识。表中依赖全部完成后才允许启动生产代码实现；只读调查可提前。

| 包 | 所属阶段 | 范围 / 发现 | 依赖 | 状态 | 完成证据 |
| --- | --- | --- | --- | --- | --- |
| OP-01 | 1 | 答案模式、领域准入、事实保证范围 R01 | 无 | RUNNING | 设计核对、隔离环境准备 |
| OP-02 | 1 | 单问 run 统一提交 R02 | OP-01 | PLANNED | 未执行 |
| OP-03 | 1 | 报告与观察故障隔离 R03 | OP-01 | PLANNED | 未执行 |
| OP-04 | 2 | RPC 测试竞态 R11 | 无 | VERIFYING | 9d13ea4；focused 2 / 30次重复 / runtime72 通过，独立复审中 |
| OP-05 | 2 | 全包门禁、类型检查、CI R04 | OP-02, OP-03, OP-04 | PLANNED | 未执行 |
| OP-06 | 2 | Pi 风险例外关闭或明确阻断 R12 | OP-05 | PLANNED | 未执行 |
| OP-07 | 3 | 投影缓存、轻量运行列表 R05 | OP-05 | PLANNED | 未执行 |
| OP-08 | 3 | 有界工件与上下文预览 R06 | OP-07 | PLANNED | 未执行 |
| OP-09 | 3 | 批量证据与明确错误状态 R10 | OP-07, OP-08 | PLANNED | 未执行 |
| OP-10 | 4 | 类型化执行接口与依赖说明 R09,R13 | OP-05 | PLANNED | 未执行 |
| OP-11 | 4 | 完整 inventory 应用验收 R08 | OP-01, OP-03, OP-10 | PLANNED | 未执行 |
| OP-12 | 5 | 长运行基准与存储决策 R07 | OP-07, OP-10 | PLANNED | 未执行 |
| OP-13 | 5 | 条件性分段日志实现 R07 | OP-12 确认触发 | CONDITIONAL | 未执行 |
| OP-14 | 5 | 综合关闭与 C.2 选择入口 | OP-01–12，OP-13 disposition 已记录 | PLANNED | 未执行 |

默认执行顺序：01 → 02 → 03 → 04 → 05 → 06 → 07 → 08 → 09 → 10 → 11 → 12 → 条件 13 → 14。
OP-06 以 2026-09-30 例外期限为硬约束；若接近期限，可在独立分支提前做版本调查，但合入仍需 OP-05 门禁。
并行只能用于不共享文件的独立工作；01/02/03/10 共享 runner 或提交契约，默认串行。

2026-09-05 执行调度：OP-04 无依赖且仅修改 runtime 测试，与 OP-01 的 application/domain 文件不重叠，提前交 Luna 实施；两包独立复审，生产功能仍按依赖顺序集成。

## 4. 每个包必须执行的控制流程

1. 读取本计划、评估记录、AGENTS、CURRENT-STATE 与 RESUME；记录实际 HEAD 和脏文件。
2. 进入隔离 worktree 时执行 `make setup`、`make install-pi`、`make doctor`；环境失败单列。
3. 先补能复现缺口的测试，运行并记录预期红灯；文档/纯迁移只用相关一致性测试。
4. 最小实现，跑包内 focused 测试，再跑第 6 节对应门禁；不边修 bug 边做无关全文件改写。
5. 对信任、持久化或公共 SPI 变化进行独立复审；记录发现如何解决。实现者不能自报关闭高风险缺口。
6. 任务拥有的代码、测试、文档和必要锁文件一起提交。先 `git diff --check`，再显式列路径 `git add`。
7. 在本表更新状态、提交 SHA、验证报告路径；向 JOURNAL 追加事件，更新 RESUME 下一包。

状态机：PLANNED → RUNNING → VERIFYING → DONE；失败进入 BLOCKED，记录复现、影响及恢复条件。
CONDITIONAL → RUNNING 或 NOT_NEEDED；NOT_NEEDED 必须有 OP-12 数据和评审结论。
只有测试通过、复审结清、证据落盘和工作树状态明确才可 DONE。任何关键门失败禁止推进依赖包。

证据存于 `runs/optimization/<package>/<run-id>/`，纳入命令、stdout/stderr、退出码、起止时间、HEAD、Python/Node/OS、报告摘要；禁止记录环境全量或凭据。
版本化账本记录命令和结论；忽略目录不存在时不能声称已重现，应可通过固定命令重新生成。

## 5. 任务级实施步骤

下列 Create 路径均为计划新增；Modify/Test 路径为现有文件。代码块定义交付接口或明确测试向量，不授权先复制空实现通过门禁。

### OP-01：建立明确的答案准入和保证范围

**Files**

- Create: `packages/capability-agent-kernel/src/capability_agent/domain/answer_admission.py`
- Create: `packages/pandapower-domain-pack/src/pandapower_domain/answer_admission.py`
- Modify: `packages/capability-agent-kernel/src/capability_agent/domain/profile.py`
- Modify: `packages/capability-agent-kernel/src/capability_agent/application/turns.py`
- Modify: `packages/capability-agent-kernel/src/capability_agent/application/runner.py`
- Modify: `packages/pandapower-domain-pack/src/pandapower_domain/profile.py`
- Test: `packages/capability-agent-kernel/tests/application/test_turns.py`
- Test: `packages/pandapower-domain-pack/tests/test_answer_policy.py`
- Create: `packages/grid-agent/tests/e2e/test_answer_admission.py`

**接口与决策**：领域准入接收当前问题、模型文本和控制器绑定的当前轮引用；零引用也调用所有配置 binding 的策略。保留现有引用形状/来源/关联校验，不由新策略替代。

```python
from dataclasses import dataclass
from typing import Literal, Protocol

@dataclass(frozen=True)
class AnswerAdmissionInput:
    question: str
    answer_output: str
    result_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]

@dataclass(frozen=True)
class AnswerAdmissionDecision:
    mode: Literal["authority_backed", "offline_information", "limited"]
    assurance: Literal["lineage_verified", "deterministic_information", "limited"]
    answer_output: str
    diagnostic_codes: tuple[str, ...]

class AnswerAdmissionPolicy(Protocol):
    def admit(self, request: AnswerAdmissionInput) -> AnswerAdmissionDecision: ...
```

领域 factory 负责注入当前 run authority，input 不提供调用方任意指定的文件路径。
这些是新增 SPI；增加明确的 profile 版本/能力声明，在 provider 启动前拒绝缺失必需组件，不使用隐式 permissive fallback。

- [ ] 新增参数化红灯用例：无工具数值断言、无工具拓扑断言、错误单位/错误场景的有效引用、跨轮未消费引用、空答案、正常真实结果、普通离线知识、无法判定的问题。前四类不能获得“事实已验证”状态。
- [ ] 固定策略：默认业务问题为 authority_backed；无当前轮有效结果时 limited。offline_information 只由领域确定性知识路径识别并生成回答，不由模型自报模式，也不通过数字/网络名正则猜分类。其余模糊问题返回 limitation 或继续获取证据。
- [ ] 准入返回的 reader text 由 controller 提交；limited 采用现有受限答案语义，不伪装 success。为普通知识问答保留领域知识来源且不制造运行证据。
- [ ] 对有有效引用的自由文本只声明 lineage_verified。新增对抗验收，将真实结果保持不变而替换文本数值/单位/排序，确保 audit 不把它标为“数值验证通过”。需要精确事实展示时由 Domain Pack 根据已验证结果渲染事实表，标注模型解释的保证范围；不解析自由文本后据此创造事实。
- [ ] 将准入模式/保证范围保存在版本化应用答案旁路元数据并关联 answer_ref；旧答案读者缺少该字段时显示 unknown，不猜测。不要直接给严格旧 schema 塞字段。
- [ ] 执行下列命令，预期新增测试先失败、实现后全部通过；复审策略不会封死正常离线信息，也不会由模型 bypass。

```sh
uv run --project packages/grid-agent pytest packages/capability-agent-kernel/tests/application/test_turns.py -q
uv run --project packages/grid-agent pytest packages/pandapower-domain-pack/tests/test_answer_policy.py -q
uv run --project packages/grid-agent pytest packages/grid-agent/tests/e2e/test_answer_admission.py -q
make validate-application
```

**关闭条件**：零投影也有明确领域准入；可追踪模式；文本语义保证没有被夸大；权威事实仍来自 gridctl。提交主题：`fix: enforce domain answer admission before commit`。

### OP-02：让单问 run 使用同一提交器

**Files**：Modify `packages/grid-agent/src/grid_agent/cli/app.py`、`packages/grid-agent/src/grid_agent/compat/v1_0_1.py`；Create `packages/grid-agent/src/grid_agent/compat/single_run.py`；Test `packages/grid-agent/tests/cli/test_run_command.py`、`packages/grid-agent/tests/cli/test_app.py`。

**接口**：适配器接受现有 RunRequest 和解析后的运行配置，组装只有一个 question 的 ApplicationRequest，调用 AgentApplication；从已提交答案进行两字段投影，不能返回未经提交的 Pi 文本。

- [ ] 记录现有 question_id、退出码、stdout、stderr、provider/model/base_url/api_key_env、offline 的兼容矩阵；写无引用/伪引用、provider 中断、重复 ID、非法 ID 回归测试。
- [ ] 提取单问适配器；配置解析复用原产品规则；run_id 对齐 question_id，既有 evidence 路径如需桥接由应用投影完成。不能静默改变调用方依赖的 paths。
- [ ] 让在线 run 经过 OP-01 准入和 controller 提交；普通 offline 知识走确定性路径；offline simulator smoke 继续真实 authority 调用并保存引用。
- [ ] 使用实际 CLI runner 捕获 stdout，执行以下断言；对错误也检查 envelope 和非零退出码。

```python
payload = json.loads(result.stdout)
assert set(payload) == {"question_id", "answer_output"}
assert payload["question_id"] == requested_question_id
assert isinstance(payload["answer_output"], str)
```

- [ ] 运行 `uv run --project packages/grid-agent pytest packages/grid-agent/tests/cli -q` 和 `make test-e2e`；旧命令、离线知识与真实 gridctl 夹具全部通过后，删除这一路重复的启动/提交代码。

**关闭条件**：成功答案可追溯到提交记录；公众 envelope 不变；不能以“至少调用过一个工具”代替问题相关证据。提交主题：`refactor: route single runs through application answer commits`。

### OP-03：将报告发布与主答案状态分离

**Files**：Modify `packages/capability-agent-kernel/src/capability_agent/application/runner.py`、`application/reporting.py`、`application/output.py`、`packages/grid-agent/src/grid_agent/compat/v1_0_1_report.py`；Test `packages/capability-agent-kernel/tests/application/test_runner.py`、`test_reporting.py`。

**接口**：新增报告发布结果，主结果继续使用已有可空 report_ref 和 diagnostic_refs；输出 schema 无需因展示失败而强制升级。

```python
from dataclasses import dataclass
from typing import Literal

@dataclass(frozen=True)
class ReportPublication:
    status: Literal["published", "unavailable"]
    report_ref: str | None
    diagnostic_codes: tuple[str, ...]
```

- [ ] 将现有报告 symlink 测试拆成两个断言：拒绝越界写入、已接受答案仍可返回。新增 renderer 异常、checkpoint I/O 异常、final admission 异常、observer 异常及答案主记录 I/O 异常。
- [ ] 在明确的展示边界捕获普通异常，返回 unavailable、report_ref=None；保留安全拒绝，不跟随 symlink，不改变外部文件。
- [ ] 诊断采用固定 code 与运行关联；如诊断工件写入也失败，仅尝试安全 stderr。KeyboardInterrupt/SystemExit 正常传播，cleanup 不覆盖主异常。
- [ ] 逐题报告失败后继续下一题。只在答案与必要状态提交成功后标 completed；不能捕获整个业务流程并无条件返回成功。
- [ ] 执行参数化用例中的核心断言：

```python
assert outcome.status == "completed"
assert outcome.completed_questions == 2
assert outcome.result.core.report_ref is None
assert len(outcome.result.core.answer_refs) == 2
assert outside_file.read_bytes() == outside_before
```

- [ ] 运行 `uv run --project packages/grid-agent pytest packages/capability-agent-kernel/tests/application/test_runner.py packages/capability-agent-kernel/tests/application/test_reporting.py -q`，再执行 `make validate-application`；验证应用 answers.jsonl 不被展示失败撤销。

**关闭条件**：展示失败可诊断且不阻断有效答案；必要证据失败仍阻断。提交主题：`fix: isolate report publication from accepted answers`。

### OP-04：修复 RPC ack 测试夹具竞态

**Files**：Modify/Test `packages/grid-agent/tests/runtime/test_rpc.py`；检查 `packages/capability-agent-kernel/tests/runtime/test_rpc.py` 是否存在同一夹具。

- [ ] 在 fake Pi 中先读取完整 prompt，再输出故意缺少 ack 的 agent_end，使该测试只测协议顺序。

```python
fake.write_text(
    "import json, sys\n"
    "sys.stdin.readline()\n"
    "print(json.dumps({'type': 'agent_end'}), flush=True)\n",
    encoding="utf-8",
)
```

- [ ] 用 try/finally 保证 client.stop；另设提前退出用例验证发送失败路径，不能扩大原 regex 接受两种错误。
- [ ] 连续运行 30 次，再跑 runtime 测试集；一次失败就保留日志，不能 retry-until-green。

```sh
for attempt in $(seq 1 30); do
  uv run --project packages/grid-agent pytest packages/grid-agent/tests/runtime/test_rpc.py::test_rpc_requires_ack_before_agent_end -q || exit 1
done
uv run --project packages/grid-agent pytest packages/grid-agent/tests/runtime -q
```

**关闭条件**：原协议错误断言稳定；提前退出独立覆盖；无遗留子进程。提交主题：`test: synchronize RPC protocol violation fixtures`。

### OP-05：完整且可重复的工程门禁

**Files**：Modify `Makefile`、`packages/grid-agent/pyproject.toml`、其 `uv.lock`、`README.md`、`README.zh-CN.md`、`docs/RUNBOOK.md`；Create `pyrightconfig.json`、`.github/workflows/verify.yml`；Test `tools/tests/test_verification_targets.py`（新增）。

**接口**：保留已有目标，新增三个稳定聚合入口。Python 包分别执行，避免同名模块合并收集。pyright 作为 dev dependency 锁定；禁止全局 ignore 降低门槛。

```make
test-kernel:
	uv run --project packages/grid-agent pytest packages/capability-agent-kernel/tests -q
test-generic-tools:
	npm run check --prefix packages/pi-capability-tools
	npm test --prefix packages/pi-capability-tools
check-types:
	uv run --project packages/grid-agent pyright
	npm run check --prefix packages/trajectory-workbench
check-fast: check-package-boundaries check-types test
check-integration: test-e2e validate validate-application
check-release: check-fast check-integration test-packages test-source-setup
```

- [ ] 新测试读取 Make dry-run，验证六个 Python 包、两个 Pi 包和工作台都有入口，且目标不存在递归环。
- [ ] 将 `make test` 扩展为完整离线单元入口，显式依赖 test-agent、test-simulator、test-tools、test-makefile-application、test-kernel、test-domain-package、test-generic-tools、test-inventory、test-workbench；保留独立 test-e2e/validate 的集成含义，清除同一调用图的重复执行。test-agent 是否已包含 e2e 在 dry-run 与 pytest collection 中核对，聚合命令不得遗漏或无意重复。
- [ ] pyright 配置覆盖 Kernel、两个 Domain Pack、两个 authority、grid-agent 的 src；测试替身后续逐步类型化，生产代码不以排除整包通过。修复基线类型问题分独立提交，记录每个豁免路径与理由。
- [ ] CI 运行 checkout → Python/Node 版本准备 → make setup → make install-pi → make doctor → 三层检查。固定 Python 3.12 和当前实际 3.14 验证线，Node 满足 >=22.19.0；macOS/Linux 分开记录，视觉金图按平台管理。
- [ ] CI 不使用 provider secrets，不发在线推理；Node/Python 下载是安装步骤。流水线配置先在本地做等价验证；未实际运行远端 CI 时不声称远端通过。
- [ ] 运行 `make -n check-release`、`make check-fast`、`make check-integration`；聚合命令任一子目标失败即非零。

**关闭条件**：全部生产包被门禁覆盖，文档准确，整套结果稳定；不把历史 Climb 的 100 分当作本次 release 证据。提交主题：`build: gate all framework and application packages`。

### OP-06：Pi 升级与到期风险处置

**Files**：Modify `configs/runtime/pi-runtime.lock.json`、`configs/runtime/pi-security-risk-exception-v1.json`、`packages/pi-capability-tools/package.json`、`packages/pi-capability-tools/package-lock.json`、`packages/pi-grid-tools/package-lock.json`；检查 `configs/runtime/patches/pi-0.80.6-before-model-request.patch` 的版本兼容性；Test `tools/tests/test_runtime_risk_exception.py`、两套 Pi capture tests。

- [ ] 用 `rg --files configs/runtime` 和 runtime locator 确认 `pi-runtime.lock.json` 及其中 package/source/patches 摘要；旧版本专用 patch 不能原样套在新版本，按实际 hook API 更新版本化 patch 和摘要。
- [ ] 检查当前官方 Pi release/API 与依赖审计，按现有例外的 >=0.84.3 下限挑选首个能满足全部 hook/extension 契约的版本；将选定版本、审计日期和理由写入执行记录。
- [ ] 在隔离环境更新统一版本和 frozen locks；保留 canonical request hook、descriptor、correlation、stdout、受限工具和凭据过滤回归。
- [ ] 执行 `make install-pi`、`make doctor`、`make check-release`，并执行更新后的依赖审计；禁止仅改 risk_counts 或删除 advisory 让门变绿。
- [ ] 修复确认后关闭例外；如果没有合格版本，标 BLOCKED 并明确发布阻断，到期门继续失败；不能自行延期例外或声称漏洞已修复。

**关闭条件**：升级证据及风险状态明确。2026-09-30 前未关闭则发布被阻断；不强迫无证据升级。提交主题：`build: upgrade validated Pi runtime and close risk exception`。

### OP-07：使投影缓存有效，运行列表轻量化

**Files**：Modify `packages/grid-agent/src/grid_agent/trajectory/service.py`、`materialize.py`、`api/catalog.py`；Create `packages/grid-agent/src/grid_agent/trajectory/cache_identity.py`；Test `packages/grid-agent/tests/trajectory/test_service.py`、`test_materialize.py`、`api/test_catalog.py`。

**接口**：缓存 identity 包含 run 身份、事件可信前缀/内容摘要、投影版本及实际读取的 metadata/artifact 依赖；缓存不承担权威证据准入。活动运行以新前缀失效，关闭运行可复用。

- [ ] 用计数 spy 写重复 open、不同 run 同 ID、工件变化、manifest/descriptor 变化、损坏缓存、活动运行追加、缺少写权限用例。
- [ ] 将源身份收集和投影构建分开；缓存命中时恢复 typed projection，缓存 miss 才 materialize。访问证据仍执行安全文件身份/内容验证。
- [ ] 运行列表使用可重建摘要，历史/未知格式安全回退；不为了展示列表对所有运行执行全部业务/上下文投影。状态不确定时显示 unknown，不能用旧缓存伪称 trusted。
- [ ] 缓存写入失败返回正确读结果和诊断；同一 key 构建合并，防止并发缓存击穿。不得在 runs 写缓存。
- [ ] 用测试断言：

```python
first = service.open_run(run_root)
second = service.open_run(run_root)
assert first == second
assert projection_build_spy.call_count == 1
assert materialize_spy.call_count == 1
```

- [ ] 运行 `uv run --project packages/grid-agent pytest packages/grid-agent/tests/trajectory/test_service.py packages/grid-agent/tests/trajectory/test_materialize.py packages/grid-agent/tests/trajectory/api/test_catalog.py -q`；对受控 fixture 测量 1k/10k/100k 事件冷/热请求。

**关闭条件**：热请求不重建/重写投影，变化正确失效；冷请求仍真实验证；记录实际复杂度，不承诺未经测量的毫秒数。提交主题：`perf: reuse verified trajectory projections`。

### OP-08：服务端限制工件和上下文预览

**Files**：Modify `packages/grid-agent/src/grid_agent/trajectory/api/artifacts.py`、`api/app.py`、`packages/trajectory-workbench/src/evidence/preview.ts`、`src/api/types.ts`；Test `packages/grid-agent/tests/trajectory/api/test_artifacts.py`、`test_app.py`、`packages/trajectory-workbench/src/evidence/preview.test.ts`。

**接口**：工件预览支持单一前缀 Range；服务端上限 131072 bytes，多段/非法范围明确拒绝。大文件全量下载与预览分离。上下文详情使用分页/截断字段，不把截断 JSON 当完整状态。

- [ ] 新增 8 MiB 和 64 MiB 已注册安全工件 fixture；请求 `Range: bytes=0-131071`，断言 206、Content-Range、长度以及完整源摘要失败时拒绝。
- [ ] 使用同一 no-follow fd 分块验证摘要并保留有界前缀；检测读取前后文件身份变化，失效重试有次数上限。未经全量验证不能声称 prefix 属于已验证工件。
- [ ] 全量下载如需缓冲，使用受限 spool 后发送已验证快照；禁止 unbounded bytes 读入内存；未知 media type 在读取前拒绝。
- [ ] 明确 unavailable/invalid/unverified/verified 状态：无明确准入记录者拒绝；重新验证成功若允许提升状态，必须返回新的验证状态并测试，不能只靠 UI 按钮禁用。
- [ ] 上下文大对象默认预览上限 131072 bytes，并返回字段级省略标记与安全工件入口；旧小对象响应兼容。API/前端类型、空/截断/错误视图同提交更新。
- [ ] 检查下列响应契约，再运行相关 Python/Node 测试与 `make test-workbench`。

```python
assert response.status_code == 206
assert len(response.content) <= 131072
assert response.headers["Content-Range"].startswith("bytes 0-")
```

**关闭条件**：服务端预览内存不随文件线性增长；首次摘要 I/O 仍可能线性，报告需明确区分；证据身份防护不退化。提交主题：`perf: bound artifact and context previews on the server`。

### OP-09：批量查询证据并保留错误状态

**Files**：Modify `packages/grid-agent/src/grid_agent/trajectory/api/app.py`、`api/projection_pages.py`、`packages/trajectory-workbench/src/api/client.ts`、`src/api/types.ts`、`src/app/App.tsx`、`src/audit/inspector-model.ts`；Test 各相邻现有测试文件。

**接口**：只读 GET 查询接收重复 ref 参数，每批最多 32 个，返回每引用 matched/missing/error 的判别状态；前端最多并发 2 批，仍绑定 run_id、selection key 与 AbortSignal。

- [ ] 新增 70 引用选择、某批失败、切换 run、旧响应迟到、重复 ref、超长查询和取消用例。
- [ ] API 对 ref 严格校验并在一次已缓存 projection 上批量索引，输出顺序与请求引用可匹配；未知引用不泄漏路径。
- [ ] 前端替换逐引用 Promise.all；成功批次保留，失败批次可明确重试，missing 与请求失败分别展示。
- [ ] 测试请求最多三批且峰值并发不超过二，错误不折叠为“没有证据”。

```typescript
expect(requests).toHaveLength(3);
expect(peakConcurrentRequests).toBeLessThanOrEqual(2);
expect(screen.getByText('部分证据加载失败')).toBeVisible();
```

- [ ] 执行 `make test-workbench` 及 `uv run --project packages/grid-agent pytest packages/grid-agent/tests/trajectory/api -q`；最后运行工作台 Playwright 行为测试。

**关闭条件**：请求有界、取消有效、部分成功可见、错误语义清晰。提交主题：`perf: batch evidence lookups with explicit partial failures`。

### OP-10：收紧类型接口与依赖契约

**Files**：Modify `packages/capability-agent-kernel/src/capability_agent/application/runner.py`、`domain/profile.py`；Create `packages/capability-agent-kernel/src/capability_agent/application/runtime_protocols.py`；Modify `tools/check_package_boundaries.py`、`docs/architecture/capstone-framework.md`；Test Kernel runner/public API 与 `tools/tests/test_check_package_boundaries.py`。

- [ ] 列出 runner 各注入点的实际生产调用与测试替身，按已有签名定义 ProviderSession、TurnController、PreparedApplication、ReportPublisher Protocol；不为未实现的多域功能增加抽象。
- [ ] 将 `_call_factory` 的反射适配限制于具名 legacy adapter；生产接口参数缺失在 provider 启动前报配置错误。新增丢失 projector/correlation/authority 参数的负例。
- [ ] 修复 `_domain_output_schema` 返回标注与真实 str 返回不一致等类型缺口；删除无效 object 联合，但不通过大量 cast 掩盖错误。
- [ ] 明确 Domain Pack 可导入 authority 的公开协议资源/规范化 API，禁止 raw simulator 内部。先记录 allowlist 与包版本测试，再评估是否需要独立 contracts 包；本包不复制两份 capability schema。
- [ ] 文档分别绘制代码依赖、运行调用和证据返回；维持四层职责。README 涉及同一事实时双语同步。
- [ ] 验证缺少必需调用参数稳定拒绝：

```python
with pytest.raises(ApplicationConfigurationError):
    build_application_with_incompatible_transport()
assert provider_start_spy.call_count == 0
```

该测试 helper 必须在测试文件中构造缺少生产 Protocol 必需参数的 transport，并走真实装配入口，不能直接 mock 配置错误。
- [ ] 执行 `make check-types`、`make check-package-boundaries`、Kernel 全测试和 `make test-packages`。

**关闭条件**：生产调用无静默丢参；装配失败可诊断；公开资源 API 与 raw 实现边界可测试。提交主题：`refactor: enforce typed application runtime seams`。

### OP-11：完成 inventory 的应用级 conformance

**Files**：Modify `packages/inventory-domain-pack/src/inventory_domain/profile.py`；Create 同目录 `provisioning.py`、`state.py`、`answer_policy.py`、`answer_admission.py`、`policy.py`、`guide.py`、`presentation.py`、`output.py`、`acceptance.py`；Create `packages/inventory-domain-pack/tests/test_application_conformance.py`；Modify `tools/test_package_artifacts.sh`、`configs/runtime/application-instantiation-protected-paths.json`。

**接口**：实现现有 DomainRuntimeProfile 八个完整应用组件及 OP-01 准入，复用公共 Kernel Protocol；测试中装配 ApplicationProfile，不注册 production grid CLI 的 inventory 模式。

- [ ] 从 `missing_application_components()` 为空开始写红灯，再加入两组独立问题：库存/资产查询与上下文复用、无效对象/外来引用/错误 authority 的受限结果。
- [ ] 提供真实 inventoryctl provisioner、状态验证、输出验证、报告片段、离线知识策略、接受案例声明；所有 current-run 数据由 reference authority 产生。
- [ ] 使用 scripted transport 但真实 executor/authority 跑 AgentApplication；验证答案、core、domains.inventory、报告失败降级及 replay。

```python
assert profile.missing_application_components() == ()
assert outcome.status == "completed"
assert set(outcome.result.domains) == {"inventory"}
assert replayed_context == stored_context
```

- [ ] 扩展干净 wheel 安装测试，从仓库外目录完整执行该应用；不得依赖 `validation/` 或源码树绝对路径来解析包资源。
- [ ] inventory 路径受 C.1 保护：先验证旧基线，记录允许变化的目录/理由/旧摘要，完成独立复审和不依赖 protected gate 的领域测试。先提交领域改动，再用 `git rev-parse HEAD:packages/inventory-domain-pack` 取得摘要更新当前配置并独立提交，然后执行完整门禁；中间两提交在集成分支不得视为 release。历史 Climb 配置与旧 closure 不变。
- [ ] 执行 `make test-inventory`、`make check-package-boundaries`、`make test-packages` 和更新后的 `make check-release`。

**关闭条件**：独立 Domain Pack 通过完整应用闭环，Kernel/generic Pi 不加入 inventory 特例。提交主题：`test: prove complete inventory application conformance`。

### OP-12：长运行基准与存储改造决策

**Files**：Create `tools/benchmark_optimization.py`、`tools/tests/test_benchmark_optimization.py`；Modify `Makefile`；不修改 context store 的持久化格式。

**接口**：`python tools/benchmark_optimization.py --events 1000 10000 100000 --output runs/optimization/benchmarks/report.json`，报告包含环境、源码、规模、重复次数、p50/p95、读取/写入字节和峰值内存。命令通过 grid-agent 的 uv 环境运行。

- [ ] fixture 采用合法事件生成器，三个规模使用相同事件分布/工件大小；临时目录隔离，重复三次，禁止读取用户业务运行做默认基准。
- [ ] 测量 context append_many、replay、列表、冷/热投影、预览；用计数器统计逻辑 I/O，时间与 RSS 作为辅助指标。
- [ ] 验证 10 倍事件量下的写入倍率；若连续两个规模的累计账本写入倍率均 >30，或每新增事件平均账本写入增长 >3 倍，则触发 OP-13。阈值是本计划的工程预算，不是既有性能事实。
- [ ] 将数据、结论和原始日志摘要写入本计划执行记录；未触发时 OP-13 标 NOT_NEEDED，并保留完整性设计。
- [ ] 运行 benchmark 自测，再运行三规模命令；规模太大无法完成时记录资源上限和失败规模，不能删掉失败点。

```sh
uv run --project packages/grid-agent pytest tools/tests/test_benchmark_optimization.py -q
uv run --project packages/grid-agent python tools/benchmark_optimization.py --events 1000 10000 100000 --output runs/optimization/benchmarks/report.json
```

**关闭条件**：可复现数据、明确分支决策；时间预算不能替代正确性门禁。提交主题：`perf: establish reproducible long-run resource budgets`。

### OP-13：触发后实现分段事务日志

**Files**：Modify `packages/capability-agent-kernel/src/capability_agent/application/context_store.py`、`application/workspace.py`；Create `packages/capability-agent-kernel/src/capability_agent/application/context_segments.py`；Test `packages/capability-agent-kernel/tests/application/test_context_store.py`。

**固定格式方向**：新运行采用版本化不可变 transaction segment；每组 append_many 对应一个 segment，含起止 revision、previous/next state hash 和 payload digest。一个原子更新 manifest 指向已提交 segment；snapshot 是可重建投影。旧运行继续旧 reader，不自动迁移。

- [ ] 实现前把格式字段、commit point、读者兼容矩阵补入本包执行记录并复审；不改变公共 ContextEvent 的领域语义。
- [ ] 依次实现 segment stage → fsync → rename → directory fsync → 原子 manifest commit → snapshot refresh。manifest 提交前中断丢弃未提交 segment；提交后从 segment 重建 snapshot。
- [ ] 注入每个持久化边界的异常/强制退出；覆盖截断尾部、重复 revision、哈希不匹配、symlink 替换、并发 writer、snapshot 落后和无空间；不能把异常都降级为报告警告。
- [ ] 保留旧格式读取、已有 run-id 防重用和信任边界；只有新 workspace 选择新 writer。
- [ ] 执行 recovery 矩阵的核心断言：

```python
assert recovered.revision in {before.revision, committed.revision}
assert recovered == replay_committed_segments()
assert no_partially_committed_transaction()
```

测试 helper 应读取真实 manifest/segments 并使用独立 replay，不能直接返回 writer 的内存状态。
- [ ] 重跑 OP-12；相同三个规模累计日志写入应近似线性，10 倍规模倍率 <=15；再执行 `make check-release`。未达性能目标或恢复不等价则不能切新 writer。

**关闭条件**：新格式恢复证明、旧格式兼容、资源目标全部达成。回退只影响新写入选择，保留已经产生的新格式 reader，禁止删除运行数据。提交主题：`perf: commit context transactions as immutable segments`。

### OP-14：综合关闭与第二正式领域选择入口

**Files**：Modify 本计划、`docs/status/CURRENT-STATE.md`、`docs/status/RESUME-NEXT-SESSION.md`、`docs/status/JOURNAL.md`、`docs/status/DECISIONS.md`、`docs/status/INDEX.md`；需要更新产品事实时同步 README 双语和 RUNBOOK。

- [ ] 核对 R01–R13 每项都有已完成包或有依据的范围说明；OP-13 可 NOT_NEEDED，不能空置。OP-06 未关闭则整体 release 不得通过。
- [ ] 在集成 HEAD 执行 `make doctor`、`make check-release`、`git diff --check`，记录所有失败与最终重跑；不能拼接不同源码版本的通过日志。
- [ ] 独立复审答案信任、报告失败、路径/凭据、缓存失效和事务恢复；清零高优先级发现，确认测试没有削弱原契约。
- [ ] 更新用户文档的保证范围：lineage 验证、确定性事实展示、自由文本解释、报告状态各自说明，不能宣称通用语义证明。
- [ ] C.2 只进入候选选择：重新验证 GitHub authority 边界、API 版本/分页/新鲜度/权限、两个独立任务集和授权外部探针需求。选择记录完成前不添加正式 Domain Pack。
- [ ] 完成条件写入 DECISIONS/JOURNAL，并将 RESUME 指向具体下一步；此包不自动启动付费验证或外部发布。

**关闭条件**：源码版本、门禁、证据和文档一致，真实待办没有隐藏在“全部完成”中。提交主题：`docs: close Capstone optimization acceptance`。

## 6. 验收门禁与兼容矩阵

OP-05 之前使用当前已有命令；新增 check-* 目标不能在尚未实现时当成可运行命令。

```sh
make doctor
uv run --project packages/grid-agent pytest packages/capability-agent-kernel/tests -q
uv run --project packages/grid-agent pytest packages/pandapower-domain-pack/tests -q
npm test --prefix packages/pi-capability-tools
make test
make test-inventory
make test-workbench
make test-e2e
make validate
make validate-application
make check-application-boundaries
make check-protected-paths
git diff --check
```

行为变化按 AGENTS 至少执行 doctor/test/test-e2e/validate；OP-02/03/11 必须另跑 validate-application；包资源/SPI/版本变化必须 test-packages；UI 变化必须工作台类型、单测和相关 Playwright。文档变更检查本地链接、CLAUDE 相对 symlink、diff whitespace 和 doctor。

| 场景 | 必须保持的结果 |
| --- | --- |
| 正常 grid 单问 / 连续 / generic | 相同权威证据规则，各自公开格式不变 |
| offline 普通知识 | 明确确定性知识路径，不制造 simulator evidence |
| 无引用业务断言 | limited 或拒绝，不获得事实保证 |
| 有效引用但模型文本错误 | 不宣称语义已验证；确定性事实展示保持真实值 |
| 证据伪造 / 错 run / 错场景 | 领域准入失败，不能被 reporting fallback 掩盖 |
| 报告 / observer / cache 失败 | 主答案不撤销，诊断明确 |
| 活动运行 / 旧格式 / 损坏尾部 | 展示可信前缀及限制，不把缓存当权威 |
| 大工件 / 长轨迹 | 响应、并发和内存有界，限额及省略可见 |
| 干净安装 / 隔离 worktree | 不依赖其他工作树的认证、缓存或源码路径 |

## 7. 回退与范围变更控制

- 回退代码用任务级 revert；不得 reset 用户工作树，不删除 runs、var 或原始证据。
- OP-01/02 回退会恢复可信度缺口，应在账本明确重新打开 R01/R02，不能沿用关闭状态。
- OP-03 回退重新打开报告故障问题；不把已生成答案改写成失败。
- OP-07/08/09 可以关闭新缓存/查询分支，读原始来源；只清理精确识别的可重建缓存，需记录范围。
- OP-06 回退不能绕过过期风险门；OP-13 回退保留新格式 reader。
- 对新增外部系统、公开 schema 不兼容、多域、写操作、存储迁移、权限扩大：先更新范围与设计决策，再实施；这不影响已授权的常规修复推进。
- 保护基线变更必须列旧/新摘要、理由、测试和复审。禁止一条“重新生成所有 baseline”掩盖跨包变更。

## 8. 执行记录格式

每包完成时在本节追加一项，表格状态同步更新。报告文件使用实际路径；尚未执行不能填虚构报告。

```text
Package: OP-xx
Source commit(s): 实际提交 SHA
Scope: 实际修改文件与接口
Verification: 实际命令、退出码、首次失败和最终结果
Evidence: 实际 runs/optimization 路径及摘要
Review: 发现、解决方式和剩余风险
Compatibility: schema/CLI/历史运行影响
Decision: DONE / BLOCKED / NOT_NEEDED 与理由
Next: 唯一下一工作包
```

2026-09-05 初始记录：方案编制时尚未启动实现。随后用户授权持续实施，当前状态以上表为准。

### OP-04 验证记录（2026-09-05）

- Source commit: `9d13ea4`，仅测试夹具改动，无生产 RPC 修改。
- Verification: 两个 focused 测试通过；协议用例连续 30/30 通过；runtime 测试集 72 passed。首次单次旧夹具通过，未声称确定性复现旧竞态。
- Commands: `uv run --project packages/grid-agent pytest packages/grid-agent/tests/runtime/test_rpc.py::test_rpc_requires_ack_before_agent_end packages/grid-agent/tests/runtime/test_rpc.py::test_rpc_reports_prompt_send_failure_when_provider_exits_early -q`；按本包命令循环 30 次；`uv run --project packages/grid-agent pytest packages/grid-agent/tests/runtime -q`。
- Evidence: `runs/optimization/OP-04/task-report.md`；`runs/optimization/OP-04/review.diff`。报告误列的旧 SHA `2c2b639` 已更正；误强制跟踪的报告取消跟踪但保留本地文件，版本化摘要保存在此。
- Review: 独立审查中；Decision: VERIFYING，尚不标 DONE。
- Next: OP-01 继续，OP-02 仅只读映射，依赖未闭合前不实施。
