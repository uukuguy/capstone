# 原型电气拓扑来源

`ieee39-recorded-topology.svg`是已有App电气拓扑组件的静态矢量导出，替换Demo2四节点示意图。
它包含IEEE-39模型已记录的39条母线、46条支路（35线路、11变压器）；不是实际企业电网或当前运行状态。

- 数据：[threadModelDiagram.ts](../../packages/capstone-app/src/threadModelDiagram.ts)，记录的gridctl拓扑。
- 绘制：[NetworkView.tsx](../../packages/capstone-app/src/NetworkView.tsx)及其[布局](../../packages/capstone-app/src/networkLayout.ts)。
- 来源版本：dev `f209fb18d7abb122b689e1b1a52c54fa13bf5371`。
- 导出入口：本地App `?thread-fixture=idle-ieee39`，不调用Provider或执行计算。
- 模型修订：`revision:sha256:66e156860a24603a5c61dd710426e64d2d5998ba691ce76909045ee91c58d432`。
- 拓扑指纹：`topology:sha256:3cb32d8170e3b7a189069c3b2ffe2aed09a74ea4959b9d886ac6aa91bd94041d`。

导出保留SVG几何、电气符号、元件title和变压器符号的计算样式，补充xmlns与来源说明，
将初始视窗收至模型范围。原型提供缩放、平移、适配全图和元件悬停名称。
重新导出时必须核对39个母线符号、46个支路组、11个变压器符号和85个元件title，
并进行XML解析与浏览器检查，避免截断或CSS缺失造成图形丢失。

原型候选A/B、负载率、电压与约束演示仍是独立合成数据，不与此拓扑绑定、不向其叠加故障或数值。
正式实现应直接复用NetworkView及真实专业投影，核对模型/场景/结果身份后才能呈现叠加层。
静态导出仅用于当前无构建依赖的设计原型，不作为新的产品拓扑渲染器。
