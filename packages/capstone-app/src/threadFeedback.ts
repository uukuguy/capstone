/** Reader-facing recovery text for bounded service codes; never expose raw exceptions. */
export function commandRejectionCopy(code?: string): string {
  const messages: Record<string, string> = {
    stale_event_seq: '页面状态已变化，本次指令未发送。请等待同步完成后重试，输入内容已保留。',
    context_change_pending: '模型或能力正在切换，请等待完成后再发送。',
    worker_unavailable: '所选模型的服务尚未就绪，请稍后重试或选择其他模型。',
    diagram_limit: '所选模型超过完整拓扑显示容量，请选择目录中可用的模型。',
    diagram_invalid: '所选模型的拓扑数据未通过校验，请选择其他模型。',
    model_unavailable: '所选模型当前不可用，请在模型目录确认名称和可用状态。',
    model_already_active: '此模型已经打开，可以直接继续分析。',
    attempt_active: '上一条指令仍在运行，请等待完成或先取消。',
    run_not_open: '本次会话已关闭，请创建新会话后继续。',
    idempotency_conflict: '本次提交与已有命令冲突，请重新同步后重试。',
  }
  return `${messages[code || ''] || '本次操作未提交。请查看当前会话状态后重试，输入内容已保留。'}${code ? `（诊断代码：${code}）` : ''}`
}

export function attemptFailureCopy(code?: string): string {
  const messages: Record<string, string> = {
    capability_required: '本次回答缺少所需的权威系统校验，未能提交。请查看运行过程后重试本次指令。',
    solver_failed: '计算未能完成。请查看运行过程中的求解器信息，调整计算条件后重试。',
    harness_failed: '执行服务未能完成本次指令。请查看运行过程后重试。',
    answer_required: '本次执行没有生成可提交的回答，请重试本次指令。',
    attempt_lease_unavailable: '执行连接已失效，请重新同步后重试本次指令。',
  }
  return `${messages[code || ''] || '本次指令未完成。请查看运行过程后重试；已完成的历史回答仍保留。'}${code ? `（诊断代码：${code}）` : ''}`
}
