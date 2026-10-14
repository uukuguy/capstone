# Execution node audit

## 2026-10-14: actual fields and controlled reply input

The current local deployment is 73bef5b. API and both workers use image
a778d62e614508c4d98917d0dff6630389ecdf3f86384c4d0acdb04c2d25b4c4.
Ports remain App5173/API8767. Existing Thread data is retained.

The same fresh OPF instruction completed in the original Thread in26.0524seconds.
The GRID tool interval union was3.9393seconds. Four native model responses
completed. Both result queries succeeded. No field error, retry or dataset
describe call occurred. The analysis receipt supplied8actual bus fields and
16line fields. Neither dataset listedname. Full35line and39bus rows,9generator
rows,1external-grid row and admitted evidence were retained.

Receipt:runs/autonomous-live/api-fresh-opf-73bef5b-1791914435/opf-report.json.
Attempt:attempt_074d8d61c507303b. Reply response:10.451seconds,3828characters.
This verifies field delivery and the observed execution. It does not prove a
stable total latency improvement or full scientific acceptance.

A separate reply experiment used the same saved context, model and explicit
reply instruction. The actual requests contained35tools or zero tools.
The input token count fell from43582to26452, about39percent.
With close output lengths of1760and1764tokens, completion took6.120seconds
with tools and6.234seconds without tools. The other two outputs were longer.
There is no measured latency benefit. No tool was executed and no diagnostic
reply was admitted as a business result.

Receipt:runs/autonomous-live/reply-tools-ab-1791914162893/report.json.
The earlier toolChoice-none trial removed tools in both variants and is excluded.
The extra reply-transition implementation remains removed from the live chain.

## Current OPF baseline: f09a0c8

Use the original Thread `thr_98b1c23a7ce472de5dc1` and the same fresh-solve instruction. New-Thread and model-switch probes verify preparation only; they do not replace this performance baseline.

Receipt: `runs/autonomous-live/api-fresh-opf-f09a0c8-1791904606/opf-report.json`. Attempt: `attempt_a7d4049c18e312d6`.

| Source | Task duration | GRID wall-time union | Context acquisition | Reply model response |
| --- | ---: | ---: | ---: | ---: |
| 0494ef7 | 33.799 s | 5.096 s | 5.896 s | 9.838 s |
| f09a0c8 | 28.801 s | 5.384 s | 0.000150 s | 10.445 s |

These intervals overlap. Do not sum them as separate phases. The current reply has 4,523 characters; 3,416 characters are Markdown tables. Its verified result projection also contains 35 line rows and 39 bus rows. This is duplicate table generation, not missing numerical results.

e96bb08 records bounded Provider token counts and first public text latency. e2d7067 declares existing table delivery only for selected bindings with a registered admitted-result projector. The model still reads required source fields and reports conclusions, method, coverage and limits. Full-row narration is reserved for explicit inline or export requests. No question, operation or network selector was added. Both changes await the same OPF live comparison; no speed improvement is claimed yet.

Status: measured on isolated backend `c886953`. This is a chain audit, not scientific acceptance or deployment acceptance.

## Sources

Public records: `.worktrees/autonomous-agent/runs/autonomous-live/overall-regression-c886953-1791869186/*-records.json`.
Private preparation measurements: each attempt's `pi-events.jsonl`, event `application_runtime_preparation`, in the isolated worker. Only stage durations were read; model reasoning and credentials were not exported.

## Sequential execution

All five instructions used Thread `thr_809251f6ce0f943c56dc`, in order, without a reset.

| Instruction | Observed request duration | Context acquisition | Session construction | Tool work and outcome |
| --- | ---: | ---: | ---: | --- |
| Grid overview and available analyses | 26.303 s | 2.993 s | 0.088 s | Three parallel reads finished at 7.054 s; three research updates followed; terminal event at 25.352 s |
| List IEEE-39 buses and lines | 14.940 s | 0.000017 s | 0.049 s | Dataset description and two queries; no calculation |
| Open IEEE-39 and resolve line 11 endpoints | 9.341 s | 0.000017 s | 0.040 s | Context open and endpoint lookup; no calculation |
| AC power flow | 9.482 s | 0.000024 s | 0.043 s | One power flow plus constraint description |
| Reuse power flow and rank three lines | 11.680 s | 0.000010 s | 0.039 s | Ranking and evidence read; no power flow call |

Public relative times start at command acceptance. Request duration also includes submission and polling overhead. A last-tool-to-terminal interval includes answer generation and delivery work; it does not by itself prove exclusive Provider latency.

