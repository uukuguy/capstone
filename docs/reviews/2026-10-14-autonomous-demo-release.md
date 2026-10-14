# cloud-demo 发布记录

## 当前正式基线：dev faa6af9

PR #18已正常合入dev，精确来源`faa6af9b4a6fe567c559d0b68ab1c4e5aa1bd4fe`。候选2b6ae7b与合并提交完整Git树一致；Linux/macOS的PR、完整发布与合并后dev门禁均通过。以下旧版本段落为历史记录。

正式验收标签`demo-20261014-2028-faa6af9`已推送，已核对annotated对象及远端精确解析提交。local-dev、local-demo和cloud-demo同源，cloud-dev24d9a32不变。两demo各完成三个注册案例、九轮执行、报告和证据回放，零Provider调用；原Thread图及Composer实际入口可用。local-demo六个原Thread与事件序号保留，未删除存储卷。

- cloud-demo API部署：6403a72d-a9bf-4a97-af9f-770ba94d12d4；App：6a7f16ed-c90d-490e-8028-a2316c7b3712。
- pandapower：aed302e7-6cf2-4e81-b4dc-661f082f60a1；PyPSA：f30c96c7-7e15-4ada-ad59-9dd280737900；四角色SUCCESS。
- 三后端源码工件：275d02003c100f876ffb2dd9fb7551587efb569a9d67b7c6c85ba98e76619780；云安装工件：621d77adddca25889fb55aefc0131875720afde4e8f034b162a840d08c7e9060，角色间一致。
- local-demo三角色镜像：sha256:3a2d87862325fecc1880f2abe9334cbcb60d4ad8148bd7dc343b5564b1c54d36；运行身份与已验证529文件的local-dev一致，App dirty=false。
- 运行收据保存在忽略的`runs/demo-n1-debug/`：demo-faa6af9-acceptance.json、local-demo-faa6af9-checks.json、faa6af9-runtime-alignment.json、faa6af9-local-demo-alignment.json和faa6af9-validation-equivalence.json。标签创建时报告尚未提交，其注释保留该历史状态；本报告现已由687ba80首次入库，并随PR #19收尾。

此为框架交付及注册回归验收；N−1输入增长、结果引用、收尾延迟、岛屿解释、恢复/驱逐和整体科学验收仍开放。图按钮曾受footer指针拦截，其点击路径不计为通过；旧Thread图恢复检查通过。Pi未部署。上一回滚参考为demo-20261014-0744-bd2a200。

## 历史发布：94349e6

当前状态：cloud-demo 已部署，基本发布检查通过。
验收标签：demo-20261014-0552-94349e6，已推送，指向下述精确源码。

用户明确指定 cloud-demo。cloud-dev 有用户使用，不作为本次验证环境。
误上传的 cloud-dev 构建 40950171、caa4727f 已取消，状态为 REMOVED。
其原 API、App 和两个 worker 的运行版本保留；未修改其配置。

发布源码：94349e6251635f67ce0d9c49eb869d6579499eb2。PR #18 为草稿，尚未合并。
local-dev 已规范重建，三个后端镜像一致：
sha256:493151b6eccb74ad770ae22876d1ce42636206cc2e72066886f7f48bdd4f8be9。

## 配置核对

- 目标项目：a7a503b3-9f48-480d-8090-f063bab3b8db，production 环境。
- 三个后端保留端口 8766、user-trial 阶段和 capstone-workbench-v1 配置。
- App 仅连接 https://capstone-api-production-ec73.up.railway.app。
- 数据库、存储、凭据和历史数据保持原配置。
- 启用 CAPSTONE_AUTONOMOUS_RESEARCH=1。
- 旧缓存配置 4/60 导致启动拒绝。统一为版本化配置的 1024/0；实际缓存仍按内存预算调度。

## 验证依据

首次 make test 有 959 项通过、4 项失败；四项测试夹具问题均修复并单独复验。
不得将首次完整命令记为成功。其余测试目标、228 项模拟器检查、39 项 E2E、
3 项注册 worker 检查及离线 validate 已通过。最终修订有 115 项 App、53 项模型/契约检查通过。

原本地 Thread 中已验证 IEEE-39 明确切换和新 N−1 求解。
计算来源与物理状态提示已加强；这不等于所有科学解释均得到确定性保证。
云端四角色 SUCCESS，API ready。实际浏览器页头为 cloud-demo · v0.1.0 · 94349e6，
对话与基础电网图可显示。部署切换时 SSE 曾断开，页面已显示连接恢复。
三个注册用例共 9 轮执行成功，每个用例的报告和证据回放通过；未调用 Provider。
收据：runs/demo-n1-debug/demo-94349e6-checks.json；浏览器截图与身份日志在同目录。
这是基本发布验收，不是所有真实 LLM 任务或科学解释的全面验收。
容器内完整工件哈希收据未导出；源码身份依据冻结上传目录、部署消息和前端提交号。

## 已部署实例

- API：dbc2db4c-7096-4e31-a761-95f04b008cf1。
- pandapower worker：ea708a2e-82d6-4a47-9327-47e388cbcf2e。
- PyPSA worker：1b24a528-bbd7-4451-bb6c-06ed76b268a6。
- App：68c5d30b-ec2a-4709-a74e-7b9f3d6ed28a。
- 三个后端使用同一冻结源码目录，启动接受同一运行契约 10a77f73e48e。

local-demo 已规范重建94349e6，同源镜像0fe8d2a49d6f，固定15173/18767，保留数据。

## 用户 Thread 恢复缺陷

用户截图中的 thr_f5c1ce9f1f662f398ea8 无法恢复。API快照、目录和历史均可读取。
前端实际加载报图身份冲突：事件1省略可选 disconnections，事件121为[]，
JSON字段顺序也不同；电网几何未变化。
20f8a0e统一空列表，bfb2e83补齐字段顺序无关比较。56项回归及类型检查通过。
修订后的实际投影代码从云端原Thread加载、追平成功；真实内容冲突仍拒绝。
只更新demo App，后端94349e6和数据保持。
App部署623e6ea2-c39a-4d7d-82cb-2a56d459c175已SUCCESS。
原Thread在实际云端页面恢复，历史OPF回答及执行过程显示，页头cloud-demo · v0.1.0 · bfb2e83。
线上收据：runs/demo-n1-debug/demo-bfb2e83-existing-thread.log。
补丁标签demo-20261014-0607-bfb2e83已推送，保留94349e6原发布标签。local-demo bfb2e83规范重建ready，镜像573cba24e7fe，固定15173/18767，保留原数据。

## 回退依据

原验收标签：demo-20261010-1231-ed2524f。
原 API：26571056-7983-42c0-9cae-5764841d7eb7。
原 pandapower worker：c0a0b907-7744-4426-9833-238096cf91f7。
原 PyPSA worker：772d84c0-394b-4204-ab89-28d499719e17。
原 App：7b89d17b-7993-4879-9db9-2755aad07bf5。
