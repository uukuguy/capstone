# Live Session Checkpoint

> Updated: 2026-09-05 08:46 CST. **Session remains active — not a final handoff.**

## Execution state

- Persistent goal active: 完成 OP01–14，route direct。唯一账本 docs/superpowers/plans/2026-09-05-capstone-optimization.md。实施worktree .worktrees/capstone-optimization，branch feat/capstone-optimization。
- OP01–06 DONE。最新生产提交41b48d0，固定make doctor && make check-release完整exit0，OP06/gate-release-41b48d0.json；全release会话94595已结束，勿重轮询/重跑。源码不再修改，当前仅状态闭合文档dirty待commit。
- OP07 RUNNING，HEAD 180aab6；缓存/轻量列表/基准工具未提交。设计与公开指纹语义复审PASS。缓存首轮复审发现6项缺口及派生cache路径symlink写入run风险，正在修复与补齐回归；不得按局部测试数关闭。

## Immediate next actions

最新覆盖：OP07全部实现与独立复审PASS（final-cache-approval.md），已VERIFYING。dirfd根/叶/文件no-follow、FIFO非阻塞拒绝、坏prefix不写cache均有回归；最后materialize14通过，此前轨迹293/类型零错误，Make验证目标18通过。root补齐真实输入11例与HTTP游标2例。三规模benchmark-final.json exit0，热读五build+write全0，100k冷14.1877/热11.7483秒；不是O(1)/生产性能。立即显式暂存任务路径提交，然后固定HEAD跑make doctor && make check-release，完整通过后关闭OP07并启动OP08。下方旧修复派工已完成，勿重复派发；所有旧focused/benchmark会话均已结束，无活动长命令。

1. public source_fingerprint设计已独立PASS并写plan：projected-source/2.0 digest用同一typedprefix+actualmetadata+verifieddependencies，cursor随任一投影输入变化失效；cache identity另外加入resolvedrunroot+projector schema。wire不改，不扩Kernelreader，必须补cursor回归。
2. op02_single_run仅负责materialize.py/test_materialize.py最后TOCTOU修复：检查后路径被换symlink仍能写run，需held dirfd/no-follow创建/读/原子写与注入回归。前六项复审已关闭；cache-fix-review.md仍REQUEST CHANGES，必须修复后复审，不能绕过。
3. root已补test_cache_inputs.py 9例真实工件tamper/delete/negative→present、manifest/三descriptor、payload-only context依赖parity、hot eagerverify；api/test_projection_pages.py 2例真实501事件HTTP分页hot/事件追加或manifest变化409。独立复审均PASS。catalog缺失status→unknown修复后13通过。轨迹整套287通过，make check-types零错误；Starlette与pyright版本提示保留。make test-verification-targets18通过，benchmark已复审但正式三规模未跑。root删除无调用旧_metadata_identity_inputs辅助函数，尚待后续门禁。
4. OP07 benchmark1k/10k/100k与完整门禁仍未执行；不得宣称cache已加速。OP08等依赖按唯一plan推进，OP13需OP12数据触发，C2延后。

## OP07 design anchors

- runs/optimization/OP-07/read-only-map.md、implementation-decisions.md、design-review.md（ignored evidence，核心决定须复制到versioned plan）。
- 实际artifact依赖：所有event.refs produced/consumed/evidence并集 + 仅context.projected/context.injected的typed payload.artifact_ref。没有任意payload路径读取；sharedcollector需parity测试对照projector实际I/O。记录verified/unavailable状态与negative→present变化。
- 缓存hit eager reverify实际依赖，端点仍current安全验证；缓存不作authority。typedprefix失败时先不缓存，只返回当前诊断；metadata固定安全发现集含缺失状态。
- RunSummary字段不扩，unknown/corrupt与nullable replay extent表达状态；list不调用open_run或任何业务/context/artifact/core projector。cache根必须在run外强制保证，单flight清理idle锁，写失败不阻断正确读结果。
- 保留现有currentrun/pointer/symlink验证，不借性能优化扩大证据准入。无Kernel领域逻辑。

## OP06 closure evidence

- 41b48d0 fullrelease: agent749/sim165/Kernel438/pandapower79/inventory11/13/1/Pi34/43/workbench128/selftests16/SDK4cases/E2E31/24-24/application/六wheel两npm/frozen源码全部通过；doctor/types/boundaries/protectedpaths通过。
- Pi0.84.4 source b79e4cc834970cca69daebffab7df1da7d1e52c4，patch64c2ce9b8b0bc1d83b4c82ed06a5e715624b4e836b5f735b8983fa0f67d9c116，patchset410f8f797d93da650e5a1a97f9331c881036d46bf815981b76475010f484be2d。
- 原exception/0.80.6patch不变；新remediation record binds3actualzeroaudits+currentlocks/graphs+SDKcaptures，独立integrationreviewPASS。实际graph391/226/227；审计依赖数不同（workspace/root计数）不表示遗漏。
- installer先checkout旧patch阻断，后保留整dirtysource再freshclone；真实Git34tests+真实安装成功。旧source保留 .grid-agent/runtime/pi/source-preserved-e75b4119c3bc411b835e686d0307786f，不删。
- runtime SDK smoke真实sdk/extensions，仅fake传输，PI_OFFLINE+tmpauth；generic/grid success9/failure5 assertions。所有旧install/测试session均结束。
- 本地Darwinarm64/Python3.14.3/Node23.11.0；包安装另Python3.12.12。未声称远端CI全矩阵通过，无付费provider。

## Durable boundaries

- main用户未跟踪2026-08-31-capstone-framework-guide.md不动；不push/main合并，不删var/auth。受保护路径修改需独立review和单独digest提交，但OP06未改受保护目录。
- Kernel中立、Domain策略、authority事实；stdout两字段，谱系≠自由文本数值验证。默认securitygate offline，未来advisory需显式可信audit，原例外期限不延期。
