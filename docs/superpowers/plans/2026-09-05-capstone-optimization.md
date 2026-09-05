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
- 当前执行包：OP-08（A已验收；B0隔离原型与验证已获用户“同意”，不授权生产集成或新增依赖）；OP-13 B继续BLOCKED，独立复审未完成。全方案未完成。执行分支 feat/capstone-optimization，隔离目录 .worktrees/capstone-optimization。
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
| OP-01 | 1 | 答案模式、领域准入、事实保证范围 R01 | 无 | DONE | cbc6d97；独立复审、定向66及固定源码完整门禁通过，详见任务验收记录 |
| OP-02 | 1 | 单问 run 统一提交 R02 | OP-01 | DONE | c81c83a；独立复审、focused91+3/17、固定源码完整门禁通过，详见验收记录 |
| OP-03 | 1 | 报告与观察故障隔离 R03 | OP-01 | DONE | 6ad5df4；独立复审与固定源码完整主/包门禁exit0，详见验收记录 |
| OP-04 | 2 | RPC 测试竞态 R11 | 无 | DONE | 9d13ea4；focused2 / 30次重复 / runtime72通过，独立规范与质量复审PASS |
| OP-05 | 2 | 全包门禁、类型检查、CI R04 | OP-02, OP-03, OP-04 | DONE | 2ce5152；独立复审及固定源码完整check-release exit0，详见验收记录 |
| OP-06 | 2 | Pi 风险例外关闭或明确阻断 R12 | OP-05 | DONE | 41b48d0；真实0.84.4/三锁零审计/捕获独立复审及固定完整release exit0 |
| OP-07 | 3 | 投影缓存、轻量运行列表 R05 | OP-05 | DONE | 7638188；独立复审、三规模测量、固定完整release exit0 |
| OP-08 | 3 | 有界工件与上下文预览 R06 | OP-07 | RUNNING | A已验收b7b49f6；B0私有隔离原型/验证已批准，生产B/C/D仍未完成 |
| OP-09 | 3 | 批量证据与明确错误状态 R10 | OP-07, OP-08 | PLANNED | 未执行 |
| OP-10 | 4 | 类型化执行接口与依赖说明 R09,R13 | OP-05 | DONE | d5eec21；最终复审PASS，固定完整doctor/check-release exit0，详见验收记录 |
| OP-11 | 4 | 完整 inventory 应用验收 R08 | OP-01, OP-03, OP-10 | DONE | 416a04d实现/218b672独立摘要；119测试/复审/真实六wheel及固定完整release exit0 |
| OP-12 | 5 | 长运行基准与存储决策 R07 | OP-07, OP-10 | DONE | de3a5c7九样本/实测复审/固定完整release PASS，100.339/100.490写入倍率触发OP13 |
| OP-13 | 5 | 条件性分段日志实现 R07 | OP-12 确认触发 | BLOCKED | A已验收3bc24a2；B未验收，572全Kernel/类型、Linux126定向通过；整体独立复审服务中断，C/D未开始、默认仍legacy |
| OP-14 | 5 | 综合关闭与 C.2 选择入口 | OP-01–12，OP-13 disposition 已记录 | PLANNED | 未执行 |

默认执行顺序：01 → 02 → 03 → 04 → 05 → 06 → 07 → 08 → 09 → 10 → 11 → 12 → 条件 13 → 14。
2026-09-05调度补充：OP08额外跨层范围待用户批准时，按已满足的依赖推进独立OP10；不把自动续行视为OP08批准，不启动依赖OP08的OP09。OP10既有范围保持不变。
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

实施澄清（2026-09-05）：离线生产路径采用领域通用概念目录、已发布知识来源和明确的信息请求语法；自然语言概念解释必须可达，`guide:<id>` 只可作为补充入口。不得枚举测试问题、网络或预期答案；混合业务请求不能被宽泛关键词误判。仅确定性来源文本可以获得 `deterministic_information`，模型生成文字不参与该判定。侧车除绑定 `answer_ref` 外，其自身摘要须由已提交事件记录并在读取时核对；“历史答案从未声明侧车”与“已提交侧车丢失/损坏”必须区别处理。单独改写侧车、模式/保证配对不合法及路径替换都不得提升保证等级。

- [x] 新增参数化红灯用例：无工具数值断言、无工具拓扑断言、错误单位/错误场景的有效引用、跨轮未消费引用、空答案、正常真实结果、普通离线知识、无法判定的问题。前四类不能获得“事实已验证”状态。
- [x] 固定策略：默认业务问题为 authority_backed；无当前轮有效结果时 limited。offline_information 只由领域确定性知识路径识别并生成回答，不由模型自报模式，也不通过数字/网络名正则猜分类。其余模糊问题返回 limitation 或继续获取证据。
- [x] 准入返回的 reader text 由 controller 提交；limited 采用现有受限答案语义，不伪装 success。为普通知识问答保留领域知识来源且不制造运行证据。
- [x] 对有有效引用的自由文本只声明 lineage_verified。新增对抗验收，将真实结果保持不变而替换文本数值/单位/排序，确保 audit 不把它标为“数值验证通过”。需要精确事实展示时由 Domain Pack 根据已验证结果渲染事实表，标注模型解释的保证范围；不解析自由文本后据此创造事实。
- [x] 将准入模式/保证范围保存在版本化应用答案旁路元数据并关联 answer_ref；旧答案读者缺少该字段时显示 unknown，不猜测。不要直接给严格旧 schema 塞字段。
- [x] 执行下列命令，预期新增测试先失败、实现后全部通过；复审策略不会封死正常离线信息，也不会由模型 bypass。

```sh
uv run --project packages/grid-agent pytest packages/capability-agent-kernel/tests/application/test_turns.py -q
uv run --project packages/grid-agent pytest packages/pandapower-domain-pack/tests/test_answer_policy.py -q
uv run --project packages/grid-agent pytest packages/grid-agent/tests/e2e/test_answer_admission.py -q
make validate-application
```

**关闭条件**：零投影也有明确领域准入；可追踪模式；文本语义保证没有被夸大；权威事实仍来自 gridctl。提交主题：`fix: enforce domain answer admission before commit`。

验收记录（2026-09-05）：最终生产提交 `cbc6d97`（OP-01范围自 `323dd7d` 后），前序功能提交 `884e07d`、`678d8d6`、`f70d0de`、`33ba380`，读取修复 `1200963`、`acaef08`、`cbc6d97`。Sol逐项复审前序实现；最后读取修复由Sol实施、root独立代码与测试审查通过。固定源码门禁均exit0：doctor、agent741、simulator165、Pi/Makefile、E2E31、offline/scripted、24/24覆盖；另Kernel413、Domain74、应用验收、六wheel/两npm干净安装通过。root独立定向66通过；真实grid报告含Guarantee scope和lineage_verified。证据：`runs/optimization/OP-01/gate-{main,packages}-cbc6d97.json`、`final-review-cbc6d97.md`。所有已知Important结清；该结论不代表自由文本数值语义已验证、不关闭OP-06风险例外。

### OP-02：让单问 run 使用同一提交器

**Files**：Modify `packages/grid-agent/src/grid_agent/cli/app.py`、`packages/grid-agent/src/grid_agent/compat/v1_0_1.py`；Create `packages/grid-agent/src/grid_agent/compat/single_run.py`；Test `packages/grid-agent/tests/cli/test_run_command.py`、`packages/grid-agent/tests/cli/test_app.py`。

**接口**：适配器接受现有 RunRequest 和解析后的运行配置，组装只有一个 question 的 ApplicationRequest，调用 AgentApplication；从已提交答案进行两字段投影，不能返回未经提交的 Pi 文本。

夹具迁移补充（2026-09-05）：额外Modify/Test `validation/run.py`、`packages/grid-agent/tests/validation/test_run_harness.py`、`packages/grid-agent/tests/e2e/test_semantic_pi_path.py` 与 `test_offline_walking_skeleton.py`，适配实际descriptor和typed语义事件。原单问未配置请求捕获通道，legacy report仍必须验证完整请求/ACK，不把捕获新功能混入本包。验证器以稳定调用ID合并start/result计数，保留全部能力观察和旧无ID轨迹；三个真实调用不得因五条事件被误计为五次调用、造成预算假超限。

进度兼容补充（2026-09-05）：统一执行器时不得丢失已发布的provider/model/timeout/retry启动摘要及等待心跳。增加最小中立Kernel运行时事件 `application_provider_resolved`（仅允许安全配置标量）与 `application_waiting`，应用既有ProgressReporter消费；唯一resolve/start路径不变，不重新在适配器解析配置。额外Modify/Test限定 `packages/capability-agent-kernel/src/capability_agent/application/runner.py` 与其 `tests/application/test_runner.py`。事件不提供模型能力、不引入grid语义；observer失败隔离仍由OP-03闭合。

实施设计补充（2026-09-05，只读调查，未启动实现）：保留 canonical `core/domains/turns/output` 布局；由应用适配器将 `core/events.jsonl`、`domains/grid/tool-results/`、`domains/grid/evidence/` 发布为旧根路径的字节保持实体快照。副本不成为 authority 输入，不使用 symlink/hardlink，不将 domain authority 扩大到 run 根。完整成功交付须保留旧路径；发布失败不得删除已提交 canonical 答案。普通离线知识/确定性无执行限制在创建 workspace 前返回，无 provider、无 authority、无 run evidence；在线及 simulator-backed 请求统一 controller 提交。应用投影从同次验证的提交事件和摘要绑定答案读取，不信任 outcome 的展示文本。同步 RUNBOOK 和双语 README 解释 canonical 与兼容副本。备选 eager mirror 增加工具路径事务耦合，暂不采用；通用 domain export SPI 超出单应用兼容需求，暂不新增。

- [x] 记录现有 question_id、退出码、stdout、stderr、provider/model/base_url/api_key_env、offline 的兼容矩阵；写无引用/伪引用、provider 中断、重复 ID、非法 ID 回归测试。
- [x] 提取单问适配器；配置解析复用原产品规则；run_id 对齐 question_id，既有 evidence 路径如需桥接由应用投影完成。不能静默改变调用方依赖的 paths。
- [x] 让在线 run 经过 OP-01 准入和 controller 提交；普通 offline 知识走确定性路径；offline simulator smoke 继续真实 authority 调用并保存引用。
- [x] 使用实际 CLI runner 捕获 stdout，执行以下断言；对错误也检查 envelope 和非零退出码。

```python
payload = json.loads(result.stdout)
assert set(payload) == {"question_id", "answer_output"}
assert payload["question_id"] == requested_question_id
assert isinstance(payload["answer_output"], str)
```

- [x] 运行 `uv run --project packages/grid-agent pytest packages/grid-agent/tests/cli -q` 和 `make test-e2e`；旧命令、离线知识与真实 gridctl 夹具全部通过后，删除这一路重复的启动/提交代码。

**关闭条件**：成功答案可追溯到提交记录；公众 envelope 不变；不能以“至少调用过一个工具”代替问题相关证据。提交主题：`refactor: route single runs through application answer commits`。

验收记录（2026-09-05）：提交 `8e880ed`（安全实体快照）、`30e9270`（统一提交/进度）、`c81c83a`（scripted夹具/验证调用计数）；完整范围自 `f70ed3d` 后。独立Spec/Quality PASS，root聚焦91+3及最终17通过。固定c81c83a主/包两链exit0：doctor、agent775、sim165、Pi/Makefile、E2E31、offline/scripted、24/24；Kernel415、Domain74、应用验收、六wheel/两npm干净安装通过。证据 `runs/optimization/OP-02/gate-{main,packages}-c81c83a.json` 和 `final-review-c81c83a.md`。先前30e9270主链770通过2失败记录保留，不改写。普通离线知识无run；单问原有请求捕获缺省不被误报为新实现；legacy report完整capture/ACK仍验证。未调用付费provider，未关闭Pi风险例外。

### OP-03：将报告发布与主答案状态分离

**Files**：Modify `packages/capability-agent-kernel/src/capability_agent/application/runner.py`、`application/reporting.py`、`application/output.py`、`packages/grid-agent/src/grid_agent/compat/v1_0_1_report.py`；Test `packages/capability-agent-kernel/tests/application/test_runner.py`、`test_reporting.py`。

**接口**：新增报告发布结果，主结果继续使用已有可空 report_ref 和 diagnostic_refs；Kernel输出schema保持 `capability-agent-output/1.0`。

实际领域契约澄清（2026-09-05）：真实app红灯发现pandapower输出1.0强制要求已接纳报告。独立评审后显式使用 `pandapower-static-analysis-output/1.1`，保留五字段和mode/count检查，允许无报告时null；非null仍严格格式/当前run准入，不伪造占位工件。额外Modify `packages/pandapower-domain-pack/src/pandapower_domain/output.py`；Test其 `tests/test_output.py`、`test_profile.py`，以及grid的 `tests/cli/test_run_command.py`、`tests/e2e/test_generic_pandapower_application.py` schema断言。历史C.1规格和兼容测试的合成1.0输入保留。同步双语README、RUNBOOK、PANDAPOWER-APPLICATION、MANUAL-VALIDATION及capability-composition架构说明；决定记录在DECISIONS。

安全写入澄清（2026-09-05）：现有报告writer的祖先检查与路径写入之间可被替换成symlink，已通过outside内容被覆盖的RED复现。新增Kernel `application/_report_files.py`，逐级dirfd绑定、私有临时写入、stage身份校验及同父发布；仅替换报告writer，不扩展通用存储SPI。新增 `tests/application/test_report_files.py`、`test_diagnostics.py`、`test_failure_isolation.py` 验证竞态、固定诊断和主/派生故障矩阵。

实施边界补充（2026-09-05）：包括可选report-shell prepare，不仅是提交后的render；包括OP-02新增provider/waiting观察事件。`_call_prompt`只隔离observer，先执行的projector.observe仍属必要准入/持久化。report引用登记失败若store仍健康可返回unavailable；若真实I/O已破坏store，必要application.completed事务仍须失败，不能用宽泛mock或catch假报完成。应用侧验收增加 `packages/grid-agent/tests/application/test_generic_entrypoint.py`，验证真实pandapower报告壳失败不撤销已提交答案和可用answers.jsonl。

```python
from dataclasses import dataclass
from typing import Literal

@dataclass(frozen=True)
class ReportPublication:
    status: Literal["published", "unavailable"]
    report_ref: str | None
    diagnostic_codes: tuple[str, ...]
```

- [x] 将现有报告 symlink 测试拆成两个断言：拒绝越界写入、已接受答案仍可返回。新增 renderer 异常、checkpoint I/O 异常、final admission 异常、observer 异常及答案主记录 I/O 异常。
- [x] 在明确的展示边界捕获普通异常，返回 unavailable、report_ref=None；保留安全拒绝，不跟随 symlink，不改变外部文件。
- [x] 诊断采用固定 code 与运行关联；如诊断工件写入也失败，仅尝试安全 stderr。KeyboardInterrupt/SystemExit 正常传播，cleanup 不覆盖主异常。
- [x] 逐题报告失败后继续下一题。只在答案与必要状态提交成功后标 completed；不能捕获整个业务流程并无条件返回成功。
- [x] 执行参数化用例中的核心断言：

```python
assert outcome.status == "completed"
assert outcome.completed_questions == 2
assert outcome.result.core.report_ref is None
assert len(outcome.result.core.answer_refs) == 2
assert outside_file.read_bytes() == outside_before
```

- [x] 运行 `uv run --project packages/grid-agent pytest packages/capability-agent-kernel/tests/application/test_runner.py packages/capability-agent-kernel/tests/application/test_reporting.py -q`，再执行 `make validate-application`；验证应用 answers.jsonl 不被展示失败撤销。

**关闭条件**：展示失败可诊断且不阻断有效答案；必要证据失败仍阻断。提交主题：`fix: isolate report publication from accepted answers`。

验收记录（2026-09-05）：生产提交 `6ad5df4`，范围自 `68c5282` 后。独立生产/安全/文档复审PASS；固定源码完整主链exit0：doctor、agent778、sim165、Pi43/Makefile、E2E31、offline/scripted、24/24；包链exit0：Kernel437、Domain79、应用验收及六wheel/两npm干净安装。定向应用25及独立50通过。证据 `runs/optimization/OP-03/gate-{main,packages}-6ad5df4.json`、`final-review-6ad5df4.md`。展示故障不撤销有效答案，必要提交仍阻断；domain schema1.1显式允许null报告，core1.0及公众两字段不变。未运行付费provider；Pi风险例外仍待OP-06。

### OP-04：修复 RPC ack 测试夹具竞态

**Files**：Modify/Test `packages/grid-agent/tests/runtime/test_rpc.py`；检查 `packages/capability-agent-kernel/tests/runtime/test_rpc.py` 是否存在同一夹具。

- [x] 在 fake Pi 中先读取完整 prompt，再输出故意缺少 ack 的 agent_end，使该测试只测协议顺序。

```python
fake.write_text(
    "import json, sys\n"
    "sys.stdin.readline()\n"
    "print(json.dumps({'type': 'agent_end'}), flush=True)\n",
    encoding="utf-8",
)
```

- [x] 用 try/finally 保证 client.stop；另设提前退出用例验证发送失败路径，不能扩大原 regex 接受两种错误。
- [x] 连续运行 30 次，再跑 runtime 测试集；一次失败就保留日志，不能 retry-until-green。

```sh
for attempt in $(seq 1 30); do
  uv run --project packages/grid-agent pytest packages/grid-agent/tests/runtime/test_rpc.py::test_rpc_requires_ack_before_agent_end -q || exit 1
done
uv run --project packages/grid-agent pytest packages/grid-agent/tests/runtime -q
```

**关闭条件**：原协议错误断言稳定；提前退出独立覆盖；无遗留子进程。提交主题：`test: synchronize RPC protocol violation fixtures`。

### OP-05：完整且可重复的工程门禁

**Files**：Modify `Makefile`、`packages/grid-agent/pyproject.toml`、其 `uv.lock`、`README.md`、`README.zh-CN.md`、`docs/RUNBOOK.md`；Create `pyrightconfig.json`、`.github/workflows/verify.yml`；Test `tools/tests/test_verification_targets.py`（新增）。