## Confirmed chain behavior

The context owner reuses prepared context on the four later instructions. It does not repeat the first instruction's approximately three-second preparation. Each instruction constructs a separate Pi session in approximately 40–90 ms. This measurement rules out repeated six-second context preparation for this sequence.

The AC calculation and the next instruction's ranking both reference `result:sha256:df217d95ad6b9096c5afa1c3d91796365a0d8ba01629d0f1e0e9a878977c5cae`. The ranking request explicitly contains this reference. The later instruction did not rerun power flow.

## Overview delay

Business tools completed by 7.054 s. Research update calls ended at 10.417, 13.580 and 16.952 s. The first update used an unadmitted symbolic reference `analysis.catalog`. The second marked a supported claim with no references. The third update succeeded. The task completed; failed submissions remained recorded.

The existing generic research protocol already says simple factual queries do not need a research record. Therefore this is not evidence of a required fixed workflow. The model chose extra state updates and needed two correction turns. Do not admit invented references or remove claim checks to shorten execution.

## Next investigation

## Execution presentation requirement

The user clarified that missing task reasoning progress is the main display defect, not missing duration alone. The accepted design is in discussion D16 and formal design “研究更新与用户展示的节奏”: one existing process area, real tool actions retained, optional current local goal and important observations or method changes tied to actual calls/results. No duplicate timeline, fixed stage cards, mandatory tool grouping, or extra summary-model request. Stage findings must remain distinct from the final answer and preserve revisions.

Current App collects only the latest research snapshot for the evidence panel. `AttemptActivity` renders tool activities without task-level explanations. Therefore stored research state does not yet prove implementation of the designed live task-progress display. Fix this projection gap using actual committed records; do not infer stages from tool names or manufacture retrospective findings.

### Reference investigation

Trace the model-visible capability observation contract and research-tool reference schema. Determine whether a capability catalogue observation has an explicit usable provenance reference, and whether tool feedback exposes the valid references clearly. Inspect the session trace metadata to distinguish model turns from final persistence before changing runtime behavior. Keep this investigation generic; do not add example-specific policy or a keyword router.

Completion timestamp remains derived from the saved terminal event and is displayed next to CAPSTONE. This audit does not change task data or the user's deployment.

## Display truth correction

## Full phase ledger verification on 594e0b4

Receipt: `runs/autonomous-live/api-full-stages-594e0b4-1791892215`.
Attempt: `attempt_ccb74705e3f83575` in the original selected Thread.
Durable task time is 34.030399 seconds. Seven stage records total 34.013 seconds; the remaining 17.4 milliseconds occur between the final timing snapshot and terminal event persistence.
Preparation is 7.819 seconds. Final verification and result assembly is 2.915 seconds. All stages have ended and all observed GRID calls retain their parent stage.
Private preparation metrics locate 6.842753 seconds in capability-context acquisition and 0.052150 seconds in session construction. RPC event handling takes 1.683622 seconds, trace writing 0.324900 seconds, and maximum queue delay 0.076715 seconds. These times overlap with stage intervals.
The previous roughly ten-second unrecorded interval is now covered. This does not certify the scientific correctness of every report. One model action lacks a recorded purpose and retains its technical title.
The actual App shows compact counts/duration, response timing inside details, muted slate tags and same-row batch fold controls. Full expand, full collapse, mixed-state enablement, and refresh persistence were checked. Steps default open for the user's current preview; saved manual choices take priority.

## Fresh OPF timing on de543f2

Receipt: `runs/autonomous-live/api-fresh-opf-de543f2-1791886032/opf-report.json`.
Thread: `thr_98b1c23a7ce472de5dc1`; attempt: `attempt_e25bcaf33f65e511`.
The task completed in 32.592 seconds; HTTP observation took 32.776 seconds.
The recorded `analysis.run` request uses `opf.ac`, flat initialization, and voltage angles. Its tool wall time is 1.456 seconds. This includes the Authority call and return; it is not a direct solver CPU measurement.
All tool intervals together cover 5.009 seconds after parallel overlap is removed. Preparation takes 3.803 seconds; session construction takes 0.045 seconds.
RPC takes 25.982 seconds, with trace writes 0.296 seconds, application event handling 1.132 seconds, and maximum queue lag 0.047 seconds. These measurements overlap with tool intervals and must not be summed as separate task phases.
The last tool ends at 21.113 seconds; final completion follows 11.479 seconds later. This interval still requires separate model-output and finalization boundaries.
The result reads cover 35 lines and 39 buses. Actual solver execution is confirmed. CAPSTONE business-step completion remains unrecorded; the UI must not infer it.

