# 事实展示与性能实验

日期：2026-09-22。依据：[深度优化方案](2026-09-22-capstone-deep-optimization-proposal.md) E 阶段。实验均不调用 Provider；测量文件写在 Git 忽略的 `runs/optimization/`，可用下列命令重建。

## 领域事实卡片

Pandapower presentation 现在仅从与当前模型的 context/revision 一致、状态为 `converged` 的已投影 `analysis.powerflow.ac.run` 计算记录派生 `total_active_loss` 卡片，记录模型 ID、数值、`MW` 单位、context/revision/result/evidence 引用。每次展示最多 20 张；缺少数值、正确单位、引用、收敛状态或同源条件时省略，避免把旧上下文的结果误标为当前模型。卡片进入领域上下文摘要和领域报告，不改变模型正文、答案准入、Kernel `core` 或 grid 双字段 stdout。定向测试覆盖有效卡片、错误单位/缺失证据、失败状态和旧上下文的省略；领域包 91 项测试通过。

卡片是已投影结果的可核查展示，不是对模型文字语义正确性的保证。报告及评价故障仍不得撤销已提交答案。当前只覆盖一个有明确值和单位的指标；排序、比较基线和条件类断言需要各自的领域合同，不能根据自由文本猜测。

## 真实 authority 重复调用

复现命令：

```sh
uv run --project packages/grid-simulator python tools/benchmark_gridctl_repeat.py --repeats 3 --output runs/optimization/gridctl-repeat-20260922.json
```

每次请求启动独立 `gridctl request` 进程；同一已注册模型先 `context.open`，再以同一 context 和默认选项连续运行三次 `analysis.run`。成功响应必须符合 `grid-capability/1.0` 的关联 ID。下表单位为秒，反映本机该次实验的整次进程墙钟时间，包括进程启动、加载、求解和持久化。

| 模型 | `environment.describe` | `context.open` | 三次分析 | 后两次中位数 | result ref |
| --- | ---: | ---: | --- | ---: | --- |
| `case9` | 0.963 | 1.420 | 1.259 / 1.580 / 1.758 | 1.669 | 三次相同 |
| `ieee39` | 1.035 | 1.768 | 1.467 / 1.478 / 1.329 | 1.404 | 三次相同 |

相同 result ref 证明内容寻址结果稳定，不能证明计算复用。既有 simulator 测试进一步确认相同 `analysis.run` 调用执行了两次求解。该实验没有分离求解与进程启动成本，也没有测得真实任务中重复语义调用的占比；三次样本不足以给出生产延迟分位数。因此暂不增加复用缓存。未来只有在代表性任务中确认重复计算占比及独立求解成本显著时，才按当前 run、context/revision、实际选项和 runtime fingerprint 设计 authority 内复用。

## 上下文与投影基线

复现命令：

```sh
uv run --project packages/grid-agent python tools/benchmark_optimization.py --events 100 1000 --repeats 2 --batch-size 10 --timeout-seconds 120 --output runs/optimization/benchmarks/current-20260922.json
```

两档各两次成功，以下为脚本记录的 p50。该基准使用固定合成状态和逻辑 Python I/O，不能代表业务求解或物理磁盘吞吐。

| 指标 | 100 events | 1000 events |
| --- | ---: | ---: |
| context append 时间 | 0.029 s | 0.550 s |
| context append 累计写入 | 0.825 MB | 78.956 MB |
| 冷投影时间 | 0.016 s | 0.126 s |
| 热投影时间 | 0.010 s | 0.108 s |
| 请求预览时间 | 0.004 s | 0.005 s |

脚本的写入放大决策为 `TRIGGERED`（100→1000 events 累计写入约 98.85 倍），与此前 OP13 动机一致；用户已明确暂缓 OP13，本次不合入隔离 worktree 的未验收改动，也不把小规模合成数据当成新的容量 SLA。UI 浏览器渲染、Provider I/O、报告发布和真实业务任务尚未分段计时；后续若出现实际时延问题，应先补齐这些阶段的同次运行观测。

## 本批验证

主目录 `make doctor`、`make test`、`make test-e2e`（37 项）、`make validate`（24/24）、`make check-types`、`make check-package-boundaries`、`make validate-application`、`make test-packages`、`make test-source-setup` 和 `make test-pi-capture-runtime` 均通过。未调用需凭据且可能计费的 Provider 验证。