类型基线范围澄清（2026-09-05）：固定pyright1.1.408、standard、最低Python3.12覆盖六包217生产文件，初始123错误。允许逐点修正Kernel application/composition/output/runner/turns、domain/provisioning、runtime/catalog/lock、tools/catalog；grid-agent cli/app、compat/single_run/v1_0_1_report、config/catalog、knowledge/offline、reporting、validation/oracles；simulator analyses、bindings/diagnostic/topology、creators、derived_results、models、operations、queries、results；inventory resources缓存返回注解。协议只澄清已有只读属性与实际factory返回类型，不提前替代OP-10执行接口设计。只保留Kernel output.py三处精确reportIncompatibleMethodOverride例外以保持既有公开schema属性/线协议；无整包exclude或全局ignore。受保护simulator与inventory的类型修复均独立审查、代码提交，再单独变更摘要。已完成测试/锁基线52e58da→摘要a49c73e，以及simulator类型d4315a0→摘要f6cfd01；旧新tree在runs/optimization/OP-05/*-digest-change.md留证，尚不代表本包完整验收。

补充已复现基线修复：`packages/inventory-domain-pack/tests/test_profile.py` 仍期待领域目录内的旧 `inventory_record_decision`；在 OP-01 前 `323dd7d` 导出源码上同样失败。OP-05 需将该测试对齐已存在的 domain/core 分离契约，并保留独立 neutral core 工具断言，不恢复旧别名、不仅删除断言。范围仅该 conformance 测试及 `configs/runtime/application-instantiation-protected-paths.json` 的对应受保护摘要；先校验旧摘要、独立复审测试改动并提交，再以该提交tree摘要独立更新基线，运行完整门禁。此项不提前实现 OP-11 的应用组件；证据 `runs/optimization/OP-05/inventory-baseline-failure.md`。

**接口**：保留已有目标，新增三个稳定聚合入口。Python 包分别执行，避免同名模块合并收集。pyright 作为 dev dependency 锁定；禁止全局 ignore 降低门槛。

上述 inventory 基线修复同时纳入其 `uv.lock`：诊断发现它缺少 Kernel 已有 filelock/python-dotenv 依赖元数据，普通 `uv run` 会自动刷新。OP-05 要显式锁定并验证 frozen 执行，纳入同一受保护范围复审；本轮诊断产生的自动锁改写已经还原，未暗中更新保护基线。

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

- [x] 新测试读取 Make dry-run，验证六个 Python 包、两个 Pi 包和工作台都有入口，且目标不存在递归环。
- [x] 将 `make test` 扩展为完整离线单元入口，显式依赖 test-agent、test-simulator、test-tools、test-makefile-application、test-kernel、test-domain-package、test-generic-tools、test-inventory、test-workbench；保留独立 test-e2e/validate 的集成含义，清除同一调用图的重复执行。test-agent 是否已包含 e2e 在 dry-run 与 pytest collection 中核对，聚合命令不得遗漏或无意重复。
- [x] pyright 配置覆盖 Kernel、两个 Domain Pack、两个 authority、grid-agent 的 src；测试替身后续逐步类型化，生产代码不以排除整包通过。修复基线类型问题分独立提交，记录每个豁免路径与理由。
- [x] CI 运行 checkout → Python/Node 版本准备 → make setup → make install-pi → make doctor → 三层检查。固定 Python 3.12 和当前实际 3.14 验证线，Node 满足 >=22.19.0；macOS/Linux 分开记录，视觉金图按平台管理。
- [x] CI 不使用 provider secrets，不发在线推理；Node/Python 下载是安装步骤。流水线配置先在本地做等价验证；未实际运行远端 CI 时不声称远端通过。
- [x] 运行 `make -n check-release`、`make check-fast`、`make check-integration`；聚合命令任一子目标失败即非零。

**关闭条件**：全部生产包被门禁覆盖，文档准确，整套结果稳定；不把历史 Climb 的 100 分当作本次 release 证据。提交主题：`build: gate all framework and application packages`。

验收记录（2026-09-05）：固定门禁提交 `2ce5152`，前序类型与受控保护摘要提交见本包记录及 `2e5ece6`→`2a81535`。独立Spec/Quality审查全部PASS；`make doctor && make check-release` exit0：pyright217文件零错误，Agent747、sim165、Kernel437、pandapower79、inventory service11/domain13/transport1、Pi43/34、workbench128、自检6、E2E31、offline/scripted及24/24、完整应用、六wheel/两npm干净安装、frozen源码npm安装全部通过。根证据 `runs/optimization/OP-05/gate-release-2ce5152.json`，审查 `gates-review.md`、`kernel-grid-types-review.md`、`simulator-types-review.md`。本地Darwin arm64/Python3.14.3/Node23.11.0；CI Linux/macOS×Python3.12/3.14/Node22.19.0仅配置，未声称远端或完整矩阵已经执行。未调用付费provider，Pi例外仍待OP06。

### OP-06：Pi 升级与到期风险处置

**Files**：Modify `configs/runtime/pi-runtime.lock.json`、`configs/runtime/pi-security-risk-exception-v1.json`、`packages/pi-capability-tools/package.json`、`packages/pi-capability-tools/package-lock.json`、`packages/pi-grid-tools/package-lock.json`；检查 `configs/runtime/patches/pi-0.80.6-before-model-request.patch` 的版本兼容性；Test `tools/tests/test_runtime_risk_exception.py`、两套 Pi capture tests。

实施控制澄清（2026-09-05）：上述例外文件改为**保留原文**，不更新旧版本漏洞计数或到期日。新增独立 `configs/runtime/pi-security-remediation-v1.json` 绑定真实替代版本的 source/npm integrity/patch、托管源码与两个扩展的三份完整 lock 字节摘要及平台无关依赖图。新 patch 使用独立版本文件名；旧 patch 保留。实际候选构建需要扩展 Kernel installer 的构建顺序，并安全保留含旧 patch 或未知修改的 managed source 后建立新目录；真实 Git 回归必须覆盖此升级路径。

安全状态的顺序为：实际安装 → 三份 frozen lock 的新鲜完整审计（六项 severity/total 均零且漏洞列表为空）及真实 patched SDK 捕获验证 → 保存精确 remediation 记录 → 固定源码完整 release 验收。记录不预先断言未来 release 已通过；默认检查器仅本地验证，不触发网络审计或 provider。捕获验证须绑定所测 runtime commit、patch 摘要和明确通过结果；安装图区分实际依赖根与包内 metadata，普通包不得借符号链接逃逸。检查器回归纳入 Make 常规门禁。详细设计和独立审查证据在 `runs/optimization/OP-06/`；本段是版本化的执行依据。

补充实际升级触点（只读调查）：还须同步 `packages/capability-agent-kernel/src/capability_agent/runtime/lock.py` 的active pin校验、`packages/pi-capability-tools/src/model-request-capture.mjs` 的capture身份、`packages/pi-grid-tools/package.json`、`tools/check_runtime_risk_exception.py`、`tools/test_source_setup.sh`，以及相关installer/locator/capture/package测试和第三方声明/当前运行文档。不要机械替换历史记录或仅用于通用身份传播的旧版本测试值。候选研究与官方来源见 `runs/optimization/OP-06/version-research.md`；0.84.4仅为优先本地验证候选，尚未选择或关闭风险。原hook在候选中仍未上游提供，必须按实际SDK控制流重写并验证patch。

- [x] 用 `rg --files configs/runtime` 和 runtime locator 确认 `pi-runtime.lock.json` 及其中 package/source/patches 摘要；旧版本专用 patch 不能原样套在新版本，按实际 hook API 更新版本化 patch 和摘要。
- [x] 检查当前官方 Pi release/API 与依赖审计，按现有例外的 >=0.84.3 下限挑选首个能满足全部 hook/extension 契约的版本；将选定版本、审计日期和理由写入执行记录。
- [x] 在隔离环境更新统一版本和 frozen locks；保留 canonical request hook、descriptor、correlation、stdout、受限工具和凭据过滤回归。
- [x] 执行 `make install-pi`、`make doctor`、`make check-release`，并执行更新后的依赖审计；禁止仅改 risk_counts 或删除 advisory 让门变绿。
- [x] 修复确认后关闭例外；如果没有合格版本，标 BLOCKED 并明确发布阻断，到期门继续失败；不能自行延期例外或声称漏洞已修复。

**关闭条件**：升级证据及风险状态明确。2026-09-30 前未关闭则发布被阻断；不强迫无证据升级。提交主题：`build: upgrade validated Pi runtime and close risk exception`。

验收记录（2026-09-05）：固定源码 `41b48d0` 的 `make doctor && make check-release` exit0，完整原始输出 `runs/optimization/OP-06/gate-release-41b48d0.json`。类型零错误；agent749、sim165、Kernel438、pandapower79、inventory11/13/1、Pi34/43、workbench128、门禁自检16、真实SDK捕获四例、E2E31、offline/scripted及24/24、完整应用、六wheel/两npm干净安装与frozen源码安装全部通过。安装器真实Git升级回归、hook、checker、捕获smoke、记录/文档集成均独立复审PASS，证据同目录。三锁新鲜audit六项计数零且漏洞列表空；版本化remediation精确绑定其源码/补丁/依赖图与捕获结果，原0.80.6例外和patch未改。旧managed源码保留为source-preserved目录，认证/var未动。记录当前替代版本的风险闭合，不声称旧版本漏洞消失或未来无新advisory。运行环境Darwin arm64/Python3.14.3/Node23.11.0，包安装烟测另用Python3.12.12；未声称远端CI矩阵全跑，未调用付费provider。上游deprecation等警告保留在原始证据中。

### OP-07：使投影缓存有效，运行列表轻量化

**Files**：Modify `packages/grid-agent/src/grid_agent/trajectory/service.py`、`materialize.py`、`api/catalog.py`；Create `packages/grid-agent/src/grid_agent/trajectory/cache_identity.py`；Test `packages/grid-agent/tests/trajectory/test_service.py`、`test_materialize.py`、`test_cache_inputs.py`、`api/test_catalog.py`、`api/test_projection_pages.py`。真实输入矩阵独立保存在 test_cache_inputs.py，避免扩大已有 service 测试文件。

**接口**：缓存 identity 包含 run 身份、事件可信前缀/内容摘要、投影版本及实际读取的 metadata/artifact 依赖；缓存不承担权威证据准入。活动运行以新前缀失效，关闭运行可复用。

实施契约细化（2026-09-05，独立设计复审PASS）：

- 不新增 RunSummary wire 字段。已知 manifest status 是记录状态而非业务正确性保证；不确定为 unknown，坏 native prefix 为 corrupt，legacy 的 replay_trusted_through 为 null。列表只读当前可信前缀和既有固定安全 metadata，通过现有 `ProjectionService.read_application_metadata` 取得标签；不调用 open_run 或任何完整投影器。保留该 helper 的现有公开签名供两个实施切面共用。
- Native identity 统一使用当前 reader 返回的 typed event tuple 的 canonical digest，含可信长度、analysis identity 与 source kind；不再另读原始日志以拼接不同时间的 snapshot。坏 prefix 先不缓存。Legacy 保留 importer identity 和明确来源类别。不为本包修改 Kernel reader。
- 明确公开 `source_fingerprint` 的生成语义升级为 `projected-source/2.0`：同一可信 typed prefix、实际 metadata 输入和当前 verified/unavailable 工件依赖状态的 canonical 摘要。原字段是 opaque 非空字符串/游标失效令牌，无公开 raw-byte-SHA 承诺；wire 字段和类型不变。cache identity 另外加入 resolved run root 与投影版本，不能用私有 cache key 代替公开 fingerprint。补 event/metadata/artifact 变化旧cursor拒绝、同输入热读cursor可继续的回归；两根目录同analysis_id不得共享缓存。
- 依赖集合独立来自所有 event.refs.produced/consumed/evidence 并集，以及仅 `context.projected`/`context.injected` 的 typed payload.artifact_ref。不得解析任意 payload 字符串为路径。shared collector 或 projector-I/O parity 测试保证没有遗漏；记录负查找，工件缺失→出现、内容损坏→不可用也须失效。metadata包含同一固定安全发现集及缺失状态；不是从缓存自报清单取得 authority。
- Hit 在返回缓存中的 verified 状态或事实前 eager 重核所有实际工件依赖；端点访问仍独立安全验证。版本化 typed cache envelope 绑定预期 identity、analysis_id 和payload摘要；摘要检测缓存损坏，不假称同用户可同时改payload/digest时仍有加密来源保证。坏缓存miss重建。
- 服务强制 cache root 位于 run 外（含解析后的路径），违规配置不得向 runs 写缓存。每服务/每run identity single-flight覆盖收集/读缓存/构建，防止等待期间拼接陈旧身份；不同run不共锁，空闲锁条目清理。缓存写失败不阻断有效读取，返回固定码、无路径/凭据的有界诊断。
- 额外测试范围允许 `tests/trajectory/api/test_projection_pages.py` 以验证游标失效。1k/10k/100k测量区分prefix/hash I/O与投影build/write次数；即使热读仍需全量验证，也不能宣称O(1)或无I/O。只读映射/设计审查留存在 `runs/optimization/OP-07/`。

- [x] 用计数 spy 写重复 open、不同 run 同 ID、工件变化、manifest/descriptor 变化、损坏缓存、活动运行追加、缺少写权限用例。
- [x] 将源身份收集和投影构建分开；缓存命中时恢复 typed projection，缓存 miss 才 materialize。访问证据仍执行安全文件身份/内容验证。
- [x] 运行列表使用可重建摘要，历史/未知格式安全回退；不为了展示列表对所有运行执行全部业务/上下文投影。状态不确定时显示 unknown，不能用旧缓存伪称 trusted。
- [x] 缓存写入失败返回正确读结果和诊断；同一 key 构建合并，防止并发缓存击穿。不得在 runs 写缓存。
- [x] 用测试断言：

```python
first = service.open_run(run_root)
second = service.open_run(run_root)
assert first == second
assert projection_build_spy.call_count == 1
assert materialize_spy.call_count == 1
```

- [x] 运行 `uv run --project packages/grid-agent pytest packages/grid-agent/tests/trajectory/test_service.py packages/grid-agent/tests/trajectory/test_materialize.py packages/grid-agent/tests/trajectory/api/test_catalog.py -q`；对受控 fixture 测量 1k/10k/100k 事件冷/热请求。

**关闭条件**：热请求不重建/重写投影，变化正确失效；冷请求仍真实验证；记录实际复杂度，不承诺未经测量的毫秒数。提交主题：`perf: reuse verified trajectory projections`。

实施与测量记录（2026-09-05）：独立设计、缓存实现、路径dirfd/no-follow/FIFO、真实输入/HTTP游标和基准工具复审均PASS，详见 `runs/optimization/OP-07/final-cache-approval.md` 等。轨迹整套293通过（随后新增FIFO定向14通过），类型零错误，验证目标18通过。曾实际发现并修复损坏prefix仍写cache、路径替换窗口与FIFO阻塞；未删除失败断言。

命令 `uv run --project packages/grid-agent python tools/benchmark_projection_cache.py --sizes 1000 10000 100000` exit0，原始结果 `runs/optimization/OP-07/benchmark-final.json`。Darwin arm64/Python3.14.3，单次合成生命周期/诊断事件，无外部工件I/O；每规模冷读五种投影build及materialize各1次，热读均0次，投影相等。1k冷/热0.1082/0.0763秒，10k为1.2149/0.9541秒，100k为14.1877/11.7483秒。缓存字节分别1,206,822 /12,160,762 /122,601,782。热请求仍需全prefix验证/摘要和typed缓存解码，保持随规模增长的成本，不能宣称O(1)、生产延迟或工件I/O加速。冷读仅指投影cache miss，非冷OS页缓存。基准工具只规范化自身新建临时根以兼容macOS /var别名；生产cache不跟随symlink。

关闭验收：固定 `7638188365482966bf57888904b3d02dbfe3d189` 的 `make doctor && make check-release` exit0（08:55 CST），结束后HEAD未变化，仅状态文档dirty。agent785、sim165、Kernel438、pandapower79、inventory11/13/1、Pi34/43、UI128、门禁自检18、SDK四例、E2E31、offline/scripted/24-of-24、完整应用、六wheel/两npm干净安装和frozen源码安装全部通过。证据 `runs/optimization/OP-07/gate-release-7638188.json` 保存命令/HEAD/退出码与捕获输出；其中一段模拟器上游warnings被工具截断，测试总数和终态保留，不声称无截断控制台转录。未运行付费provider或远端CI矩阵。

### OP-08：服务端限制工件和上下文预览

**Files**：Modify `packages/grid-agent/src/grid_agent/trajectory/api/artifacts.py`、`api/app.py`、`packages/trajectory-workbench/src/evidence/preview.ts`、`src/api/types.ts`；Test `packages/grid-agent/tests/trajectory/api/test_artifacts.py`、`test_app.py`、`packages/trajectory-workbench/src/evidence/preview.test.ts`。

**接口**：工件预览支持单一前缀 Range；服务端上限 131072 bytes，多段/非法范围明确拒绝。大文件全量下载与预览分离。上下文详情使用分页/截断字段，不把截断 JSON 当完整状态。

#### 已批准的范围补充（2026-09-05）

状态：**用户以“同意”批准以下跨层扩展，采用共享读取链方案B；未豁免独立复审，也未批准新依赖或自制通用JSON解析器**。只读证据与独立比较保存在 `runs/optimization/OP-08/frontend-read-only-map.md`、`backend-memory-map.md`、`bounded-preview-design-review.md`。原OP08清单中的网关/HTTP/UI改动不足以兑现完整请求路径的选定工件内存上限：

1. Artifact HTTP在网关前调用完整ProjectionService；即使cache hit，eager依赖验证仍调用Kernel `ImmutableArtifactRegistry.register_existing`，其 `_read_descriptor` 用chunks列表与join分配完整工件。
2. 上下文投影解析完整context-view；context detail还解析完整canonical request。只截HTTP输出不能消除之前的分配，也不能把空对象伪称为完整历史状态。
3. Pandapower `ContentReferenceVerifier`先完整JSON解码再核对领域内容摘要和类型。不能以原始文件SHA替换领域语义准入，不能因UI显示verified而跳过当前run校验。

建议扩展为共享读取链的有界实现（独立方案比较推荐B）：增加Kernel中立流式工件身份校验、grid投影的显式上下文省略表示，以及Domain拥有的有界语义验证接口；网关保留同fd完整摘要验证、有界前缀和已验证spool下载。备选薄预览路由仍需要处理同一Domain缓冲问题，并会增加重复的准入/上下文还原路径，因此暂不推荐。

已批准的额外文件范围：Kernel `trajectory/artifacts.py`及相邻测试；grid `trajectory/service.py`、`cache_identity.py`、`context_projection.py`、`projection_models.py`及相邻测试；pandapower `authority.py`及相邻测试；Workbench实际context消费者及测试。具体小模块拆分与版本失效规则须在实现前写明并独立复审，不预先批准新依赖或自制通用JSON解析器。

控制条件：原有Domain摘要、类型、关联及当前run准入语义保持等价，正常小响应保持兼容；大上下文明确省略字段并仅提供已准入工件入口。新增8/64MiB真实HTTP全链路测试与峰值/读取计数，不能仅用假投影测试网关后半段。非普通文件、symlink替换、源文件变化、摘要失败与拒绝/省略状态均测试；不扩LLM工具、不修改业务authority计算、不隐式降低合法证据预览能力。保证限定为选定工件body保留内存有界，不宣称事件账本/工件数量/总请求内存O(1)或摘要I/O常数时间。如语义等价与预算不能同时满足，必须报告剩余缺口，不能降低断言关闭OP08。

跨层范围授权已解除，但各切片仍须满足下列设计、测试和独立复审门槛；原有OP07关闭结论与固定release证据不受影响。OP-13未提交持久化文件不属于本包，禁止混入提交。

#### 执行切片与设计门槛

按08-A→08-B→08-C→08-D串行集成；只读映射可以并行。Root负责契约和集成，Luna只做有界映射/机械检查，Terra按明确文件所有权实施；风险契约由独立复审者复核。每片记录源码身份、命令、退出码、失败与修复，不以切片通过宣称整包完成。

| 切片 | 实现范围与接口约束 | 先写的失败测试与验收 | 前置门槛 |
| --- | --- | --- | --- |
| 08-A 中立摘要读取 | Kernel `trajectory/artifacts.py`及测试；保持`ArtifactPointer`、`register_existing`、`verify`公开契约，内部以固定块累计长度/原始SHA，不收集chunks后join；保留同fd及路径绑定检查 | 已注册8/64MiB文件不调用整文件读取helper；摘要/长度错误、读取中变化、路径替换拒绝；记录峰值与读取量，现有完整性测试不退化 | 明确读取前后身份检查与错误类型，并独立复审；不得改OP-13文件 |
| 08-B 领域语义与投影 | Domain `authority.py`保持领域摘要/类型/关系准入；grid `service.py`、`context_projection.py`、`projection_models.py`与`cache_identity.py`传播显式省略状态 | 对现有解码/重编码结果做差分测试：键顺序、重复键、转义、Unicode、整数/浮点、嵌套及大标量；旧缓存不可返回旧的完整状态假象，小对象兼容 | 先确定有界语义算法及缓存版本失效规则；新依赖/通用解析器须另行说明并获批准 |
| 08-C HTTP与Workbench | API `artifacts.py`、`app.py`及Workbench预览/API类型/context消费者；前缀与下载分离；context显式`state_omitted`、`omitted_fields`和已准入工件入口 | 非法/多段/后缀Range在工件读取前拒绝；206与Content-Range精确；前端拒绝忽略Range的200；未知媒体类型先拒绝；取消/源变化/下载清理均覆盖 | 明确spool磁盘上限、超限状态和生命周期；API/前端同步变更，禁止路径重开下载 |
| 08-D 全链验收 | 真实冷/热ProjectionService→当前run准入→网关→客户端，禁止假投影替代 | 8/64MiB两档真实HTTP内存及读取计数；context省略与下载快照；focused→完整release，独立复审、回退检查 | A/B/C均验收；剩余线性分配必须如实列出，不能放宽内存断言 |

领域语义核查已确认：`_content_hash`使用`json.dumps(..., ensure_ascii=False, separators=(",", ":"), allow_nan=False)`，不排序键；默认`json.loads`接受重复键并保留最后值。result解析后移除顶层`result_ref`再摘要；evidence/context对完整解析文档摘要；revision则使用原始UTF-8字节摘要。流式实现必须分别保留这些规则，不能统一替换成raw SHA。超大标量和重复键是有界实现的未决难点，不得通过隐藏子进程全量分配或拒绝原本合法文档来伪装等价。

08-A内部实现约束：私有流式helper接收已打开普通文件fd，返回累计字节数和SHA256；读取块上限1MiB。开始记录`fstat`的dev/ino/size/mtime_ns/ctime_ns，读取最多初始size加一个探测字节，长度不符或身份变化抛`ArtifactIntegrityError`，避免增长文件无限读取。仍在原fd打开期间检查run root、parent和leaf命名绑定，并在命名检查后再次核对原fd身份。`register_existing`与`verify`均走此链；既有第二次验证允许保留，明确是两次线性I/O而非常数I/O。打开叶子加nonblocking，随后fstat拒绝非普通文件；fstat失败必须关闭fd。返回Path仍是现有API，不承诺之后调用者重新打开获得原快照；08-C下载必须自行保有已验证快照。

08-A测试执行路径：`packages/capability-agent-kernel/tests/trajectory/test_artifacts.py`保留原回归；新增相邻`test_artifact_streaming.py`覆盖8/64MiB注册和验证、禁止整读helper、逐块计数及tracemalloc峰值、同inode等长变更/追加/截短、EOF后变更、root/parent/leaf替换、FIFO限时拒绝与fstat异常fd关闭。fixture分块构造且在内存测量前结束；只测注册/验证调用的增量分配，峰值上限须来自固定块预算，不随fixture规模放宽。命令：`uv run --project packages/capability-agent-kernel pytest packages/capability-agent-kernel/tests/trajectory/test_artifacts.py packages/capability-agent-kernel/tests/trajectory/test_artifact_streaming.py -q`，预期新行为先FAIL再全PASS；随后`make test-kernel`及生产类型门禁。完整OP08仍按08-D执行release。

- [x] 08-A具体身份检查设计经Sol独立复审APPROVE；33项工件测试基线通过，记录`runs/optimization/OP-08/streaming-registry-baseline.md`。实现约束与复审结论摘录见`streaming-registry-brief.md`，Terra负责该切片源/测试；此设计通过不等于代码验收。
- [x] 08-A RED→最小实现→GREEN、全Kernel/类型门禁及独立代码复审：b7b49f6验收；清理异常修复后独立SPEC/QUALITY双PASS，focused52/root593Kernel及类型通过，8/64MiB峰值约2.1MB。历史TDD记录缺口通过干净恢复源→完整RED→重新实现解决，不追认旧记录。另以37661bf提交测试可移植性修复，保持真实递归失败及公共异常断言，无产品解析变更。证据：OP08 `streaming-registry-closure.md`、`streaming-registry-report.md`、`kernel-gate-investigation.md`。仅关闭A，不代表真实HTTP全链或整包完成。
- [ ] 08-B算法和缓存版本提案；若需额外依赖，先提交理由、兼容性与内存证据再申请授权。2026-09-05核查发现既有依赖不提供分片字符串/键；ijson和json-stream的所评估API仍完整交付单个值，stream-json虽有分片但引入Node运行依赖且不直接保证Python语义。六组真实摘要差分和独立裁决保存在OP08 `domain-semantic-vectors.json`、`domain-streaming-decision.md`。B0隔离验证已批准；B生产集成仍需验证与独立复审后的决定。

**已批准OP08-B0（不改变完整目标）**：用户在解释明确后以“同意”批准Domain私有“分片JSON语义校验器＋临时磁盘索引”的隔离原型和验证。仅使用现有Python标准库，不新增Kernel公共JSON接口、外部依赖或Node要求；不改现有证据，不接入生产。先完成可行性验证和独立复审，再决定生产集成。需证明重复键首位置/末值、转义键、Unicode/代理项、浮点舍入/负零/整浮差异、被覆盖非法值、result_ref排除和无效JSON与现有行为严格一致；以8/64MiB单个巨大字符串/键/数值拼写及多成员结构验证固定内存预算；明确磁盘额度、清理、失败分类和同fd身份绑定。不得靠隐藏整读、额外合法性限制或排除领域证据来通过。分项通过不等于B0可行性通过；生产集成仍需后续决定。
B0原型放在`tools/experiments/op08_semantic/`，不安装进Domain/Kernel wheel，不由任何生产模块导入；通过后也不得自动迁入生产。首个独立切面B0.1：`strings.py`提供64KiB固定缓冲UTF8Cursor与`read_json_string(cursor,sink)->StringInfo(byte_count,digest,has_unpaired_surrogate)`，精确保留后续token；正常分片与全部转义按Python语义重编码。未配对代理项以内部surrogatepass及标记保留，待重复键去重后的可达文档阶段判断；不能过早拒绝被覆盖值。测试`tools/tests/test_op08_semantic_strings.py`覆盖所有分割点、异常/短写及8/64MiB真实文件固定4MiB峰值预算。独立设计复核已批准，Terra按`runs/optimization/OP-08/b0-string-brief.md`执行TDD；根代理负责后续集成复审。重复键磁盘索引、任意数值拼写和全链资源预算仍是B0未闭合项目，不以字符串子项通过替代整体证明。

- [x] B0.1字符串原型：完整RED、差分/大文件GREEN、类型检查、独立代码复审。最终root78PASS、独立78PASS及7776组差分通过；原型显式Pyright/仓库类型/doctor/diff及符号链接检查通过。四组8/64MiB键/值峰值均263243字节，最大读取65536字节，输出长度及增量SHA一致。独立SPEC/QUALITY双PASS；源blob787145337829f3a69c7fdae5845afe94549268a9，测试fd2477450f24771cadcbd8e55f978853c211f17e。证据OP08 `b0-string-root-verification.md`、`b0-string-review.md`。只验收隔离字符串子项，不代表完整B0可行性。
  2026-09-05根复核发现首次21PASS漏测：高代理项后接简单转义被误拒绝，高/高/低序列配对错误；已实测并退回Terra补RED修复、异常覆盖及真实峰值记录，尚未验收。
  后续更正：根补全测试另发现Unicode转义控制字符/引号/反斜杠规范化错误，实测34RED后修复并可读性重构，以上最终验收覆盖这些修正。严格UTF8分片预读可提前发现后续无效字节；后续解析不得假设错误只发生于当前token内。
- [ ] B0后续：数值等价、对象/数组及重复键磁盘索引、配额/身份/清理、整体差分与规模测量、可行性结论。

**B0.2数值隔离原型（现有授权内，自主推进）**：新增`tools/experiments/op08_semantic/numbers.py`和`tools/tests/test_op08_semantic_numbers.py`。`NumberCanonicalizer(sink, integer_spool)`只接受调用方持有的空可寻址磁盘spool，`feed(chunk: bytes)`每块最多65536字节，`finish()->NumberInfo(byte_count,digest,has_nonfinite)`；一次实例仅处理完整单个数字token，不接收JSON分隔符，不是完整文档解析器。source读取与磁盘配额由后续解析器控制，不能以这个子项代替完整资源证明。有限输出精确等于Python json.loads/json.dumps；NaN/±Infinity及溢出不输出伪造数值，以has_nonfinite标记延期至重复键消解后的可达性检查。

词法状态覆盖负号、零/非零整数、小数点及至少一个小数位、指数标记/符号及至少一个指数位；拒绝前导零、空token、空指数及非ASCII数字。遇小数/指数前，整数前缀分块写临时spool，不能因超过当前整数位数阈值就提前拒绝可能合法的浮点拼写；结束确认为整数才检查`sys.get_int_max_str_digits()`（0代表无限），流式复写原数字，整数-0输出0。spool不读成完整bytes、不关闭调用方流、不覆盖非空spool；部分失败输出不得代表成功。
词法另显式接受大小写精确的NaN、Infinity、-Infinity，其他常量拼写拒绝。spool须fileno/fstat证明普通文件、seekable且初始大小/位置为0，拒绝BytesIO、非普通文件、非空文件及不可寻址文件；调用方提供独占、可读写且与sink不同的文件。成功后spool保留整数前缀，位置在前缀末尾；失败保留部分内容和当时位置，调用方负责清理及磁盘额度。原型不操作路径/身份准入，也不自行删除或截断文件。

浮点尾数保留最前1100个有效数字、总有效位数N、小数位数F和被舍弃尾部非零sticky。完整尾数总位数T已知后，指数绝对值仅在T+2000处饱和，并仍消费/校验全部指数拼写。代表数指数q=E-F+N-L，L是保留位数；sticky时代表数字追加1并令q减1。binary64舍入中点含次正规/溢出边界的有限十进制有效位数小于1100，故前缀区间内不含舍入边界，保留端点与尾部非零性即可保持舍入。全零尾数独立保留浮点负零但不能跳过词法验证。先检查运行时binary64前提，不满足归类为原型不可用，不伪造值。独立数学裁决已确认相对T的饱和保留指数抵消；6200组候选差分已通过，不当作实现验收。
舍入证明前提还包括本地CPython十进制转换器正确舍入至最近偶数；不仅凭sys.float_info断言所有解释器成立。当前CPython3.14.3环境经实际中点/次正规/溢出对照校准，跨运行时需重复校准；生产兼容性结论暂不扩展。依据Python json文档的默认int/float转换及CPython dtoa.c的nearest/round-even说明，参考链接见隔离设计复核记录。

- [x] B0.2先建立可导入占位接口和行为测试，捕获真实RED；小数/整数/常数规范化、无效词法、每字节分块、运行时整数阈值、负零/溢出延期、准确中点及远尾sticky、指数抵消、短写/故障/流所有权均须断言。最终完整初始60RED；后续超读1RED、复审协议异常19RED均修复。
- [x] B0.2实现后运行`uv run --project packages/grid-agent pytest tools/tests/test_op08_semantic_numbers.py -q -s`及原字符串回归；8/64MiB真实数值文件覆盖长整数前缀后转float、大量小数零后指数抵消、超长指数，固定4MiB tracemalloc增量，spool为磁盘文件，输出长度/摘要/读取上界有实测记录。默认阈值拒绝巨大整数；阈值0场景必须流式输出而非构造Python大整数。八组最大峰值132879字节，块65536；最终数值/字符串联合171PASS。
- [x] B0.2显式Pyright原型、仓库类型门禁、doctor/diff/符号链接检查和独立SPEC/QUALITY复审后单独提交；不改生产模块/OP13，不关闭完整B0。独立复审171PASS/类型0、额外13173组有效分割差分及18类无效拼写通过；源ccc397c17bf8608ed0413755fbae80dfd67dad15，测试e11c7b47871ebe919935610287b7b57f61fe6fb9。证据OP08 `b0-number-design-review.md`、`b0-number-root-verification.md`、`b0-number-measurements.txt`、`b0-number-review.md`。仅验收完整数字token原型，不是完整JSON文档或生产语义校验器。

**B0.3磁盘对象成员索引（现有隔离授权内）**：新增`tools/experiments/op08_semantic/object_index.py`及`tools/tests/test_op08_semantic_object_index.py`。`DiskObjectIndex(connection: sqlite3.Connection, keys: BinaryIO)`使用调用方独占的新建磁盘SQLite库和追加式普通键文件；不关闭、不删除、不截断调用方资源。拒绝内存库、已有schema、活动外部事务、非默认row/text factory及非普通/不可寻址键文件。SQLite采用并读取确认cache_size=-1024、mmap_size=0、temp_store=FILE；这些是配置证据，不是native RSS硬上界。

接口：`new_object()->int`分配对象ID；`put(object_id,key_offset,key_length,value_id)->Member(position,key_offset,key_length,value_id)`，ID为正SQLite整数、position从0开始。键范围由B0.1产生的规范带引号字节给出；索引不解析JSON、不接受全量键字符串。flush后用同一fd的pread最多65536字节重算SHA256，查询object_id+digest+length候选，再对每个候选逐块精确比对。摘要碰撞不能当作相等；新键分配末位，重复键仅更新value_id，保留首次键范围和位置。不同对象互不影响。value_id是不透明引用，非有限/代理项延期验证与值可达性由后续文档组装负责；保留首次规范键范围供最终可达输出验证。

`members(object_id)->Iterator[Member]`顺序懒加载，不fetchall；从开始迭代到关闭/耗尽期间禁止该索引写入，避免游标与修改混用。每次new_object/put用独立savepoint原子操作；异常回滚并保留原始cause，回滚失败标记索引不可再用且不得掩盖首错。输入位置/长度与文件实际范围检查，不以其他对象已有ID猜测成功。调用方遵守键文件仅追加、无并发修改；这不是权威源身份校验或路径安全证明。
独立复核补充：拒绝附加数据库，schema初始化也须原子；objects(id INTEGER PRIMARY KEY,next_position INTEGER NOT NULL)，members以(object_id,position)为WITHOUT ROWID主键，碰撞索引为(object_id,digest,key_length,position)。pread合法短读循环补足，EOF/超读拒绝；提前关闭迭代器释放游标。savepoint清理覆盖BaseException并原样重抛中断，普通存储/协议/状态失败统一ObjectIndexError(OSError)保留cause，非法标量参数ValueError。任何回滚失败后索引失效。
具体机制：PRAGMA database_list只允许main（不接受attached）；初始化表和索引全部在savepoint中，失败不遗留部分schema。pread每次请求<=65536，短读循环，EOF/非bytes/超出请求均ObjectIndexError。members的游标在finally关闭（包括generator.close）。BaseException路径执行ROLLBACK TO及RELEASE，KeyboardInterrupt/SystemExit原样重抛；清理失败附加不含源数据的诊断且poison，不能覆盖首错。

- [x] B0.3独立设计复核后，先建立可导入占位和真实行为RED：首次位置/最后值、不同对象、相同长度强制摘要碰撞、规范转义等价、缺失对象/非法范围、数据库故障回滚、键读取错误、调用方资源保留、懒迭代与写入互斥。初始15RED后实现15PASS，补充覆盖最终27PASS。
- [x] B0.3实现并测量真实8/64MiB键（键文件分块生成，注册及重复比对均测量），固定4MiB tracemalloc上限及65536 pread上界；成员数量规模验证懒读取，明确SQLite原生缓存和磁盘增长未由tracemalloc覆盖。两规模峰值均264501字节；256/4096成员遍历峰值2472/1096字节。
- [x] 命令`uv run --project packages/grid-agent pytest tools/tests/test_op08_semantic_object_index.py -q -s`，联合字符串/数值回归、显式原型Pyright、仓库类型/doctor/diff/符号链接检查；独立SPEC/QUALITY通过再提交。root联合198PASS，独立索引27PASS/显式类型0、额外顺序/碰撞/提前关闭探针通过；源21248c9b19c78d6fbd70fbcc7288d1f207053a13，测试1fcc96dda39a5ce0f1bbff0fa9d32a23deacb4a8。证据OP08 `b0-index-design-review.md`、`b0-index-root-verification.md`、`b0-index-review.md`。B0.4仍须完成文档语法/组装、重复覆盖可达性、资源配额/身份/清理和完整差分，不以该索引子项替代。

**B0.4完整文档组装原型**：新增`tools/experiments/op08_semantic/document.py`（资源生命周期、语法扫描、输出控制）及`document_store.py`（SQLite节点/数组边/磁盘遍历状态），测试`tools/tests/test_op08_semantic_document.py`。必要时给strings.UTF8Cursor增加有界数字token片段/空白消费方法，给DiskObjectIndex增加`member_after(object_id,position)->Member|None`，均先补RED并保留已验收回归。不读取整个数字/键/文档，不用Python递归或随深度增长的列表/生成器栈。所有节点及解析/输出栈帧关系在SQLite，Python只持有当前节点/帧和有界片段。

接口：`canonicalize_document(source: BinaryIO,sink: BinaryIO,*,scratch_parent: Path,omit_top_level_key: str|None=None)->DocumentInfo(byte_count,digest)`。仅支持与当前Domain权威一致的对象根节点；先完成整个JSON语法及解析时错误检查，再按最终成员索引遍历可达值，可选排除指定顶层键（结果摘要使用result_ref，嵌套同名键不排除）。重复键首位置/末值保持，NaN/Infinity/未配对代理值仅在最终仍可达时拒绝；无法通过覆盖逃避非法UTF8/非法转义/整数转换位数限制。保留下来的键字节也做严格UTF8可编码性检查，不能因其值被覆盖而跳过键合法性。

共享新建磁盘库由组装器独占：先初始化要求fresh schema的DiskObjectIndex，再建立文档节点/数组边/遍历帧表。采用autocommit，不在索引调用外留下活动事务；每次解析失败整个scratch实例作废，不提供部分恢复状态。每个数字使用组装器拥有的临时整数spool，完成后关闭；调用方source/sink始终不关闭。资源均置于scratch_parent下唯一TemporaryDirectory，只清理本次创建的文件；失败/中断也清理，清理错误不覆盖首错。解析完毕后输出可能因保留非法值而失败，部分sink输出不可作成功/摘要证据。

错误分类：DocumentDecodeError表示词法/语法/解析时数字位数错误，DocumentShapeError表示非对象根，DocumentCanonicalError表示最终保留非有限数或不可UTF8编码的键/值；DocumentResourceError表示I/O、SQLite、临时存储/运行时资源故障，不将资源耗尽报告为JSON不合法。原型不宣称源身份、磁盘额度、native RSS或生产可用性已完成。

深度约束证据：当前CPython3.14.3、sys递归限制1000，实测100/500/999/1000/2000/10000层数组及被覆盖版本均可解析/规范化；不能自加1000层数据上限。采用磁盘迭代遍历，不设输入深度合法性阈值。参考json.loads/dumps若发生RecursionError/MemoryError，测试记录reference_unavailable而非语义PASS；新旧资源可用性差异必须保留为后续采纳风险，不能借此宣称完整等价。独立设计有条件批准见OP08 `b0-document-design-review.md`。

- [x] B0.4先写真实端到端行为RED：普通嵌套、数组、重复/转义键、被覆盖非法值、保留非法键/值、解析时错误不可覆盖、顶层字段排除、非对象根、尾随数据、清理和流所有权。初始32RED→32PASS；清理掩盖主错1RED及调用方异常分类2RED均修复。
- [x] 实现磁盘语法/遍历及必要的有界cursor/keyset接口。完整文档专项44PASS27.59s（含8/64MiB四形状与12000层，无skip），峰值<=600251字节；独立1000结构差分通过。最终四模块日常回归225PASS2.13s，23项既有压力用例按§6不重复运行；完整字节/长度/SHA、重复成员和嵌套语义均覆盖。
- [x] 显式原型Pyright、doctor/仓库类型/diff/符号链接检查通过；独立SPEC/QUALITY复审PASS，另38项聚焦PASS。证据OP08 `b0-document-root-verification.md`、`b0-document-review.md`；最终document源3615bb7898eae5ffc4205be86a9ddf90765c7f39、测试279c146ca40cb88d3f77f55d084cb52fb7001260。完整B0还须磁盘额度、同fd身份、清理失败、native内存及完整Domain语义验证；本子项不自动触发生产迁入。
- [ ] 08-C明确HTTP失败状态、spool预算/清理及省略字段契约，落实到类型和测试。

**B0.5源绑定切面（隔离验证）**：新增`verified_source.py`，提供`VerifiedSource(fd,expected_digest,expected_size)`只读适配器；调用方已安全打开并准入普通文件，适配器不接收路径、不重开、不关闭调用方fd。固定最大65536字节pread，从偏移0开始，独立于调用方游标；逐块累计原始SHA，EOF前核对预期长度/摘要及同fd dev/ino/size/mtime_ns/ctime_ns。文件被改动或I/O失败均资源错误，不当作JSON不合法。与document原型组合时_parse必须读至EOF后才_emit，故失败不得产生成功摘要或输出。只证明已打开fd到语义输入的绑定，不替代路径准入、不可变下载快照或恶意写入者隔离。日常测试仅正常绑定、错误摘要/长度、读取中修改、调用方fd所有权/游标及读取上界；小型真实文件足够。磁盘额度与完整Domain验证仍为后续B0工作。

- [x] B0.5上述边界4RED→4PASS；联合日常229PASS2.33s、显式类型0/doctor/diff/符号链接通过，不重复23项既有压力用例；独立SPEC/QUALITY通过（另4PASS及类型0）。证据OP08 `b0-source-root-verification.md`、`b0-source-review.md`；源5ea46282ed87f17068dc53cf8221abe1dde0eadf，测试2ffabf51f224cf218b7e12edfa01530d37123530。仅验收原始fd绑定，不等于完整B0通过。
- [ ] 08-D记录真实全链证据，并完成整包独立复审后才能关闭OP-08、启动OP-09。

回退：各片单独提交且不混入OP-13；按D/C/B/A逆依赖回退任务提交，失效新版本派生缓存，不迁移或删除历史runs。已接受答案、权威证据与默认legacy存储行为保持不变。

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

实施依据：`runs/optimization/OP-10/runtime-seams-map.md`与`dependency-boundary-map.md`。OP05已将_domain_output_schema标注修为str，不重复修复。第一独立切面为静态导入边界：仅允许pandapower Domain Pack使用 `from grid_simulator.capabilities import contract_root`（可别名）；拒绝root/module整包导入、其他符号、star、内部子模块及混入未许可符号的from-import。保留实际安装依赖和既有其他方向检查；不声明静态AST门等价于恶意动态代码沙箱。不新建重复contracts包、不改simulator公开导出。

运行接口设计（独立复审PASS，实施前澄清已解决）：保留可调用factory接口，不改成.create/.prepare对象API。provider factory保留request/profile/prepared_application/bindings/catalog五kwargs；preparer保留profile/request/workspace/registry/credentials五kwargs。必要transport/controller/output契约在provider.start前做signature bind预检，不调用provider；不把正确调用后内部TypeError伪装成签名错误。canonical prompt_and_wait转发on_semantic_event/correlation_id/on_heartbeat，旧prompt名称只允许具名适配且完整转发，不静默丢参。legacy validate(payload)仅通过保留已准入引用上下文的具名适配器，不用通用过滤；上下文感知validator显式接收context。报告prepare可缺省为no-op，有render仍使用配置render，只有render缺失时使用GenericReportShell；报告普通异常继续OP03非阻断。新Protocol只覆盖实际消费接口，保留已有具体PreparedApplication/TurnController公开导出，不用大量Any/cast掩盖类型问题。详细调用表与复审见OP10/runtime-contract-design.md、runtime-design-review.md。

类型收紧实施澄清：实际调用方 `packages/grid-agent/src/grid_agent/application/composition.py` 纳入同一接口迁移及相邻装配测试，保留provider字符串选择与对象注入行为；只改类型衔接，不新增provider选择策略。新Protocol应使用已有明确的request/profile/workspace类型和实际消费的结构接口，不能靠 `Protocol | Callable[..., object]` 或 `Concrete | object` 宣称已收紧。需要兼容的动态边界通过校验和具名适配进入类型化内部，不把合法的结构化测试替身强制变成某个具体类。必须以全仓锁定pyright及实际装配测试验证，不能只检查新增文件。09:20左右的局部注解试验暴露七处上下游不一致，已撤回；不作为完成实现。

最终类型裁决（Sol只读复核，2026-09-05）：controller操作使用已有ActiveTurnHandle/FinalizedTurn值对象而非具体controller类；内部协议还显式保留active_turn_path、context_view_path、trajectory_requests_path、trajectory_capture_state_path、trajectory_allowed_refs_path、trajectory_acks_path六个Path或None通道。适配器不得丢失这些属性、包装返回值或用通用__getattr__逃避类型检查。报告内部使用实际ReportPublisher：配置GenericReportShell保留原实例且只传九字段，其他配置render传完整十一字段，缺prepare为no-op；普通发现/签名/执行异常仍置于派生隔离，不在构造或primary preflight变fatal，只有render缺失/不可调用才默认fallback。输出在provider启动前选定类型化state/build/validator组合，保留既有schema选择与当前引用作用域，legacy验证仍先scope再validate。删除未消费的Protocol；public legacy prompt用明确输入协议后转canonical。验收必须覆盖真实descriptor六通道、对象身份、公开legacy装配及报告发现异常，不仅检查私有helper或局部pyright。裁决详情：`runs/optimization/OP-10/final-typing-contract-decision.md`。

最终复审修复补充：类型声明不是返回值验证。controller source在构造装配时校验签名/通道并存入session；start/submit/fail调用后必须验证实际值DTO且保留实例身份，不能以缺status默认success，也不能把调用后内部异常误报为签名错误。合法具体controller实现不受强制；测试替身仍可结构实现controller，但返回既有DTO。引用验证回归必须通过新的selected-output适配生产路径，不以已无调用方的旧helper通过冒充覆盖。支持性调用方范围增加`validation/run.py`及`packages/grid-agent/tests/validation/test_scripted_transport.py`：脚本transport接收并调用on_heartbeat，原8项E2E因缺此参数失败；不放宽Kernel预检，不改变权威步骤或证据。所有失败和修复需要新源码重跑，不沿用初稿全绿。

- [x] 列出 runner 各注入点的实际生产调用与测试替身，按已有签名定义 ProviderSession、TurnController、PreparedApplication、ReportPublisher Protocol；不为未实现的多域功能增加抽象。
- [x] 将 `_call_factory` 的反射适配限制于具名 legacy adapter；生产接口参数缺失在 provider 启动前报配置错误。新增丢失 projector/correlation/authority 参数的负例。
- [x] 修复 `_domain_output_schema` 返回标注与真实 str 返回不一致等类型缺口；删除无效 object 联合，但不通过大量 cast 掩盖错误。
- [x] 明确 Domain Pack 可导入 authority 的公开协议资源/规范化 API，禁止 raw simulator 内部。先记录 allowlist 与包版本测试，再评估是否需要独立 contracts 包；本包不复制两份 capability schema。局部证据：54项checker测试、边界门、boundary-review.md及docs-version-review.md；固定整包门禁已通过，见下方记录。
- [x] 文档分别绘制代码依赖、运行调用和证据返回；维持四层职责。README 涉及同一事实时双语同步。双语及architecture复审PASS，本地38目标链接和CLAUDE相对symlink检查通过。
- [x] 验证缺少必需调用参数稳定拒绝：

```python
with pytest.raises(ApplicationConfigurationError):
    build_application_with_incompatible_transport()
assert provider_start_spy.call_count == 0
```

该测试 helper 必须在测试文件中构造缺少生产 Protocol 必需参数的 transport，并走真实装配入口，不能直接 mock 配置错误。
- [x] 执行 `make check-types`、`make check-package-boundaries`、Kernel 全测试和 `make test-packages`。

**关闭条件**：生产调用无静默丢参；装配失败可诊断；公开资源 API 与 raw 实现边界可测试。提交主题：`refactor: enforce typed application runtime seams`。

验收记录（2026-09-05 10:35 CST）：固定源码 `d5eec21f11a40056d3fdf104035ee00447fdfa9d` 的 `make doctor && make check-release` exit0，结束后HEAD未变。全生产pyright零错误；agent788、sim165、Kernel464、pandapower79、inventory11/13/1、Pi43/34、workbench128、门禁自检18、真实SDK捕获四例、E2E31、offline/scripted/24-of-24、完整应用、六wheel/两npm干净安装及frozen源码安装全部通过。完整原始证据 `runs/optimization/OP-10/gate-release-d5eec21.json`，最终独立复审 `runtime-final-rereview.md` PASS；早先HIGH无效controller返回被视为成功及MEDIUM测试旧helper均已关闭，实际malformed-submit为failed/0。checker另54项回归与独立边界/文档复审通过。`_domain_output_schema`的str修复已在OP05完成，本包保留既有fallback，不重复改profile或schema。曾出现脚本transport缺heartbeat的8项E2E失败，已真实RED→GREEN并全套重跑；root一度并行test/validate撞固定案例锁，失败保留 `parallel-gates-conflict.json`，随后串行doctor/test/validate及本次完整release通过，不删除隔离或放宽断言。运行环境Darwin arm64/Python3.14.3/Node23.11.0，安装烟测另Python3.12.12；上游警告保留，未声称远端CI矩阵已运行，未调用付费provider，未改保护路径。

### OP-11：完成 inventory 的应用级 conformance

**Files**：Modify `packages/inventory-domain-pack/src/inventory_domain/profile.py`、`execution.py`（仅环境过滤）；Create 同目录 `provisioning.py`、`state.py`、`answer_policy.py`、`answer_admission.py`、`guide.py`（含 policy provider）、`presentation.py`、`output.py`、`acceptance.py`；Create `packages/inventory-domain-pack/tests/test_application_conformance.py` 及组件测试；Modify `packages/grid-agent/tests/contract/installed_smoke.py`、`configs/runtime/application-instantiation-protected-paths.json`；复用现有 `tools/test_package_artifacts.sh` 无需修改。

**接口**：实现现有 DomainRuntimeProfile 八个完整应用组件及 OP-01 准入，复用公共 Kernel Protocol；测试中装配 ApplicationProfile，不注册 production grid CLI 的 inventory 模式。

- [x] 从 `missing_application_components()` 为空开始写红灯，再加入两组独立问题：库存/资产查询与上下文复用、无效对象/外来引用/错误 authority 的受限结果。
- [x] 提供真实 inventoryctl provisioner、状态验证、输出验证、报告片段、离线知识策略、接受案例声明；所有 current-run 数据由 reference authority 产生。
- [x] 使用 scripted transport 但真实 executor/authority 跑 AgentApplication；验证答案、core、domains.inventory、报告失败降级及 replay。

```python
assert profile.missing_application_components() == ()
assert outcome.status == "completed"
assert set(outcome.result.domains) == {"inventory"}
assert replayed_context == stored_context
```

- [x] 扩展干净 wheel 安装测试，从仓库外目录完整执行该应用；不得依赖 `validation/` 或源码树绝对路径来解析包资源。
- [x] inventory 路径受 C.1 保护：先验证旧基线，记录允许变化的目录/理由/旧摘要，完成独立复审和不依赖 protected gate 的领域测试。先提交领域改动，再用 `git rev-parse HEAD:packages/inventory-domain-pack` 取得摘要更新当前配置并独立提交，然后执行完整门禁；中间两提交在集成分支不得视为 release。历史 Climb 配置与旧 closure 不变。
- [x] 执行 `make test-inventory`、`make check-package-boundaries`、`make test-packages` 和更新后的 `make check-release`。

**关闭条件**：独立 Domain Pack 通过完整应用闭环，Kernel/generic Pi 不加入 inventory 特例。提交主题：`test: prove complete inventory application conformance`。

设计细化复审（2026-09-05）：`runs/optimization/OP-11/design-review.md` PASS；下面契约属于本包已批准方向的实施细化。修订消除了报告上下文形状、报告附加引用覆盖、历史catalog混入输出及prepare失败语义四处缺口；不改Kernel或reference service。支持性安装验收调用方 `packages/grid-agent/tests/contract/installed_smoke.py` 纳入本包，复用现有仓库外复制执行路径。

#### OP-11 implementation contract — reviewed refinement

This refines the already approved canonical OP11, not an additional product
mode. OP10 dependency is closed at d5eec21; closure documentation is 2f6c452.
At design review no OP11 production edits existed. Old protected trees were verified at 10:40 CST:
inventory-domain-pack dc7c1e666af660f95fa8fcb6cfb7bd21a4a74108,
inventory-reference-service 3267711cc30e5c2dc3ff1e0e630b76f21a0d030a.

#### Scope and approach

Complete inventory's existing public Kernel SPI using its current executor,
authority, projectors and packaged resources. Do not modify Kernel, generic Pi,
the reference service, its calculations, or grid CLI selection. No new package
dependency or capability schema. Keep inventory a conformance/reference Domain
Pack. Reject the initial preflight note's fake-authority acceptance approach.

Alternative of adapting pandapower components by importing that pack is rejected:
it couples domain policy/state. A second runner or canned precomputed responses
would not prove SPI conformance. Independent inventory components with real
authority execution are the selected existing-plan approach.

#### Component contracts

##### Runtime preparation and profile assembly

New provisioning.py owns InventoryRuntimeProvisioner.prepare(*, binding,
workspace: Path, credentials: CredentialLease) -> PreparedInventoryEndpoint.
The endpoint has executor, metadata, idempotent close. Validate matching
credential scope and empty credentials before process work. Resolve a supplied
trusted executable first; otherwise check the real inventoryctl beside the
current interpreter in its scripts directory, then configured PATH as a fallback.
Require an executable regular file; an explicit invalid executable fails without
falling back to a different authority. The clean-wheel smoke must exercise the
default no-argument profile discovery, not inject a source executable.
Do not guess another worktree or copy ignored runtime state.

Expose a binding-local executable basename, fixed request/--workspace arguments,
a binding-local search path, timeout/output-limit metadata and sanitized
environment through the existing descriptor contract. Install the validated
console script into the newly owned binding bin without following destination
symlinks or replacing an existing unexpected path. Reuse InventoryctlExecutor;
composition's existing environment.describe call verifies the registered
protocol/capability surface. Supply timeout and sanitized environment directly
to InventoryctlExecutor. Output-limit metadata is descriptive: it does not
bound subprocess.run's captured output in the existing executor. Do not widen
OP11 into an executor or Kernel refactor or claim a memory bound from metadata.
No second execution route or shell invocation.

Implementation review refinement (2026-09-05): the existing inventory environment
denylist retains nonstandard provider credentials (for example cloud credential
paths and PAT variables). Tighten only inventory execution.sanitize_environment
to a small runtime allowlist shared by provisioning and the legacy executor
factory; unknown business/provider variables and import-path injection stay out.
This is credential-boundary completion, not an executor I/O, subprocess-buffer,
Kernel or authority refactor. Verify both actual child environments and endpoint
metadata, retaining installed environment.describe conformance.

GuideProvider.load/open uses only the existing resource allowlist (overview,
capability-map, evidence-and-recovery) and verifies regular no-follow bound reads
and captured digests before returning text/index data. PolicyProvider.load uses
the packaged system policy. No imports from pandapower private helpers.

build_inventory_profile() keeps its no-argument entry point and existing
manifest/authority/executor/projector semantics, adding all eleven required
application fields. Use the same concrete resource set for guides and policy.
The test can use dataclasses.replace for an explicit provisioner/executable;
do not add a production inventory CLI branch.

##### Domain state and context

New state.py owns a versioned inventory-readonly-state/1.0 JSON mapping:
state_schema, state_revision, active_context_ref, catalogs keyed by context_ref,
asset_results keyed by result_ref, stock_summaries keyed by result_ref.
Use existing ActiveCatalogState, AssetResultState, StockSummaryState and
InventoryStateDelta. Accept initial empty mapping as empty state, reject wrong
schema, negative/bool revision, unknown structural fields, key/reference
mismatch, wrong reference kinds, missing catalog context and revision mismatch.
Keep catalog history so a later catalog selection does not invalidate legitimate
previous results. Preserve original source record on identical replay/reuse;
reject conflicting content under the same content reference. A different
producer_turn_id alone for identical authority data must not fabricate a
collision; retain the first provenance record.

merge is pure and validates both input and output; it never queries authority.
Only existing verified projectors produce deltas. build_context returns a
detached DomainContextView containing the supplied binding_id, state and top-level
admitted_refs derived from these admitted records: inventory context, revision,
result and evidence references. Do not put these refs solely in admitted_artifact_refs:
the existing Kernel report wrapper replaces that field with the report artifact
reference. The inventory validator must combine public admitted_refs and
admitted_artifact_refs and never inspect the wrapper's private base object.
The state adapter cannot invent an artifact/report reference. DomainContextView
is not a cryptographic admission
API for arbitrary callers: production trust comes from Kernel authority-verified
projection and committed current-run context.

##### Answer admission and evidence policy

answer_policy.py implements the existing AnswerEvidencePolicy methods against
inventory result/evidence reference kinds and supported semantic claim categories
(asset, stock, evidence, offline_information). The controller already enforces
current-turn ownership and authority verification; do not bypass or replace it.
No hardcoded grid reference formats or arbitrary binding-name restriction.

answer_admission.py factory receives the current-run authority and returns the
existing AnswerAdmissionDecision(mode, assurance, answer_output, diagnostic_codes).
For authority-backed input retain reader text and lineage_verified only; never
claim free-text numbers are semantically proven. Without references, only a
deterministic packaged informational request is offline_information /
deterministic_information. Unknown/mixed business requests return limited.

Reusable information categories come from the actual guides: read-only inventory
capabilities, current-run evidence, and recovery after missing context. Exact
guide:<resource-id> and bounded English/Chinese information-request syntax may
select those concepts, but must match the entire informational request. No
question/asset/catalog/expected-answer shortcut, substring business classifier,
or dependence on model-generated text. Offline response returns packaged text
and does not invoke the authority or manufacture evidence.

##### Output and presentation

New output.py declares inventory-readonly-output/1.0. Its payload contains only
catalog_id, context_ref, revision_ref (all nullable together when no catalog),
asset_result_refs, stock_summary_refs (lists), and report_artifact_ref (nullable).
Build from the supplied inventory context, never a directory scan or model text.
The two result lists contain only records whose context_ref AND revision_ref
match the active catalog triple. Retain other valid catalogs/results in state,
but do not mix historical catalog refs into this single-active-catalog payload.
When no active catalog exists, both result lists must be empty.
Cross-check all inventory refs against the context's retained catalogs/results
and admitted evidence lineage. Preserve non-null report refs only when admitted
by the existing Kernel report context wrapper; null report remains valid.

Implement context-aware validate_with_context(payload, *, context) plus
validate(payload) for the public SPI. Standalone validation must fail closed on
non-null references without a supplied admission scope; use a constructor
allowed_references option or a clearly defined structural-only empty-payload
case, not permissive reference validation. Validate exact payload keys,
list/string shapes, reference types, matching catalog/context/revision, and
binding identity during build. No framework core/domains fields nested in
the domain payload; no raw artifact paths exposed by payload.

presentation.py renders context/report fragments exclusively from the detached
verified inventory records. Actual runner report dispatch passes the public
application snapshot, whereas output dispatch passes DomainContextView. Accept
both forms: for the snapshot, select exactly one domains envelope whose
schema_id is inventory-readonly-state/1.0, use its mapping key as binding_id,
validate/detach its state through InventoryStateAdapter, and reject absent,
foreign or ambiguous matches. DomainStateEnvelope has no domain_id field.
Do not inspect other domains' state or modify Kernel reporting. An initialized
matching envelope with empty state is valid. Formatting may display counts and
totals already returned by authority, not recompute inventory balances.
Renderer failures are derived and must leave accepted answers and a valid
null-report output. Test the real default GenericReportShell path for actual
inventory summary content, not just existence of a report reference.

##### Acceptance and packaging

acceptance.py provides DomainAcceptanceProfile offline/scripted/provider
declarations as inspectable case metadata; declarations alone are not evidence.
No provider invocation in acceptance declarations or profile construction.

Test scripted transports carry the exact OP10 signature and drive real
prepared capability tools/executor/authority through semantic events. At least:
1. Two turns: catalog.open + asset.list, then stock.summary using the previous
   actual context without reopening. Assert committed answers, core,
   domains.inventory, real result/evidence refs, report and replay equality.
2. Missing asset request produces typed tool failure and a limited answer with
   no invented evidence. Foreign-run refs and wrong authority cannot acquire
   lineage_verified; where existing preflight rejects, provider start remains
   zero. A mismatch detected only during tool projection occurs after start:
   do not add a new preflight guarantee. Persisted limited admission is the
   negative acceptance evidence; the existing runner subsequently returns a
   failed ApplicationOutcome, not happy-path completed domain output.
3. Zero-reference business prose remains limited; supported information returns
   deterministic guide text with no result/evidence; mixed request is limited.
4. Report prepare-only failure leaves the accepted answer and a diagnostic;
   if subsequent render succeeds, report publication may still succeed.
   Final render/publication failure leaves the accepted answer, with report_path,
   report_ref and domain report_artifact_ref all null. Exercise these separately;
   do not change existing Kernel failure-isolation semantics.
5. A successful report must preserve inventory admitted_refs while adding its
   admitted_artifact_refs; validate both domain and report references through the
   actual report-aware output path. A state unit test with two valid catalog
   histories proves only active context/revision results enter output (synthetic
   unit records are not substituted for real authority conformance).
6. Tampered current-run artifact fails authority verification; state/output
   reject unadmitted or foreign refs rather than recomputing expected answers.

Extend the existing standalone installed smoke at
packages/grid-agent/tests/contract/installed_smoke.py, already copied and run
outside the repo by tools/test_package_artifacts.sh. Keep its existing tests.
Add complete inventory AgentApplication execution using real wheel-installed
inventoryctl and packaged guides. Assert the expected installed console script
exists at Path(sys.executable).parent / inventoryctl(.exe) in the fresh venv,
then use the default no-argument profile/provisioner so lookup cannot silently
test a host-PATH executable. No import of validation/ or test source paths.
This supporting test caller is included in OP11 scope; no new public CLI/helper
is needed. The packaged acceptance declaration does not become a fake executor.

#### Implementation slices and verification

A: state/output/presentation + focused real-data and negative tests.
B: provisioning/guide/policy/answer_policy/answer_admission/acceptance/profile +
complete application conformance tests. This avoids admission depending on a
guide provider that does not exist yet. A before B integration; root owns
installed smoke and ledger.
All task-owned test files live under packages/inventory-domain-pack/tests/;
additional standalone smoke remains root-owned. No concurrent suite runs sharing
fixed run IDs. Use temporary isolated run roots for every new test.

RED first for missing_application_components and each missing behavioral seam;
verify red is the intended missing behavior, then implement, run smallest
focused test, full inventory tests and full production pyright. Independent
review must cover current-run trust, state/reference identity and installed
execution, not just Protocol presence.

Before changing a protected tree: old baseline check above. After focused tests
and independent review, commit domain source/tests and installed test caller.
Then derive HEAD:packages/inventory-domain-pack and update only the current
protected config in a separate commit. Do not modify historical Climb digests.
Run package boundaries, installed packages, then fixed-source doctor/check-release.
Neither intermediate code nor digest-only commit closes OP11 without full gates.

#### OP-11 acceptance record (2026-09-05)

- Source: `416a04d052c51fe4639a29347a975107bb624cac` (22 source/test files).
  Independent digest-only commit `218b672eea615d92d6c4af3d52b6c4af8ed20f54`;
  inventory tree `dc7c1e666af660f95fa8fcb6cfb7bd21a4a74108` →
  `c224b47dd15ad5988935e907966ed48f11774527`. Reference service unchanged.
- Fixed-source `make doctor && make check-release` exit0 at11:42 CST; HEAD
  remained218b672, only task documentation changed. Production pyright0;
  agent788/simulator165/Kernel464/pandapower79/inventory-service11/
  inventory-domain118+transport1/Pi43+34/Workbench128/gate-selftests18;
  built SDK four cases, E2E31, offline/scripted coverage24/24,
  full application validation, six-wheel/two-npm and frozen-source install PASS.
- Environment: Darwin arm64, main Python3.14.3/Node23.11.0; actual clean wheel
  Python3.12.12. Dependency warnings retained; no remote CI or paid-provider claim.
  Raw untruncated capture: `runs/optimization/OP-11/gate-release-218b672.json`.
- Reviews: `root-slice-a-review.md`, `root-b-components-review.md`,
  `application-tests-review.md` under the same evidence directory all PASS.
  Cross-kind result collision2RED and nonstandard credential leakage1RED fixed.
  Preliminary worker reports remain incomplete history, superseded by root reports.
- Failures retained: initial incomplete component assertions; test namespace
  mismatches; catalog-only limited admission; public typed transport error handling.
  Corrected tests preserve existing Kernel semantics. Source smoke environments
  lacked inventory or interpreter-adjacent script; assertions stayed strict and
  actual six-wheel external-directory execution passed.
- Contract: eleven profile components, real two-turn authority execution,
  current-run admitted outputs, report isolation and replay. Read-only inventory
  remains conformance infrastructure, not a new production CLI/domain selection.
  Domain lineage does not prove free-text numeric semantics. No Kernel/Pi/service
  change, user-state migration, push or paid provider. Decision DONE; next OP-12.

### OP-12：长运行基准与存储改造决策

**Files**：Create `tools/benchmark_optimization.py`、`tools/tests/test_benchmark_optimization.py`；Modify `Makefile`；不修改 context store 的持久化格式。

**接口**：`python tools/benchmark_optimization.py --events 1000 10000 100000 --output runs/optimization/benchmarks/report.json`，报告包含环境、源码、规模、重复次数、p50/p95、读取/写入字节和峰值内存。命令通过 grid-agent 的 uv 环境运行。

**实施计量契约（2026-09-05，独立设计复审通过）**：

- 每个 N/重复使用独立子进程及临时目录；默认三次、append batch100。
  Context 初始化事件不计入 N；追加 N 个合法 `domain.state.projected`，
  固定256字节状态且 previous_revision 连续，真实 append/replay 等价。
  此分布隔离账本重写成本，不代表业务负载或不断增长的诊断列表。
- Trajectory 另用 N 个合法 hash-chain 生命周期/诊断事件和一个固定65536字节
  request text 的真实注册工件；每样本一个 run（不是 N 个 run）。真实列表、
  冷/热投影及 canonical-request preview helper；热投影等价且 projector/
  materializer 调用为零。冷缓存不表示清空 OS cache；预览不代表浏览器、
  HTTP 端到端或工件大小增长测试，也不改变 OP08 的待批准范围。
- 包装真实 Python stream/descriptor I/O，精确测试 open/fdopen 委托不重复计数。
  账本另在真实 `_stage_bytes` 统计成功 final+backup staging 字节，不使用最终
  文件尺寸冒充累计写入，不混入 snapshot。计时含探针成本；RSS 是独立样本
  进程的累计 high-water，而非可重置的单操作峰值。三样本 nearest-rank p95
  等于最大值，不宣称生产尾延迟或物理磁盘流量。
- 每样本默认300秒，CLI 参数有界且报告记录；保留所有规模/重复、失败阶段、
  已完成操作、exit status、上限与可恢复 scratch 路径。坏进度输出不能阻止
  最终失败报告。正常样本清理自己的临时目录，超时遗留不扩展删除范围。
- 决策用所有重复均完成的 append 阶段累计字节中位数 W；精确十倍 N 的
  每事件倍率为 `(W_large/N_large)/(W_small/N_small)`，即累计倍率/10。
  达到任一触发条件即可 TRIGGERED；NOT_NEEDED 要求请求样本全部完成且
  至少有有效十倍对照，否则 INCONCLUSIVE。后续阶段失败可以保留已完成
  append 的触发证据，但不能伪称整组基准通过。
- 保存 Python/Node（可用时）/平台、HEAD/dirty paths/基准源码摘要、原始
  重复及各操作 p50/p95；长测仅显式 `make benchmark-optimization`，普通
  `test-verification-targets` 纳入小规模自测，不隐式启动长测。

- [x] fixture 采用合法事件生成器，三个规模使用相同事件分布/工件大小；临时目录隔离，重复三次，禁止读取用户业务运行做默认基准。
- [x] 测量 context append_many、replay、列表、冷/热投影、预览；用计数器统计逻辑 I/O，时间与 RSS 作为辅助指标。
- [x] 验证 10 倍事件量下的写入倍率；若连续两个规模的累计账本写入倍率均 >30，或每新增事件平均账本写入增长 >3 倍，则触发 OP-13。阈值是本计划的工程预算，不是既有性能事实。
- [x] 将数据、结论和原始日志摘要写入本计划执行记录；未触发时 OP-13 标 NOT_NEEDED，并保留完整性设计。
- [x] 运行 benchmark 自测，再运行三规模命令；规模太大无法完成时记录资源上限和失败规模，不能删掉失败点。

```sh
uv run --project packages/grid-agent pytest tools/tests/test_benchmark_optimization.py -q
uv run --project packages/grid-agent python tools/benchmark_optimization.py --events 1000 10000 100000 --output runs/optimization/benchmarks/report.json
```

**关闭条件**：可复现数据、明确分支决策；时间预算不能替代正确性门禁。提交主题：`perf: establish reproducible long-run resource budgets`。

#### OP-12 measurement record — 2026-09-05 12:11 CST

- Source `de3a5c7baa2258de3203cfd938b604347117a1e4`; benchmark SHA256
  `beb03997247da762a7495eacb00828965bf8ad5418fc02904dc22d9091e812a6`.
  Only JOURNAL/RESUME dirty at measurement start. macOS26.3 arm64,
  Python3.14.3, Node23.11.0; batch100, three repeats,300second sample limit.
- Nine of nine samples completed, no timeout/failed scale omitted; real replay
  equality, list count1, cold/hot equality, all six hot projector/materializer
  counters zero, real request preview valid. Request artifact exactly66,410bytes
  at every scale; initialization excluded and context ledger has N+1 events.
- Exact cumulative ledger bytes (final+backup) identical across each scale's
  three repeats. Final ledger sizes786,298 /7,896,303 /79,356,308 bytes are
  recorded separately and are **not** the cumulative write metric.

| N appended events | Cumulative ledger bytes | Append seconds p50 / p95 | Sample peak RSS bytes p50 / maximum |
| --- | ---: | ---: | ---: |
| 1,000 | 7,866,295 | 0.083386 / 0.084449 | 82,788,352 / 83,066,880 |
| 10,000 | 789,299,940 | 1.405892 / 1.468942 | 587,644,928 / 588,120,064 |
| 100,000 | 79,316,645,345 | 70.498804 / 70.525125 | 5,198,430,208 / 5,299,552,256 |

| Operation seconds p50 / p95 | N=1,000 | N=10,000 | N=100,000 |
| --- | ---: | ---: | ---: |
| context replay | 0.057193 / 0.057971 | 0.575093 / 0.577737 | 5.840944 / 5.865083 |
| run list | 0.046100 / 0.046757 | 0.454520 / 0.459789 | 4.936301 / 4.986432 |
| cold projection | 0.083612 / 0.083770 | 0.869022 / 1.019797 | 8.760987 / 8.841518 |
| hot projection | 0.064233 / 0.066214 | 0.683777 / 0.697590 | 7.004169 / 7.031487 |
| request preview | 0.003449 / 0.003596 | 0.003566 / 0.003646 | 0.003476 / 0.003568 |

- **Decision: OP-13 TRIGGERED.** Tenfold cumulative write ratios100.339479 and
  100.489866 both exceed30; corresponding per-event ratios10.033948 and
  10.048987 both exceed3. This proves the approved engineering trigger for
  this fixed workload, not a latency SLA or a general business distribution.
- Large sample process high-water reaches about5.30GB; per-operation RSS cannot
  attribute that cumulative peak solely to preview/projection. The fixed-size
  preview reads66,410bytes and does not prove bounded HTTP/artifact memory.
  Hot cache avoids rebuilding/writing but still reads144,912,541 logical bytes
  at100k; no O(1) read claim. No provider or operator business runs accessed.
- Raw full metrics/repetitions: `runs/optimization/benchmarks/report.json`;
  untruncated tool capture: `runs/optimization/OP-12/formal-benchmark-de3a5c7.json`.
  Selftest evidence and independent design/code reviews in the same OP-12 folder.
  Final benchmark23 tests PASS; prior20+verification6 PASS; doctor/links3/
  relative CLAUDE symlink/diffcheck PASS. Initial15 missing-source RED,
  fdopen duplicate-count RED and malformed-progress/no-comparison3RED retained
  and repaired. Independent measurement-review.md PASS.
- Fixed `de3a5c7` `make doctor && make check-release` exited0 at12:18 CST.
  Production pyright0; agent788/simulator165/Kernel464/pandapower79;
  inventory service11/domain118+genericPi1; Pi43+34; workbench128;
  gate selftests41 (including benchmark23); real installed SDK4; E2E31;
  offline/scripted24-of-24/full application; six-wheel/two-npm clean install
  and frozen source setup all PASS. Raw untruncated capture:
  `runs/optimization/OP-12/gate-release-de3a5c7.json`.
  Upstream dependency warnings retained; local Darwin verification, not remote
  CI or paid provider. OP-12 DONE; OP-13 starts with contract review, not an
  unreviewed writer switch. OP-08 scope approval remains outstanding.

### OP-13：触发后实现分段事务日志

**Files**：Modify `packages/capability-agent-kernel/src/capability_agent/application/context_store.py`、`application/workspace.py`；Create `packages/capability-agent-kernel/src/capability_agent/application/context_segments.py`；Test `packages/capability-agent-kernel/tests/application/test_context_store.py`。

#### OP-13 reviewed implementation contract — 2026-09-05

Root accepts the four persistence choices and the bounded consumer changes below
as necessary implementation detail of the approved segmented-log direction.
Sol authored the candidate; Terra independently reviewed B1–B3, initially BLOCK,
then PASS after the corrections below. Source design/review evidence remains in
`runs/optimization/OP-12/segment-contract-proposal.md` and
`segment-contract-review.md`; this versioned section controls implementation.
No OP08, domain behavior, user-run migration or paid/external scope is added.

##### Recommendation and rejected alternatives

Adopt an immutable, content-addressed segment chain with one constant-cardinality
manifest as the only authority for newly created workspaces. Keep
`core/context-events.jsonl` as an empty, regular **logical replay entry**, not as
a second ledger. Public `ApplicationContextStore.replay()` and
`replay_events()` retain their signatures and dispatch from that path to the
sibling segmented layout.

Two alternatives should be rejected:

1. Rewriting a full compatibility JSONL after every append preserves raw-file
   consumers but recreates the O(N²) write pattern and two crash-coordination
   authorities.
2. Appending a non-authoritative full JSONL mirror is linear in normal runs but
   exposes partial transactions after crashes and still creates ambiguous raw
   consumers. The existing legacy report discards all
   `application-context-event/1.0` records anyway, so that mirror has no report
   value.

The selected design therefore changes raw-file inspection for **new** runs but
preserves the supported store API and every `ContextEvent` domain meaning.

##### New workspace layout and fail-closed format selection

`ApplicationWorkspace.create()` creates the following new-run layout:

```text
core/
  context-storage.json          immutable layout marker
  context-manifest.json         absent until the genesis transaction commits
  context-segments/             immutable committed segments and owned temps
  context-events.jsonl          empty 0600 regular logical replay entry
  context.json                  rebuildable materialized snapshot
  .context-write.lock           fixed regular cross-process lock file
```

The layout marker is an exact-schema document:

```json
{
  "schema": "application-context-storage/1.0",
  "mode": "segmented-transactions/1.0",
  "run_id": "<portable run id>"
}
```

It is created exclusively, fsynced, and never rewritten. The segments directory
and lock file are created by the same new-workspace operation. Computed
workspace properties may expose these fixed paths; do not add a user/CLI writer
mode or a required constructor field that breaks structural workspace fakes.

Format selection is disk-derived and must not downgrade:

| On-disk condition | Reader/writer decision |
| --- | --- |
| Valid marker + segments directory | Segmented v1; a missing/invalid manifest after initialization is corruption |
| No marker, no manifest, no segments directory | Legacy JSONL v1, unchanged |
| Any partial/mixed segmented sentinel | Fail closed; never try the legacy JSONL reader |
| Valid segmented marker plus nonempty `context-events.jsonl` | Fail closed as inconsistent new layout; never interpret it as authority |

The one permitted pre-initialization state is a valid marker, an empty segments
directory, no manifest, and empty snapshot/logical-entry files. Only
`initialize()` may turn that state into the genesis commit. After genesis,
manifest absence is always an integrity failure.

Deleting only the manifest while leaving the marker or segments directory must
therefore fail, even if an attacker writes syntactically valid legacy JSONL into
the placeholder. If an attacker can delete and replace every layout sentinel,
there is no repository-local external trust anchor that can distinguish the
replacement; that limitation already exists for wholesale old-ledger
replacement and must not be disguised as downgrade protection.

Existing user runs are never migrated, rewritten, or deleted. A pre-OP-13 tree
with none of the segmented sentinels keeps the current legacy reader **and
writer**, including its existing transaction recovery.

##### Exact manifest and segment records

The manifest has a constant number of bounded scalar fields; it never contains
a segment list, event list, or accumulated digest history. Its byte size is
O(1) in transaction count (integer spelling may grow logarithmically):

```json
{
  "schema": "application-context-segment-manifest/1.0",
  "run_id": "<portable run id>",
  "segment_count": 17,
  "committed_revision": 1201,
  "committed_state_hash": "<64 lowercase hex>",
  "head_segment_sha256": "<64 lowercase hex>"
}
```

One successful `append_many()` produces exactly one segment. A segment has this
exact, extra-forbidden shape:

```json
{
  "schema": "application-context-segment/1.0",
  "run_id": "<portable run id>",
  "start_revision": 1102,
  "end_revision": 1201,
  "previous_segment_sha256": "<64 lowercase hex or null for genesis>",
  "previous_state_hash": "<64 lowercase hex>",
  "next_state_hash": "<64 lowercase hex>",
  "payload_sha256": "<64 lowercase hex>",
  "events": ["<strict ContextEvent JSON objects>"]
}
```

Digest definitions are unambiguous:

- `payload_sha256 = sha256(canonical_json_bytes(events))`.
- `segment_sha256 = sha256(canonical_json_bytes(the complete segment object))`.
- The committed filename is `context-segments/<segment_sha256>.json`; the
  manifest and predecessor links contain the bare 64-character digest.

The publisher must never overwrite a final segment. Stage under an unpredictable
owned temporary name in `context-segments`, fsync the descriptor, and publish
with an atomic no-clobber operation. If the final digest name already exists,
accept it only after binding a regular no-follow descriptor and proving its
bytes have the exact digest and content; otherwise fail. Then fsync the segments
directory. A portable no-clobber helper belongs in `context_segments.py`; plain
`os.replace()` over an unchecked final segment is not sufficient.

Replay starts from the manifest head, strictly decodes the exact digest-named
regular file, verifies its full-file digest, and walks predecessor digests
backward before reversing the chain. It must prove all of the following:

- exactly `segment_count` distinct segments are reachable, with no cycle;
- the first segment has `start_revision == 1` and a null predecessor;
- every segment contains at least one event and
  `len(events) == end_revision - start_revision + 1`;
- every event has the manifest run ID, contiguous sequence/revision values, and
  the existing event/state hash invariants;
- adjacent segment revision, predecessor digest, and state-hash boundaries
  match;
- the head end revision/state hash equals the manifest scalars; and
- replaying the existing reducer yields the same final revision and state hash.

Raw JSON is part of the integrity contract, not merely an input to Pydantic.
Use one strict decoder for marker, manifest, and segment bytes that:

- rejects duplicate object keys at every nesting depth through an
  `object_pairs_hook`;
- rejects `NaN`, `Infinity`, and `-Infinity` through `parse_constant`, and
  recursively rejects every non-finite decoded float (including exponent
  overflow such as `1e309`);
- accepts strict UTF-8 only; and
- requires `raw_bytes == canonical_json_bytes(decoded_value)`, including key
  order, separators, UTF-8 spelling, and exactly one final newline.

Only after that raw-canonical check may strict models validate the decoded
shape. For a segment, then verify the canonical `events` value against
`payload_sha256`, verify the complete raw bytes against both
`segment_sha256` and the digest filename, and finally replay the event/state
chain. A whitespace-reencoded or key-reordered document is invalid even when it
decodes to the same values and its filename was recomputed from those
noncanonical bytes.

Reads are bounded before allocation: marker and manifest are each limited to
16 KiB; a segment is limited to 64 MiB. The reader consumes at most limit + 1
bytes and rejects overflow. The writer applies the same segment limit to its
canonical bytes before staging, so an oversized `append_many()` fails before
durable mutation with the store still usable. These constants are segmented-v1
storage-format limits, not operator configuration; the legacy JSONL reader and
writer retain their existing behavior and receive no retroactive size limit.

Every marker, manifest, and segment read must pin the parent chain first (the
existing `open_bound_parent()` is suitable), then open the leaf with
`O_RDONLY | O_CLOEXEC | O_NOFOLLOW | O_NONBLOCK`, and only then use `fstat()` to
require a regular file before reading. Recheck the opened descriptor metadata
after the bounded read.

Identity treatment differs intentionally by mutability:

- The layout marker and content-addressed segments are immutable. Recheck that
  the currently named leaf is the same inode as the opened descriptor; a
  replacement is corruption.
- The manifest is the mutable atomic pointer. Pin and validate the opened
  regular descriptor and its selected immutable chain, but do **not** reject it
  merely because a concurrent writer atomically replaced the named manifest
  with a new inode after open. The opened old manifest is a valid committed
  prefix. No retry is needed if that old chain validates completely. This
  exception applies to lock-free replay; a writer holding the exclusive lock
  must still bind and recheck the currently named manifest before committing.

The current `read_bound_regular_file()` both omits `O_NONBLOCK` and enforces
named-leaf identity, which is wrong for the mutable-manifest case.
`context_segments.py` therefore needs narrow private readers with explicit
immutable/mutable binding modes rather than directly reusing that leaf reader.
This stays scoped to OP-13 storage and does not broaden the OP-08
public-artifact reader.

Unreferenced final-name segments are not committed. Readers ignore them; they
must never select “the newest filename.” Recovery may remove only exact owned
temporary files. It must not garbage-collect final-name segments during OP-13,
because doing so adds reader/GC races and risks historical user data.

##### Writer lock and stale-instance rule

The current in-process `RLock` remains for reentrancy/thread ordering, but it is
not a multi-instance transaction lock. Segmented writes additionally hold one
OS advisory exclusive lock on `core/.context-write.lock` from the first manifest
read through segment publication, manifest commit, and snapshot refresh.

The lock contract is:

- open no-follow, require a regular file, bind `(device, inode)` before and
  after acquisition, and fail on replacement;
- on the current supported Linux/macOS release targets, use POSIX `flock`,
  released automatically on process death, rather than a mkdir/PID lock that
  requires unsafe stale-lock deletion;
- import the POSIX locking facility conditionally so importing the package on
  another platform does not crash, but fail closed with a sanitized unsupported
  storage-platform error before creating or opening a segmented writer when no
  reviewed lock backend exists; OP-13 does **not** claim or implement untested
  Windows locking;
- after acquiring it, reread and validate the authoritative manifest/head;
- compare run ID, revision, state hash, and head digest with the store instance's
  cached base; a stale instance fails before staging anything rather than
  rebasing silently or creating a fork; and
- readers need no lock: one atomically read manifest selects an immutable chain.
  Old reachable segments are retained, so a reader sees either the old or new
  complete prefix while a writer commits.

Two processes constructed from the same head therefore have one winner. The
loser receives a sanitized `ContextStoreError`, becomes unavailable, and must
be reopened against the winning head before its caller deliberately retries.

##### Commit point and typed failure outcome

Before touching durable files, reduce and validate the complete draft batch.
Stage and fsync the next materialized snapshot after the segment is durable but
before the manifest replacement, so ordinary snapshot allocation/no-space
failures still occur before the authoritative commit.

Under the write lock, perform this sequence:

1. validate the locked base manifest/head;
2. stage and fsync the immutable segment;
3. atomically publish the segment without overwrite;
4. strictly fsync `context-segments/`;
5. stage and fsync the next `context.json` projection without publishing it;
6. stage and fsync the next constant-cardinality manifest;
7. atomically replace `context-manifest.json`;
8. strictly fsync `core/` — **this successful fsync is the commit point**;
9. publish the next in-memory snapshot immediately, then attempt to publish the
   already-staged `context.json`, fsync `core/`, and clean only owned temporary
   files.

Authoritative fsync helpers must propagate failure; the current best-effort
directory-fsync helper is not suitable for steps 4 or 8.

Outcome semantics are explicit:

| Failure boundary | Logical outcome | Required API behavior |
| --- | --- | --- |
| Draft/reducer validation | Definitely uncommitted | Existing `ContextStoreError`; store remains usable |
| Segment/snapshot/manifest staging or segment publication before manifest replacement | Definitely uncommitted | Sanitized `ContextStoreError`; best-effort cleanup; store unavailable after any uncertain I/O |
| Manifest replacement not performed or atomically reports failure | Definitely uncommitted | Same; old manifest remains authority |
| Manifest replacement succeeded but its directory fsync reports failure | **Indeterminate durability** | Raise `ContextCommitIndeterminateError(ContextStoreError)`; store unavailable; never claim rollback or retry in-place |
| Commit point passed; snapshot replace/fsync or cleanup then fails | Definitely committed | `append_many()` returns the committed event tuple normally, publishes the next in-memory snapshot, records projection repair as pending, and never rolls back/deletes authoritative or sidecar data |

`ContextCommitIndeterminateError` is an additive public subtype with no backend
message or path leakage. It means “do not retry and do not delete files that the
transaction may reference; reopen/replay to determine the committed prefix.” It
does not mean committed or rolled back.

Only classified snapshot/cleanup I/O failures after the commit point may be
treated as a stale derived projection. The manifest's committed revision and
state hash are the durable stale-snapshot record; the live store additionally
sets a private `_snapshot_refresh_pending` flag with a sanitized reason code.
It retries atomic snapshot materialization after reopening and at the next safe
locked entry, but a repeated projection-only failure does not change the
already-valid append result or authorize an event retry. `store.snapshot`
remains the committed next state. `verify_materialized_snapshot()` remains a
strict check and raises while disk projection is stale; it does not pretend the
old file is current. OP-13 does not add a report dependency on this private
status: report-side public replay verifies the manifest authority directly, so
snapshot projection diagnostics cannot block or weaken the primary answer.

Do not catch programming errors or all `BaseException` as benign projection
warnings. A control-flow `BaseException` during the manifest boundary keeps its
original type and has an unknown outcome; upper layers must preserve potentially
referenced sidecars. Process-kill tests determine recovery from disk rather
than expecting in-process cleanup.

All three `TurnController` mutation paths must distinguish commit outcome:

- `start()` currently restores the prior active-turn and active-draft files for
  every `BaseException` around `store.append()`. It may restore them only for a
  definitely-uncommitted typed error. On indeterminate, unclassified, or
  control-flow failure it leaves the post-preparation filesystem state intact
  (the new active-turn file remains and the obsolete draft remains removed),
  then rethrows; a committed `turn.started` must not lose its active sidecar to
  compensation.
- `submit()` must separate sidecar-write compensation from the
  `store.append_many()` call. A sidecar write failure before append restores the
  four captured file states. A definitely-uncommitted `ContextStoreError` from
  append also restores them. `ContextCommitIndeterminateError`, an unclassified
  post-entry exception, or a control-flow `BaseException` preserves all answer,
  admission, archive, and active files and is rethrown without being flattened
  to an ordinary `AnswerCommitError`. Validate the returned two-event tuple
  outside the rollback block so an implementation invariant failure cannot
  delete potentially referenced files.
- `fail()` already performs active/draft cleanup only after `append_many()`
  returns. Preserve that ordering: indeterminate/control-flow failure rethrows
  with active files intact, performs no optional failure-answer publication,
  and does not call `_record_turn_failed`; a known committed return proceeds to
  its existing idempotent cleanup. Any later cleanup/publication error cannot
  undo the committed failure segment or trigger another context append.

The runner must recognize an indeterminate commit before its broad
ordinary-exception compensation and must not call `_fail_active_turn()`,
`_mark_failed()`, or retry another context transition for that turn. The B/C
supplement below defines concrete sticky health and lexical phase checks so
existing lifecycle/projector wrappers need not relay the exception subtype.
It may return a sanitized failed application outcome,
preserving the run for reopen/recovery. A known committed transaction is
returned normally even when `context.json` needs repair, so it follows the
existing successful controller path.

##### Recovery and snapshot contract

The manifest, not `context.json`, is authority. On segmented-store construction:

1. take the writer/recovery lock;
2. select format without fallback;
3. replay the manifest-selected chain independently;
4. if `context.json` is missing, stale, truncated, or hash-invalid, attempt an
   atomic rebuild from replay; and
5. expose that replayed state as `store.snapshot` even if the derived-file
   rebuild reports a classified I/O failure, retaining the pending repair flag.

A crash before the manifest commit leaves the old manifest authoritative; a
published-but-unreferenced segment is logically discarded. A crash after the
commit point leaves the new chain authoritative even if the snapshot is old.
Recovery must always satisfy:

```python
assert recovered.revision in {before.revision, committed.revision}
assert recovered == replay_committed_segments()
assert no_partially_committed_transaction()
```

Missing/truncated/digest-invalid referenced segments, duplicate revisions,
chain forks selected through a forged predecessor, marker/run-ID mismatch,
symlink/replacement races, and an invalid manifest are authority failures and
raise sanitized `ContextStoreError`. They are never repaired from snapshot or
the empty JSONL placeholder. A classified snapshot-repair I/O error leaves the
opened store on replayed authority with repair pending; it does not validate or
publish the stale file as current.

##### Performance claim boundary

Every healthy segmented append attempts and stages the complete current
`context.json` in the same transaction. With normal I/O it materializes that
snapshot before return; the classified post-commit projection failure follows
the pending-repair success semantics above. OP-13 does not introduce a
checkpoint cadence, intentionally delayed public snapshot, or snapshot API
change. That choice keeps OP-13 focused on the demonstrated full-ledger rewrite
problem.

The OP-13 rerun of the same fixed-state 1k/10k/100k workload must report two
separate logical-write counters and keep the original ledger gate:

1. `context_ledger_write_bytes`: all canonical segment bytes plus every staged
   manifest byte. Its tenfold ratios must remain `<=15`.
2. `context_total_logical_write_bytes`: the first counter plus every staged
   `context.json` byte, including failed-attempt bytes where the existing probe
   counts them. Its tenfold ratios on the same fixed-state workload must also
   remain `<=15`.

Directory metadata/fsync traffic is reported separately when observable and is
not invented as payload bytes. Neither counter uses final file size as a proxy.
The first remains directly comparable to the canonical ledger gate; the second
prevents a constant manifest from hiding snapshot rewrite cost.

Add one bounded 100/1,000-event growing-core characterization using
`diagnostic.recorded`, which appends to the real `CoreContext.diagnostics`
collection. It must complete and replay equivalently and must publish its
snapshot and total-write ratios, but that ratio is descriptive rather than an
OP-13 acceptance threshold.
Repeatedly serializing genuinely growing current state can remain superlinear;
OP-13 must state that this cost is unresolved and must not claim comprehensive
O(N) storage behavior from the fixed-state result.

A focused unit test must construct/recover the segmented store, replace the
full-chain replay helper with a failure sentinel, and then successfully append
from the cached validated head. Full-chain replay is allowed on construction,
explicit replay, and recovery, but not on each healthy append.

##### Public API, Path replay, and compatibility

The following API remains unchanged:

- `ApplicationContextStore.initialize(workspace, ...)`
- `append()` / `append_many()` and their return types
- `snapshot`, `workspace`, `replay()`, `replay_events()`
- `verify_materialized_snapshot()`
- `ContextEvent` fields, ordering, hashes, and reducer semantics
- `ApplicationWorkspace.context_events_path`

For a Workspace argument, replay uses its fixed sibling paths. For a Path
argument, a path named `context-events.jsonl` remains the logical entry:

1. safely bind the path and its parent as today, preserving relative-path use;
2. inspect the exact sibling marker/manifest/segments sentinels;
3. choose segmented or legacy by the fail-closed table above; and
4. in segmented mode require the entry itself to be an empty regular file, but
   obtain all events from the manifest chain.

An invalid segmented layout never falls back merely because the placeholder is
valid JSONL. Arbitrary legacy ledger paths without the sibling sentinels retain
the current JSONL behavior. No new public manifest-path overload is needed.

###### Legacy report bridge

`grid_agent.analysis.report._read_context_events()` directly reads the path
but already discards every application-context event. Do not create a full
JSONL mirror for it. Instead, narrowly update
`grid_agent.compat.v1_0_1_report.PandapowerApplicationReportShell` to call the
public `ApplicationContextStore.replay_events(workspace)` inside its existing
report-isolation boundary before invoking the legacy renderer:

- successful replay keeps the current report meaning: the empty placeholder
  yields no legacy analysis events;
- a replay/integrity failure adds one sanitized “application context ledger
  unavailable” report diagnostic and rendering continues; and
- ordinary report/descriptor/I/O failures remain nonfatal to the primary
  answer. `BaseException` is not converted into a report warning.

The compatibility single-run answer reader and Kernel runner replay call sites
already use the public API and need replay regressions, not a replay-call rewrite.
The runner's separate indeterminate-compensation changes remain required above.

###### Legacy writer coverage

Legacy-format tests must use a test-only fixture that materializes the exact
pre-OP-13 workspace tree with all three segmented sentinels absent. Do not add a
runtime/CLI `legacy` switch, and do not weaken old malformed/truncated,
replacement, transaction rollback, or byte-for-byte failure assertions.

New-workspace tests separately prove that `ApplicationWorkspace.create()`
selects segmented v1 by default. The rollout sequence is implementation-local
reader/writer opt-in during development, all compatibility/recovery/release
gates, then the single default switch in workspace creation. A rollback may
switch future workspace creation back to legacy, but the segmented reader must
remain permanently available for runs already created.

##### Required scope beyond the canonical three source files

The canonical source ownership remains:

- `application/context_segments.py`: strict records, digest/chain validation,
  safe segment publication, strict fsync, lock, and segmented replay.
- `application/context_store.py`: public dispatch, reducer integration, commit
  outcomes, snapshot recovery, and legacy backend retention.
- `application/workspace.py`: new-run marker/directory/lock/placeholder creation
  and computed paths.

Additional production/tool changes that are actually necessary:

1. `application/turns.py`: apply the outcome-aware compensation rules to
   `start()`, `submit()`, and `fail()`; retain restoration only for definitely
   uncommitted failures and preserve potentially referenced sidecars otherwise.
2. `application/__init__.py` and top-level `capability_agent/__init__.py`: export
   the additive indeterminate subtype and read-only `ContextStoreHealth` enum
   symmetrically, as required by the B/C compensation supplement below.
3. `application/runner.py`: use concrete typed health plus lexical persistence
   phases to suppress unsafe compensation even through wrapped exceptions;
   follow the B/C supplement while returning only sanitized failure information.
4. `grid_agent/compat/v1_0_1_report.py`: narrow public-replay validation and
   nonblocking diagnostic; no legacy report/parser rewrite.
5. `tools/benchmark_optimization.py`: count actual staged segment bytes and
   manifest bytes at the new seam, and report committed segment storage rather
   than the zero-byte logical entry. Preserve initialization exclusion; report
   snapshot bytes separately **and** include them in the additional total
   logical-write counter.

No production changes are required in Kernel projector, compatibility
single-run, inventory, a CLI, or any domain pack if the public store API is
preserved.

Test changes beyond canonical `test_context_store.py` are required only where
tests inspect physical JSONL bytes rather than behavior:

- Kernel `test_workspace.py`, `test_turns.py`, `test_projector.py`, and relevant
  `test_runner.py` cases;
- grid generic-entrypoint/offline-walking-skeleton raw-ledger assertions;
- targeted `compat/single_run` and v1 report bridge regressions;
- benchmark instrumentation self-tests; and
- existing installed-smoke and inventory-conformance replay assertions as
  unchanged end-to-end gates.

Tests for the distinct old `grid_agent.analysis.store.AnalysisContextStore` and
`context/context-events.jsonl` are out of scope and must remain unchanged.

##### Minimum test matrix

| Area | Required cases and assertions |
| --- | --- |
| New default | New workspace has valid marker/segments/lock, empty logical entry, no pre-genesis manifest; genesis creates one committed segment and manifest |
| Legacy | Explicit pre-OP-13 fixture reads/appends unchanged; malformed line, missing newline, replacement, rollback, and relative Path tests retain their old assertions |
| Anti-downgrade | Missing/corrupt manifest with marker or segments present; partial sentinels; nonempty placeholder; marker/run mismatch all fail without legacy fallback |
| Raw/record validation | Truncated/missing head; duplicate top-level and nested event-payload keys; non-finite constants/exponent overflow; whitespace/key-order recoding; noncanonical digest-named bytes; oversize marker/manifest/segment; wrong filename/payload digest; extra/missing fields; wrong run ID; cycle, duplicate/noncontiguous revision, predecessor/state-hash mismatch |
| Commit boundaries | Inject before/after segment write/fsync/publish/directory fsync, manifest write/fsync/replace/directory fsync, snapshot replace/fsync, and cleanup; a fresh process sees exactly old or committed revision |
| No space | Fail each allocation/write boundary; precommit stays old, postcommit snapshot failure replays new and rebuilds projection |
| Forced exit | Use subprocess `os._exit` at each durable boundary; reopen from disk and assert the three canonical recovery invariants without writer-memory helpers |
| Concurrency | Two processes append from the same head behind a barrier: exactly one wins, loser is stale/unavailable, no branch/lost update; deterministic manifest replacement after reader open accepts the opened old valid inode, while a reader starting later sees the new complete prefix |
| Path safety | Relative logical path, symlinked parent, marker/manifest/segment/lock replacement, FIFO/socket/device leaves proving nonblocking rejection, final-name collision, and no overwrite outside `core/` |
| Turn compensation | For `start`, `submit`, and `fail`: definitely-uncommitted typed append failures restore only their pre-append file states; indeterminate/unclassified/control-flow outcomes preserve post-preparation files; known committed plus stale snapshot follows success and replays all referenced sidecars |
| Runner | Indeterminate start/submit/fail does not call `_fail_active_turn`, `_mark_failed`, retry a context transition, or delete active/answer artifacts; failure output is sanitized and a fresh replay determines the prefix |
| Platform lock | Linux and macOS exercise real cross-process `flock` and crash release; a simulated unsupported platform fails before segmented storage creation/open and does not fall back to an unlocked writer |
| Report | Segmented public replay is validated, legacy report still sees no analysis ledger events, corrupt segment produces only sanitized report diagnostic, and no full JSONL mirror is generated |
| Consumers | Kernel runner/turns/projector equality, `compat.single_run` Path replay, inventory conformance, and installed smoke all match `store.snapshot` |
| Performance | Instrument real segment, manifest, and snapshot staging; reject a zero/stale probe; fixed-state 1k/10k/100k requires both ledger-only and total logical-write tenfold ratios `<=15`; cached append must not replay the chain; 100/1,000 growing-core completes/equates and reports its non-gating ratio and unresolved scope |

Every recovery helper in tests must read the real marker, manifest, and segment
files through an independent replay path. It may not return the writer's cached
snapshot or infer commitment from a test hook call count.

##### Compensation health and wrapper seams — B/C contract supplement

This supplement refines the earlier indeterminate-exception rules. Typed store
health plus lexical runner phases govern compensation even when an adapter
wraps the original exception. It does not expand Slice A or authorize OP-08.
The source review motivating this supplement is retained in the ignored
`runs/optimization/OP-13/compensation-seams.md`; this canonical section owns
the implementation and acceptance requirements.

###### Decision

Use one explicit read-only health value on the concrete
`ApplicationContextStore`, plus lexical runner phases around provider work and
controller persistence. Do not require every existing wrapper to preserve a
new exception subtype, and do not inspect duck-typed flags on controllers,
projectors, reports, or injected fakes.

The public typed state is:

```text
ContextStoreHealth.READY
ContextStoreHealth.UNAVAILABLE
ContextStoreHealth.COMMIT_OUTCOME_UNKNOWN
```

`ApplicationContextStore.health -> ContextStoreHealth` is read-only.
`COMMIT_OUTCOME_UNKNOWN` is sticky for that instance: only reopening and
replaying the workspace can establish a new usable instance. The existing
private snapshot-repair-pending state remains separate; a known committed
transaction with a stale rebuildable snapshot is still `READY`.

Once health is `COMMIT_OUTCOME_UNKNOWN`, every later store mutation rejects
without touching disk and leaves health unchanged. That rejection must not
overwrite the sticky state with `UNAVAILABLE`; only an authoritative backend's
ambiguous commit boundary can enter unknown, and only a fresh replayed store
can leave it.

Runner checks use `isinstance(store, ApplicationContextStore)` followed by the
enum property. A structurally injected test store is not queried for `health`;
there is no `getattr(..., "health")`, truthy flag, or Protocol expansion.

The segmented backend sets `COMMIT_OUTCOME_UNKNOWN` before propagating:

- `ContextCommitIndeterminateError` after manifest replacement when directory
  durability was not established; and
- an unclassified exception or control-flow `BaseException` while manifest
  replacement/commit outcome cannot be proven old or committed.

A validation failure or a persistence failure proven to precede manifest
replacement is `UNAVAILABLE` (or remains `READY` for preflight validation), not
unknown. A successful durable manifest commit followed by a classified
snapshot-refresh failure publishes the next memory state, returns success, and
remains `READY` with private repair pending.

The same health contract applies to the retained legacy writer without changing
its JSONL or transaction-record format. Its current append path can swallow an
exception from `_rollback_transaction()` and then propagate the original
ordinary `ContextStoreError`; that exception type alone is **not** proof of
rollback. After any failure once the legacy transaction may have touched an
authoritative file, re-read the ledger and snapshot through the bound safe
reader and compare both against the transaction's recorded previous hashes:

- an exact old ledger/snapshot pair means definitely uncommitted and health
  becomes `UNAVAILABLE`, preserving the existing fail-closed instance behavior
  and byte-for-byte rollback assertions; but
- a missing, unreadable, mixed, new, or otherwise non-old pair after rollback
  failure means `COMMIT_OUTCOME_UNKNOWN`, while the original exception remains
  the propagated error.

Thus `UNAVAILABLE` means mutation is prohibited, not that every historical
error was implicitly rolled back. Controller compensation is safe only when
the error is a known definitely-uncommitted type **and** concrete health is not
unknown. A fresh legacy recovery may use its existing transaction marker to
resolve old/new state; no legacy format, normal rollback behavior, or migration
is added here.

###### Why this is smaller than wrapper-by-wrapper typed relay

Two designs were considered:

1. **Relay `ContextCommitIndeterminateError` through every wrapper.** This
   requires special catches in controller, both projector append sites, report
   reference publication, completion/failure lifecycle helpers, and runner. It
   still cannot preserve the original type of a control-flow `BaseException`
   while converting it to an ordinary typed error. One missed broad catch
   silently re-enables compensation.
2. **Concrete store health plus lexical runner phase — selected.** The store is
   the only component that knows the durable boundary. The runner already owns
   a concrete `ApplicationContextStore | None`, so it can compare a real enum
   directly. Existing `DomainProjectionError`, `ApplicationConfigurationError`,
   and the original `BaseException` remain unchanged. Structural controller and
   projector fakes need no new attribute.

This state is not a generic result protocol and is not added to
`TurnControllerSession`. It answers only whether another context mutation or
destructive compensation is safe on this concrete store instance.

###### Runner phase rule

The current inner `try` combines `_call_prompt()` and `controller.submit()`.
Split it into two lexical blocks:

1. **Provider/projector phase.** Ordinary provider failure retains the existing
   best-effort `controller.fail()` path while the concrete store is not
   `COMMIT_OUTCOME_UNKNOWN`. This includes ordinary transport/model failures.
   A provider-phase `BaseException` retains the current behavior: attempt the
   same safe failure publication, preserve the original control-flow exception,
   and attach only a compensation `BaseException` as its cause.
2. **Controller submit phase.** After entering `controller.submit()`, an
   indeterminate, unclassified `Exception`, or control-flow `BaseException`
   must not invoke `controller.fail()` or any later context compensation. The
   controller owns definitely-uncommitted sidecar restoration. Rethrow the
   original exception unchanged; do not convert a control-flow exception. A
   known definitely-uncommitted `AnswerCommitError`, or a non-indeterminate
   `ContextStoreError` after controller restoration, retains the old failure
   lifecycle when concrete store health is not unknown.

Use a module-private enum, not an object flag or `getattr`, for the outer handler:

```text
_CompensationDisposition.ALLOWED
_CompensationDisposition.PRESERVE_POSSIBLE_COMMIT
```

Set `PRESERVE_POSSIBLE_COMMIT` when an unclassified/indeterminate failure leaves
`start()` or `submit()`, and whenever the concrete store health is
`COMMIT_OUTCOME_UNKNOWN`. Do not set it for a known definitely-uncommitted
`AnswerCommitError` or non-indeterminate `ContextStoreError` after its owning
controller compensation has completed and concrete store health is not
unknown. The outer `except Exception` checks both the enum and the store health
before **each** call to `_fail_active_turn()` or `_mark_failed()`. It may still
construct a sanitized failed `ApplicationOutcome`; it does not append another
context event when preservation is required.

This lexical split is necessary even with store health. A bug after a store
append returned committed events can leave the store `READY` while the
controller raises a `RuntimeError`; the submit-phase disposition still prevents
a second transition. Conversely, an ordinary provider failure with a `READY`
store keeps the old failure lifecycle.

`controller.start()` also needs its own boundary because it currently runs
outside the inner `try`. A typed definitely-uncommitted error may retain normal
application-failure handling after the controller restores its pre-start files.
An indeterminate or unclassified exception sets `PRESERVE_POSSIBLE_COMMIT`;
`BaseException` is rethrown unchanged and reaches only `finally` cleanup.

For both `start()` and `submit()`, “known definitely uncommitted” means the
caught value is `AnswerCommitError`, or is `ContextStoreError` but not
`ContextCommitIndeterminateError`, **and** a concrete store is not
`COMMIT_OUTCOME_UNKNOWN`. Ordinary admission/preflight/validation rejection is
therefore not mislabeled as an uncertain commit.

###### Exact seam behavior

| Current seam | Required narrow behavior |
| --- | --- |
| `runner.py:601` ordinary inner catch | This catch belongs only to provider/projector work after the split. Before calling `_fail_active_turn`, require disposition `ALLOWED` and concrete store health not unknown. A submit-phase known definitely-uncommitted typed error retains this lifecycle; only an unclassified/indeterminate submit exception sets preserve disposition. |
| `runner.py:610` control-flow catch | Provider-phase `BaseException` may use the existing failure attempt and must rethrow the original object. Submit-phase `BaseException` performs no compensation and is rethrown directly. |
| `runner.py:682` outer catch | Recheck store health and disposition. If either requires preservation, skip both `_fail_active_turn` and `_mark_failed`; return only sanitized failure output/diagnostic. Never infer rollback merely from the caught wrapper type. |
| `_fail_active_turn():1542` | Add the concrete `store` as a private keyword argument and return `_CompensationDisposition`. Check typed health before calling `controller.fail`. A known successful `fail()` return yields `ALLOWED`; any ordinary exception after entering `fail()` is swallowed only to preserve the original provider error but yields `PRESERVE_POSSIBLE_COMMIT`, even if store health is still `READY`. Unknown health also records the fixed diagnostic `context_commit_outcome_unknown`. A control-flow exception still propagates. The caller merges the returned disposition before any later append. |
| `_mark_failed():1498` | Do not call an indeterminate write away. Skip the append if health is already unknown. If its own append makes health unknown, retain the original application failure as primary, record the same fixed diagnostic, and return without recursion or retry. Ordinary best-effort failure remains nonfatal. |
| `_record_report_reference():1462` | Existing `ApplicationConfigurationError` wrapping may remain. Store health survives the wrapper. No sidecar compensation occurs here. |
| `_publish_report():1315` | Presentation/write/admission exceptions remain an ordinary nonblocking `report_unavailable` result only when store health is not unknown. If report-reference append made health unknown, rethrow the caught existing exception; do not convert it into a report warning and continue to completion. Outer handling skips all context compensation. |
| `_mark_completed():1481` | Existing `ApplicationConfigurationError` wrapping may remain. Outer handling must observe unknown health and must not follow it with `_mark_failed`. A known definitely-uncommitted completion error keeps the existing failure path. |
| `projector.py:218-220,652-654` | Existing `DomainProjectionError` / `CapabilityTransportError` wrapping may remain under this design. The segmented store's sticky unknown health survives flattening; the provider-phase catch checks it before attempting `controller.fail`. Therefore no projector production change is required solely for relay. |

The fixed `context_commit_outcome_unknown` diagnostic uses the existing
artifact/stderr diagnostic path; it is not itself appended to the unavailable
context store and contains no exception text, path, or provider data.

###### Controller compensation contract

The canonical controller rules remain, with one implementation clarification:

- `start()`: restore prior active/draft files only for a proven precommit
  failure. Preserve the post-preparation active sidecar on indeterminate,
  unclassified, or control-flow outcome.
- `submit()`: separate sidecar writes from store append. Restore captured files
  for sidecar-write or proven precommit typed failure. Preserve them for
  indeterminate, unclassified, or control-flow outcome. Validation of the
  returned event tuple occurs outside the destructive rollback block.
- `fail()`: active/draft cleanup, optional failure-answer publication, and
  `_record_turn_failed` occur only after append returned a known committed
  result. Any exception from append leaves those files and in-memory controller
  records untouched.

Controllers should continue to propagate `ContextCommitIndeterminateError`
when directly available, but runner safety does not depend on every adapter or
projector retaining it. No new `AnswerCommitError` subtype is required.

###### Minimal source scope

- `application/context_store.py`: define/export `ContextStoreHealth`, expose the
  read-only property, and set sticky unknown at the backend's ambiguous commit
  boundary. This belongs to Slice B/C, not Slice A codec/reader.
- `application/turns.py`: apply the already-canonical three-path compensation
  rules; no store-health duck typing.
- `application/runner.py`: provider/submit lexical split, private compensation
  enum, concrete health checks at the named seams, and fixed diagnostic.
- Public `application/__init__.py` and `capability_agent/__init__.py`: export the
  health enum consistently with the existing store error exports.

No production change is required in `projector.py`, report implementations, a
Domain Pack, Kernel SPI protocols, or injected fake interfaces for this
decision. `grid_agent.compat.v1_0_1_report.py` remains separately required by
the physical segmented-layout compatibility contract, not by compensation
state propagation.

###### Focused RED/GREEN matrix

1. Store transition tests prove `READY -> UNAVAILABLE` for a definite
   precommit I/O failure, `READY -> COMMIT_OUTCOME_UNKNOWN` for manifest
   durability ambiguity/control-flow injection, stickiness after later calls,
   and a fresh reopened instance resolving to a valid old or committed prefix.
   A later rejected append on the unknown instance must leave health unknown,
   not downgrade it to unavailable.
   Legacy fault injection separately proves successful old-pair rollback yields
   `UNAVAILABLE`, while a swallowed rollback failure with no provable old pair
   yields sticky unknown and prevents sidecar compensation, without changing
   the legacy ledger bytes or transaction schema.
2. A projector append sets unknown, projector wraps it as
   `DomainProjectionError`, and runner calls neither `controller.fail` nor
   `_mark_failed`.
3. An ordinary provider exception with a `READY` store still calls
   `controller.fail` once and follows the existing failed-run path.
4. If that `controller.fail` append becomes unknown, the original provider
   failure remains the sanitized primary failure, active sidecars remain, and
   `_mark_failed` is not called.
   The same no-mark assertion applies when `controller.fail` raises an
   unclassified `RuntimeError` after a known commit while store health remains
   `READY`; the private returned disposition carries that lexical uncertainty.
5. `controller.submit` indeterminate and unclassified `RuntimeError` cases both
   preserve all answer/admission/active files and cause zero compensating
   transitions. A `BaseException` case proves object identity is preserved and
   only `finally` cleanup runs.
   Separate admission/preflight `AnswerCommitError` and definite
   non-indeterminate `ContextStoreError` cases prove the old failure lifecycle
   still runs when store health is not unknown.
6. Provider-phase `BaseException` retains the existing single failure attempt
   and original exception/cause behavior, demonstrating that the submit rule
   did not disable ordinary provider cleanup.
7. Report-reference append unknown is not returned as
   `ReportPublication("unavailable")`; completion and application-failed
   appends are not attempted, and the report artifact remains for recovery.
8. Completion append unknown is not followed by `_mark_failed`; failure output
   is sanitized and all previously committed answer/report artifacts remain.
9. `_mark_failed` becoming unknown emits only the fixed diagnostic and performs
   no recursive/retry append.
10. Structural injected controller/projector fakes without a `health` member
    continue to work because runner reads health only from its concrete
    `ApplicationContextStore` reference.

###### Non-goals

- Do not change Slice A raw codec/reader or its current review boundary.
- Do not create a general transaction-result protocol, attach flags to
  exceptions, or add `health` to controller/projector/report Protocols.
- Do not reinterpret report rendering failures as primary failures; only a
  context commit whose outcome is unknown escapes report-warning isolation.
- Do not retry, compensate, delete sidecars, or select a committed prefix from
  in-memory assumptions after unknown health. Fresh public replay is the only
  resolution.

#### OP-13 implementation slices and review gates

Each slice follows RED → minimal implementation → focused GREEN → independent
review → explicit-path commit. Do not run concurrent complete gates, and do not
switch the workspace default before slices A–C pass. Existing legacy assertions
remain; raw-file tests gain new-layout equivalents rather than reading an empty
placeholder and falsely passing.

**A — strict format and reader, no writer/default switch**

Files: Create
`packages/capability-agent-kernel/src/capability_agent/application/context_segments.py`,
`packages/capability-agent-kernel/tests/application/test_context_segments.py`;
test-only pre-OP13 workspace fixture belongs in
`packages/capability-agent-kernel/tests/conftest.py` if shared. Do not change
`ApplicationWorkspace.create()` in this slice.

Internal interfaces (not added to the public Kernel SPI):

```python
def decode_document(raw: bytes, *, max_bytes: int) -> dict[str, object]: ...
def encode_segment(
    events: tuple[ContextEvent, ...], previous: SegmentManifest | None,
) -> tuple[ContextSegment, bytes, str]: ...
def decode_segment(raw: bytes, *, expected_sha256: str) -> ContextSegment: ...
def read_chain(
    entry_path: Path,
) -> tuple[SegmentManifest, tuple[ContextEvent, ...]]: ...
```

`StorageMarker`, `SegmentManifest`, `ContextSegment` implement the exact
schemas above; `SegmentStorageError` is the private sanitized error. The
segment codec verifies structural/event boundary/digest consistency; the public
store later applies the existing reducer to the returned complete events.
This split must not import `context_store` back into `context_segments`.

- [x] Add actual canonical genesis/batch files and first RED tests for codec,
  reader, limits and anti-downgrade; evidence-retention deviation noted below.
- [x] Reject top/nested duplicate keys, nonfinite/exponent overflow, UTF-8 error,
  whitespace/key-order recoding, wrong filename/payload hash, missing/extra
  schema fields, inconsistent revision/count/run/hash and nonregular files.
  Require exact max+1 read enforcement, not a post-read length check alone.
- [x] Test manifest opened-before-replace returns old full chain; marker or
  immutable segment replacement fails. Wrong/missing manifest with new sentinels
  never reads fallback JSONL. Test helpers construct real canonical files, not
  writer-memory return values.
- [x] Run and review `test_context_segments.py`; commit only reader/codec/tests.
  Existing production defaults and old ledger remain unchanged.

Slice A source: `3bc24a2`. Final root checks: 32 focused tests, 496 complete
Kernel tests and production pyright pass; independent review passes with H1
(mtime-restored same-inode rewrite) and M1 (replacement after final fstat)
closed. Full raw root checks are retained in
`runs/optimization/OP-13/root-slice-a-gates-final.json`; review history remains
in `slice-a-review.md`. This is not the later full release gate or performance
acceptance.

Evidence-retention deviation: the worker's initial/H1 RED tool responses were
not archived in full; later race RED evidence also records a summary rather
than its complete traceback. They are not recreated or labeled full raw
evidence. Root's actual resolved-root probes and complete verification captures
are retained, and all four race regressions were independently rerun. Slice A
code is accepted with this explicit historical audit limitation. Subsequent
slices must capture complete tool returns immediately, including failed runs.

**B — transaction writer and public store dispatch, explicit new-layout fixtures**

Files: Modify the new module, `application/context_store.py`, public error
exports `application/__init__.py` and `capability_agent/__init__.py`;
Test `test_context_segments.py` and `test_context_store.py`.
A private `create_segmented_layout(core_path: Path, run_id: str) -> None`
creates only a fresh marker/directory/lock; test fixtures can explicitly call
it before initialization until the default switch. It must reject existing
partial/nonempty layouts, not migrate them.

- [ ] Add RED tests for public Workspace/Path dispatch, genesis, append/replay
  equality, reopen with absent/stale snapshot and strict snapshot verification.
  Use a genuine pre-OP13 fixture for old writer fault-injection tests; do not
  delete new sentinels to manufacture a legacy fixture.
- [ ] Separate common event reduction from backend publication so both backends
  preserve identical `ContextEvent` semantics. Segmented store construction
  validates/replays the chain; healthy append only validates locked current
  head against cached base. Prove append works with full replay patched to fail.
- [ ] Implement the reviewed segment publication, strict fsync and locked
  constant manifest protocol. Return committed events with pending snapshot
  repair only after the durable commit point; raise the additive public
  `ContextCommitIndeterminateError` for uncertain durability. Export the
  read-only `ContextStoreHealth`; test sticky unknown across later rejected
  calls and legacy rollback ambiguity using the supplement's old-pair proof.
- [ ] Inject ordinary I/O failures and subprocess `os._exit` at every boundary
  in the reviewed matrix. Inspect real disk state in a fresh process:

```python
assert recovered.revision in {before.revision, expected_committed.revision}
assert recovered == independently_replayed_disk_chain
assert [event.sequence for event in disk_events] == list(range(1, recovered.revision + 1))
assert recovered.state_hash == independently_replayed_disk_chain.state_hash
```

- [ ] Use an actual two-process barrier with two instances loaded from one head;
  exactly one append wins, loser fails stale, and no event is lost/forked.
  Kill the lock holder and prove another process can acquire the same safe lock.
  Include FIFO and lock/parent/manifest replacement, oversize preflight with a
  still-usable store, and absent locking backend.
- [ ] Full Kernel tests and production pyright; independent persistence review.
  Commit this opt-in backend only after high-priority findings are resolved.

##### B implementation refinement: bound directory generation and failure phases

The following is part of B acceptance, not additional OP-08 scope. Keep physical
helpers private to `application/context_segments.py` and transaction orchestration
in `application/context_store.py`; no public callback or transaction protocol.
The same locked core descriptor is borrowed by all writer operations.

Cache the successfully constructed core and named `context-segments` directory
identities as `(st_dev, st_ino)`, validating directory mode and no-follow access
on every observation. Do not compare directory timestamps or auto-rebase an old
instance. Bracket constructor chain replay with safe core-path and segments-name
checks. On append, repeat these checks before/after locked head reading, directly
before manifest replacement, after manifest replacement plus core fsync, and
before a normal return following snapshot work. The segment publisher separately
compares cached, opened, and named segment-directory identities before/after
publication. Healthy append must not reread the complete chain.

Use this private phase sequence:

```text
PRECOMMIT -> MANIFEST_REPLACE_IN_PROGRESS
          -> MANIFEST_REPLACED_UNSYNCED -> COMMITTED
```

Set IN_PROGRESS before the atomic replace call. Only the dedicated replace
helper's classified filesystem failure proves a failed replace and resets to
PRECOMMIT. Preserve unclassified/control-flow exceptions and their identity.
Keep UNSYNCED through core fsync and its trailing layout-binding check; mark
COMMITTED and publish next memory only after both succeed. A late binding loss
also sets sticky COMMIT_OUTCOME_UNKNOWN: it must not be downgraded by a generic
COMMITTED cleanup handler. Raise the sanitized indeterminate subtype for a
classified binding failure; do not publish/repair snapshot, unlink owned temps,
retry, or compensate after discovering unknown authority. Precommit binding
failure instead sets UNAVAILABLE and leaves the old manifest and published
orphan segments intact.

Snapshot staging accepts an absent `context.json`. Classified postcommit
snapshot/owned-temp failures retain committed success and repair-pending state.
Normal lock/descriptor cleanup failure after a known commit retains success but
makes the instance UNAVAILABLE. Cleanup during exception unwinding must never
replace the original throwable. Legacy rollback proof uses a private bounded-
buffer, no-follow/nonblocking streaming reread of both old files; inability to
prove both hashes means sticky unknown, not successful rollback.

- [ ] Add real directory rename tests at: before locked head read; after head
  read/before segment publication; after segment publication/before manifest;
  immediately before the actual manifest replace; and the equivalent early/late
  core-path replacements. Inspect both detached and currently named directories.
- [ ] Prove precommit rejection writes nothing into the replacement layout;
  post-replace rejection preserves uncertain artifacts and rejects later empty
  and nonempty mutations without I/O.
- [ ] Preserve primary exception identity when snapshot cleanup or lock setup
  cleanup also raises, including KeyboardInterrupt.
- [ ] Keep a process-oracle negative control: intentionally skipping manifest
  core fsync must be detected before snapshot publication. Compare physical
  decoded segments, public replay, requested payload, and a fresh child reopen.

Implementation-refinement evidence: `runs/optimization/OP-13/slice-b-private-seams.md`
and `root-process-tests-review.md`. Historical 73 focused tests and production
pyright pass in `root-cleanup-primary-green.json`. Subsequent directory-generation
review passes in `root-generation-review.md`; six real rename RED cases and the
initial-capture sanitization RED were fixed. The expanded 11-process tests pass
in `root-process-expanded.json`. Short-write/ENOSPC partial-stage cleanup six RED
cases were fixed; the current full Kernel559 and production pyright pass are in
`root-partialstage-kernel.json`. Overall B persistence review remains open. These
are not B closure, full release acceptance, or a performance result.

Later cross-platform evidence: `root-linux-report.md` records126 focused
persistence tests passing on local Linux arm64/Python3.12.13, exact dependency
pins, source/test blob fingerprints and reproduction command. The first Linux
125PASS/1FAIL run is retained: a legacy test's first-stat hook fired during
Python3.12 format detection, before its intended post-read comparison. The
corrected hook targets the fd-relative ledger leaf and asserts EOF first;
production validation and the original failure assertion were not relaxed.
`root-postlinux-mac-gates.json` records571 full Kernel tests and production
pyright passing after that fix. This is not remote CI or Windows verification.
Overall B independent review was interrupted by a service error and has not
issued a final verdict; neither the generation-only PASS nor these test results
waives the independent-review gate. Source remains uncommitted and default
creation remains legacy.

2026-09-05 14:34 CST blocker audit: the independent reviewer remains in a
terminal service-error state and no overall B report exists after three
consecutive goal turns carrying that condition. Safe local follow-through
completed cross-platform and remaining lock tests; the final current-tree
Kernel572/production pyright/diff gate passes in `root-blocker-audit-gates.json`.
The full review cannot be replaced by another repeated test run or author
self-approval. Resume B acceptance only through an available compliant
independent review, resolve its findings, then commit B and proceed to C.
OP-08's pending explicit scope approval remains separate; automatic goal
continuation is not that approval. The full optimization objective is blocked,
not complete, and no package acceptance criterion has been weakened.

**C — compensation and compatibility consumers**

Files: Modify
`packages/capability-agent-kernel/src/capability_agent/application/turns.py`,
`application/runner.py`,
`packages/grid-agent/src/grid_agent/compat/v1_0_1_report.py`;
Test Kernel `test_turns.py`, `test_runner.py`, `test_projector.py`;
grid compatibility/single-run/report and generic-entrypoint tests.

- [ ] First reproduce sidecar deletion under an injected indeterminate append
  for start and submit; record RED. Then split preparation failure from append
  outcome handling. Preserve sidecars on indeterminate/unclassified/control-flow
  outcomes. Use the B/C supplement's concrete health and lexical boundaries;
  safety must survive existing wrapper exception types without Protocol changes.
- [ ] Assert fail/runner paths add no compensating transition, call neither
  `_fail_active_turn` nor `_mark_failed`, and return only sanitized failure
  information. Replay determines commitment; the test must not presume that an
  exception always means rollback.
- [ ] After a real durable commit plus forced snapshot-refresh failure, assert
  primary success, current memory, all referenced sidecars present, and fresh
  replay equality. Ordinary precommit typed errors retain existing rollback tests.
- [ ] Add the narrow public-replay report check with diagnostic-only failure;
  preserve legacy report meaning and no JSONL mirror. Test corrupt segment
  diagnostics do not revoke an otherwise valid primary answer.
- [ ] Run complete application/compatibility and inventory/installed replay
  gates, then independent trust/compensation review and explicit-path commit.
  No Domain Pack source, legacy AnalysisContextStore or stdout schema change.

**D — measurement seams, new default, documentation and acceptance**

Files: Modify `application/workspace.py`, `test_workspace.py`,
`tools/benchmark_optimization.py`, `tools/tests/test_benchmark_optimization.py`,
and only consumer tests tied to physical layout. Update `docs/RUNBOOK.md` and
`docs/architecture/capstone-framework.md` for new-run inspection/recovery;
if shared README facts change, synchronize `README.md` and `README.zh-CN.md`.

- [ ] Instrument real segment/manifest/snapshot staging, separately report each
  and ledger/total sums. Keep old-format counter support for the retained legacy
  fixture. A zero-byte logical entry is not a ledger size and never a write metric.
  Add exact-counter RED/GREEN tests before benchmark changes.
- [ ] Switch only newly created workspaces to the reviewed segmented layout;
  test no data migration, old-format read/append, anti-downgrade, exclusive run
  creation, default generic/single-run/report/installed flow and supported-platform
  error. Run types and focused tests before any long measurement.
- [ ] Freeze source and preserve OP12 baseline report. New measurement output
  must use a distinct path, never overwrite the existing OP12 evidence:

```sh
uv run --project packages/grid-agent pytest packages/capability-agent-kernel/tests/application/test_context_segments.py packages/capability-agent-kernel/tests/application/test_context_store.py -q
uv run --project packages/grid-agent pytest tools/tests/test_benchmark_optimization.py -q
uv run --project packages/grid-agent python tools/benchmark_optimization.py --events 1000 10000 100000 --output runs/optimization/OP-13/benchmarks/report.json
make doctor
make check-release
git diff --check
```

- [ ] The tool also runs/reports the reviewed bounded100/1000 growing-core
  characterization without changing the baseline fixed-state workload. Check
  both fixed-state ledger-only and snapshot-inclusive tenfold ratios <=15.
  Preserve failed scales and exact source/runtime/limits; no extrapolated pass.
- [ ] Independent final storage/recovery/consumer/metric review. Keep unsupported
  Windows, current-run evidence, growing-snapshot cost and helper-only preview
  limitations explicit. Record all gates and commits here before OP13 DONE;
  leave OP08 approval and OP09 dependency visible.
- [ ] Rollback changes only future workspace creation. Retain new-format reader
  for already-created segmented runs; do not delete segments, snapshots, sidecars
  or user evidence to make a rollback appear clean.

**固定格式方向**：新运行采用版本化不可变 transaction segment；每组 append_many 对应一个 segment，含起止 revision、previous/next state hash 和 payload digest。一个原子更新 manifest 指向已提交 segment；snapshot 是可重建投影。旧运行继续旧 reader，不自动迁移。

- [x] 实现前把格式字段、commit point、读者兼容矩阵补入本包执行记录并复审；不改变公共 ContextEvent 的领域语义。
- [ ] 依次实现 segment stage → fsync → publish → directory fsync → 原子 manifest commit → snapshot refresh。manifest 提交前中断不把未引用 segment 纳入已提交前缀，保留 final-name 文件；提交后从 segment 重建 snapshot。以以上详细提交点/异常合同为准。
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

### 开发与交付分层（2026-09-05 用户调整）

开发测试用于控制边界，不逐轮套用交付标准。日常修改运行正常路径、关键合同边界和已发现缺陷的最小回归；阶段收敛运行相关集成、类型和环境检查；生产行为变更在阶段验收执行 AGENTS 规定门禁，交付阶段执行完整兼容、压力及资源验证。保留既有专项证据，不因无关小改重复8/64MiB、超深嵌套或故障组合穷举；仅当对应算法、缓冲或资源生命周期变化使原证据失效时重测。极端用例不得自动演变为新的产品要求或无限扩张当前任务。证据真实性、stdout合同、权威边界、兼容性及用户数据安全不降级。

OP08-B0.4具体裁量：文档存储是单次操作独占且失败即整体废弃的临时库，无局部恢复接口；不要求文档表初始化额外事务。以第二张表创建失败后整个临时目录已清理、调用方流仍打开、无成功输出的聚焦测试验证。B0.3可复用索引自身的既定savepoint合同不变。

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
- Review: kernel_review 规范与质量双PASS；复核 Kernel 对应夹具无需修改，focused2、重复30/30、无遗留 fake 进程。root 在当前工作树另跑 runtime：72 passed / 0.76s。Decision: DONE。
- Next: OP-01 继续，OP-02 仅只读映射，依赖未闭合前不实施。

### OP-01 首版与门禁诊断（2026-09-05）

- Source commits: `884e07d`（准入与侧车）、`678d8d6`（版本化 profile preflight）。实施者报告Kernel395、Domain72、focused及`make validate-application`通过；尚未独立验收。
- `make test` 首次全套诊断：6 failed / 730 passed / 1 Starlette-httpx deprecation warning，96.06s，test-agent退出1使make退出2；后续simulator/Pi目标未执行。运行期间HEAD从884e07d变为678d8d6，此结果只作失败诊断，不能拼接为关闭证据。
- 失败集中于 `packages/grid-agent/tests/application/test_generic_entrypoint.py` 五个报告/提交用例和 `packages/grid-agent/tests/cli/test_run_command.py::test_analysis_generic_uses_the_real_runner_and_pandapower_output_contract`。Terra负责追踪替身契约与生产路径，不降低准入保证；修复后在固定源码重跑完整门禁。
- Sol审查包：`runs/optimization/OP-01/review-678d8d6.diff`；实施报告：`runs/optimization/OP-01/task-report.md`。Decision: RUNNING，未关闭。
- 补充基线：inventory domain目录测试13pass/1fail，已在323dd7d导出源码独立复现，非OP-01回归，纳入OP-05受控测试修复；不宣称inventory门禁全绿。
- 修复提交 `f70d0de` 固定源码：doctor、make test（agent741/simulator165/grid Pi43/Makefile）、test-e2e31、validate（离线/脚本core/full及24/24 coverage）、Kernel400、Domain73、validate-application、test-packages全部exit0。保留Starlette/httpx和pandapower依赖警告，不声称零警告；原始工具输出节选在 `runs/optimization/OP-01/gate-{4638,46839,91956}-f70d0de.json`。
- f70d0de复审仍未关闭：报告期待值须来自durable事件而非FinalizedTurn内存；缺profile/authority须provider前拒绝；静态allowed_refs不能替代当前轮产生/消费；策略输出mode须在profile真实声明集合内。Terra已确认并开始修复，完成后重新固定源码验证；绿门禁不能代替这些明确契约。