The 42828fe App changes use “执行过程”, count tools separately from business steps, and preserve inline results after topology focus. TypeScript and 138 focused App tests pass. Source changes are distinct from backend deployment.

`cfbc618` changes the timeout-continuation label to the actual wait-budget and session-continuation event. It does not assert method changes or verified result reuse. The focused regression failed before the correction and passed after it; TypeScript passed. Research snapshots can retain prior notes; complete per-note origin remains a backend projection gap when older history is absent. Do not present such snapshots as proven new discoveries.

## Real chain on 0ab6f27

Canonical isolated rebuild completed, API8890 and both workers use `sha256:7e1fbc6a9f12a6270130305085e05ba927b2165716f9cf5bc00c80e20a3c7b85`; ready status passed. Original ports and user data were not changed. Probe95902 completed on Thread `thr_220fe7cca87e2b6209d5`, receipt `runs/autonomous-live/api-three-0ab6f27-1791871301`. Request duration50.588s, terminal48.659s relative to acceptance;13 successful tools. OPF returned12.883s, last result read23.647s. No research update occurred. The real running page showed10 actions in276px (max320px), no body overflow; completion14:02:33. This confirms that task-level progress cannot be created by merely projecting research notes: the main loop did not produce such notes in this task. Keep the missing output visible as a backend gap.
## 2026-10-14 场景图层与连续结果复用

bf7a309三个指令均完整结束：mv双线路断开69.789秒，原Thread IEEE39 OPF39.331秒、N−1 82.739秒（HTTP观察时长）。OPF账本实际37.684秒，工具并集4.6371秒；任务准备5.316秒，回复10.774秒，末尾核验及图层整理5.590秒。末尾读场景几何、拓扑与停运状态，是可进一步去重的结构性开销，不等同求解时间。N−1有一次gen字段min_vm_pu/max_vm_pu查询失败并恢复；正式回复完整报告46场景和未找到满足全部条件的缓解方案，未宣称成功最优解。mv短路缺少ext_grid[0/1].s_sc_max_mva/rx_max，失败原因明确保留；一次研究结论更新缺引用失败未阻断任务。

9dca4ab规范重建ready，同源镜像506a94bba5dd。连续追问复用双断开结果，账本实际28.4153秒，工具并集3.2931秒，未调用任何新潮流/分析求解。图层真实记录21未求解母线、两条断开线路、4分区，App按最新简明方案仅给17/4母线分区着特殊色；核对0母线套圈、2断开符号和对应图例。收据api-scene-island-bf7a309-1791918398、api-scene-ieee39-bf7a309-1791918516、api-scene-reuse-9dca4ab-1791919473。三指令完成不等同全部图层或科学验收完成。

## 2026-10-14 电网图修订实测

aff8319/f18dc4c：Authority投影全部真实断开开关；基础图不依赖计算，闭合开关不加符号。线路/变压器端点和母线联络开关均覆盖。128项模型/契约检查通过；重复开关符号修正后38项NetworkView检查及类型通过。local-dev规范重建ready，API及两worker同镜像972003baa725，固定5173/8767。

原Thread thr_98b1c23a7ce472de5dc1：孤岛图实查6个断开开关、21特殊色母线、19内部支路、8断开元件标签。线路31的开关48位于索引190（Bus117）端，旧图遗漏已修正。闭合开关不加符号，内部孤岛名称不常驻。故障指令70.353秒完整结束；基础状态只读追问33.021秒完整结束。收据api-visible-final-island-aff8319-1791923654、api-visible-switch-aff8319-1791923556。

新N−1只做校核的指令31.077秒完整结束，实际两批analysis.contingency.n_minus_one.run覆盖46场景；2父结果准入并验证关联子结果。图与Authority均为线路26停运、线路23/27/28过载，App有1断开及3过载。收据api-visible-n1-authority-f18dc4c-1791924161。

未通过的行为必须保留：N−1历史只读44.021秒遇unknown_result后读取46份证据，但只准入部分场景，图只显示线路0；不能称其整体图示与报告匹配。“重新N−1+缓解”31.260秒只有历史证据读取和模型派生，没有新的N−1计算，却正式声称重新执行，属于真实性缺陷。收据api-visible-n1-scene-f18dc4c-1791923925、api-visible-n1-fresh-f18dc4c-1791924048。此前孤岛正式回复也曾把电压未求解推断为物理失电。图层修订通过不等于三样例科学验收通过，任务链路的运行来源和回复约束仍需修复。
