# 输入工具条与指令附件：本机验证

实现提交：`df12507d`。本机验证，尚未声称 dev 集成或云端发布。

- 265项受影响的App测试通过，9.16秒；TypeScript、diff检查通过。
- 待确认命令的DR选择往返测试先失败后修复；true/false均可恢复。
- 开关成功发送后恢复off，下一指令为false；未确认发送保留原选择和草稿。
- 规范重建、API/worker身份、就绪、Vite可用性检查通过。
  镜像 `sha256:d21a37d02184598f4d257917e84057de33cd61a7c79ded489db51fa037c2f986`。
  日志 `/tmp/capstone-composer-refinement-rebuild.log`；范围清理记录
  `.capstone-agent/cache-maintenance-20261028-004958-41472.log`。
- 在Vivaldi现有标签新建会话，实际检查顺序为“深度思考、模型、上传资料、设置”，
  无“技能”“上下文”按钮；分别查看了off暗色、on高亮，恢复off。
- 通过原生文件选择器上传176字节的界面测试Markdown，卡片先在待发送区。
  提交后在所属指令内显示文件名、大小、版本；刷新后元数据恢复，待发送区为空。
  文件卡片仅用资源目录元数据，不把文件体放入对话渲染数据。
- 会话 `thr_f6bf974c950fe9fae398`：
  `attempt_2ba69af2b862e3cf` 在00:57:40.824—00:57:44.351完成，3.527秒；
  实际读取附件并正确回答“附件归属界面测试”，模式false，附件引用1项。
  `attempt_cb14906b05121173` 在01:00:19.899—01:00:22.173完成，2.273秒；
  无新附件，实际提交attachment_refs=[]、模式false，回答“收到”。旧附件未被挂到新指令。
- 截图/AX证据：忽略目录 `runs/composer-refinement-20261028/vivaldi/`，
  `toggle-on`、`toggle-off`、`restored`、`final`各一组。

附件卡片依赖有权限的资源目录；加载期间或目录不可用时显示元数据暂不可用，
不伪造文件名。保留历史与斜杠契约；未删除用户文件、对话或旧模式选择。
此前两次迎峰度夏对照的报告和产物未改动，见
[对照分析](2026-10-27-summer-lightweight-dr-comparison.md)。
