# Enterprise resource upload validation

2026-10-18 03:32：真实浏览器在独立企业研究会话上传1,077,936,128字节文件，56%暂停、刷新后重选原文件续传完成；服务端SHA与本地一致，刷新后上下文目录可见资源v1。上传入口已接分片进度/暂停/续传/取消，25项相关测试和类型检查通过。规范重建91d65912478d ready。当前只完成存储与恢复；按资源引用接入隔离执行器及按需分析仍待实现，不计GB分析验收。未提交、未合dev，其他环境不变。

- Session: `thr_35b6fdb2979e66d4c4f6`, created through the real New Session menu.
- Synthetic transfer fixture: `/tmp/capstone-resource-browser-1gib.bin` (binary transfer test, not business data).
- Resource: `resource_781aa31037c2496b97e6a05e023c9983`, version 1.
- Bytes: 1,077,936,128. SHA-256: `c475c1483304d6170450472d482030f64798a90b4fbc1d56cf28260066553ae8`.
- First request received 502 during the local rebuild. The receipt survived reload. The later upload was paused at 56%, then resumed after reload and original-file selection.
- Object store and PostgreSQL use the real local-dev stack. API resource listing returned the same size and SHA. The context panel lists 1028.0 MiB, v1 after reload.
- Browser transfer uses File.slice. Unit tests forbid whole-file arrayBuffer on the resource route, reject mismatched resumed bytes and preserve upload identity after remount.
- API/worker rebuild image: `sha256:91d65912478d72bb33930161c46eac35d38668ead6e4d9f4dbec20dc17866cda`.
- Screenshot: `/tmp/capstone-resource-upload-complete.png`.

## Remaining work

The resource is `unprocessed`. It is not automatically an LLM input or an Authority result. The UI says this explicitly. Immutable resource selection, a scoped acquisition bridge into the isolated executor, bounded processing and source coverage are still required. Do not embed the full file in the existing base64 task request. Do not grant the model storage credentials or arbitrary backend URLs. Keep the small-file analysis path available during migration.
