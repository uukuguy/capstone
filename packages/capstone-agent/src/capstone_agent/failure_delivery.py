"""Reader summaries copied from admitted results, without new scientific claims."""

from collections.abc import Mapping, Sequence

from .result_projection import ResultProjection


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
