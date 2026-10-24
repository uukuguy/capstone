"""Reader summaries copied from admitted results, without new scientific claims."""

from collections.abc import Mapping, Sequence

from .result_projection import ResultProjection


NATIVE_FAILURE_REASONS = {
    'native_capacity_exceeded': '本轮超过应用配置的容量。具体项目、实际用量和配置上限见失败详情；已生成文件保留。',
    'native_transport_timeout': '执行器连接超时，本轮未能正常收尾。',
    'native_transport_failed': '执行器连接中断，本轮未能正常收尾。',
    'native_executor_http_rejected': '执行器拒绝了系统请求，未能正常收尾；已停止执行并保留已有文件。',
    'native_task_deadline': '本轮达到执行时间上限。',
    'native_deadline_exceeded': '执行等待超过时限。',
    'native_response_too_large': '执行记录超过系统传输容量。',
    'native_event_history_limit': '执行事件数量达到系统上限。',
    'native_event_identity_changed': '执行记录一致性校验未通过。',
    'native_research_response_invalid': '研究记录格式校验未通过。',
    'native_research_source_invalid': '研究资料来源校验未通过。',
    'native_contract_rejected': '执行结果或研究记录的系统校验未通过。',
    'native_receipt_persistence_failed': '执行记录保存失败。',
    'native_artifact_persistence_failed': '执行器已返回，但生成文件未能完整保存，本轮交付尚未完成。',
    'native_execution_error': '系统执行异常，尚未记录到更具体的原因。',
    'native_research_runtime_invalid': '研究流程的状态或配置校验未通过，已保留此前的有效结果。',
    'native_research_branch_invalid': '研究子任务与父任务的状态、问题或审阅权限校验未通过。系统已停止执行，已有文件与记录仍保留；需修复研究执行链路后继续。',
    'native_research_checkpoint_failed': '研究进度保存未获确认，未将本轮标记为完成。已保留现有文件与执行记录。',
    'native_continuation_no_progress': '后续动作未产生新的工具执行或已保存的状态进展，系统已停止重复续跑。本轮未完成交付；此前生成的文件和执行记录仍保留。',
    'native_goal_blocked': '整体任务存在尚未解决的必要输入、权限或执行能力问题，未完成交付。已保存的部分结果和执行记录仍保留；具体缺口见执行过程。',
    'native_runtime_dependency_missing': '执行器加载组件失败：服务环境缺少必需的运行组件。请联系维护人员修复执行器环境后重试；无需修改任务指令或重新上传资料。',
    'native_model_context_limit': '模型可接收的上下文容量不足，本轮未能继续处理。',
    'native_model_rate_limit': '模型服务限制了本轮请求，执行未能完成。',
    'native_model_authentication': '模型服务身份验证失败，需检查应用的服务配置。',
    'native_model_output_invalid': '模型服务返回了无法处理的结果，本轮未能正常收尾。',
    'native_model_output_rejected': '模型服务拒绝了本次回复，本轮未能完成交付。已保留此前的工作记录和文件。',
    'native_model_turn_incomplete': '模型回复未正常结束，本轮尚未完成交付。此前的工作记录和文件仍保留；系统未取得更具体的模型错误原因。',
}


def native_transport_summary(value: object) -> str:
    """Render only registered transport fields, never a server response body."""
    if not isinstance(value, Mapping):
        return ''
    operations = {'task_admission', 'task_status', 'research_bootstrap', 'research_pending', 'research_acknowledge'}
    operations |= {'resource_status', 'resource_part', 'resource_complete'}
    if set(value) == {'operation', 'transport_phase'}:
        phases = {'ReadTimeout', 'WriteTimeout', 'ConnectTimeout', 'PoolTimeout', 'TimeoutError', 'task_deadline'}
        if (isinstance(value['operation'], str) and value['operation'] in operations
                and isinstance(value['transport_phase'], str) and value['transport_phase'] in phases):
            return f" 系统请求：{value['operation']}；等待阶段：{value['transport_phase']}。"
        return ''
    if set(value) != {'operation', 'http_status', 'protocol_code'}:
        return ''
    codes = {'invalid_task', 'task_not_found', 'research_owner_conflict', 'unauthorized',
             'executor_capacity', 'resource_not_found', 'research_transport_file_changed', 'unrecognized_response'}
    if (not isinstance(value['operation'], str) or not isinstance(value['protocol_code'], str)
            or value['operation'] not in operations or value['protocol_code'] not in codes
            or type(value['http_status']) is not int or not 400 <= value['http_status'] <= 599):
        return ''
    return (f" 系统请求：{value['operation']}；HTTP {value['http_status']}；原因：{value['protocol_code']}。")


def _text(value: object) -> str:
    return " ".join(str(value).split()).replace("|", "\\|").replace("<", "&lt;").replace(">", "&gt;")


def retained_result_summary(projections: Sequence[ResultProjection]) -> str:
    if not projections:
        return ""
    lines = ["", "", "已核验的部分结果（各项对应其原计算场景）：", "",
             "| 结果 | 记录状态 | 已保存的数据 |", "| --- | --- | --- |"]
    length = sum(len(line) + 1 for line in lines)
    shown = 0
    statuses = {"completed": "已完成", "partial": "部分结果", "unavailable": "无法展示"}
    for index, projection in enumerate(projections, start=1):
        values = []
        for metric in projection.summary:
            value = ("未提供" if metric.value is None else "是" if metric.value is True
                     else "否" if metric.value is False
                     else format(metric.value, ".6g") if isinstance(metric.value, float)
                     else _text(metric.value))
            unit = "" if metric.unit is None else " " + _text(metric.unit)
            values.append(f"{_text(metric.label)}：{value}{unit}")
        if projection.tables:
            values.append("数据表：" + "、".join(_text(table.title) for table in projection.tables))
        details = "；".join(values) or "未提供摘要指标"
        line = f"| {index} · {_text(projection.model_id)} | {statuses[projection.status]} | {details} |"
        if length + len(line) > 12_000:
            break
        lines.append(line)
        length += len(line) + 1
        shown += 1
    if shown < len(projections):
        lines.extend(["", f"其余 {len(projections) - shown} 项请在计算结果中查看；全部记录仍保留。"])
    lines.extend(["", "以上是已保存的计算观察，不能替代尚未完成的检查或最终业务结论。"])
    return "\n".join(lines)


def recorded_failure_summary(events: Sequence[Mapping[str, object]]) -> str:
    messages: list[str] = []
    for event in events:
        failure = event.get("failure")
        if event.get("ok") is not False or not isinstance(failure, Mapping):
            continue
        message = failure.get("message")
        if isinstance(message, str) and message.strip() and message not in messages:
            messages.append(message)
    if not messages:
        return ""
    # These are already redacted public tool observations, never exception text.
    lines = ["", "", "执行中记录的失败（不等于后续重试仍失败）：", ""]
    lines.extend("- " + _text(message) for message in messages[-5:])
    if len(messages) > 5:
        lines.append("其余失败及后续处理请在执行过程中查看。")
    return "\n".join(lines)
