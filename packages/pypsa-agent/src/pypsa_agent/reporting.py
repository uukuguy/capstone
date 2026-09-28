"""Reader-facing report shell for the PyPSA application.

The application owns the report presentation.  Domain records remain opaque;
this shell only renders the lifecycle and tool records already admitted by the
Kernel, so PyPSA and pandapower use the same reader-facing report shape.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
import re
from typing import Any

from capability_agent.application.answer_format import format_report_answer
from capability_agent.application.reporting import extract_tool_failures, format_tool_failure


_REFERENCE = re.compile(r"(?:[a-z][a-z0-9-]*):sha256:[0-9a-f]{16,64}")


class PyPSAApplicationReportShell:
    """Render a formal, per-turn application report for PyPSA runs."""

    def render(
        self,
        *,
        questions: Iterable[str] = (),
        answers: Iterable[str] = (),
        assurances: Iterable[str] = (),
        trajectories: Iterable[str] = (),
        references: Iterable[str] = (),
        context: object | None = None,
        presentation: object | None = None,
        core: Mapping[str, object] | None = None,
        domains: Mapping[str, object] | None = None,
        runtime: Mapping[str, object] | None = None,
        **_: object,
    ) -> str:
        del presentation, domains
        question_values = _text_values(questions)
        answer_values = _text_values(answers)
        assurance_values = _text_values(assurances)
        reference_values = _text_values(references)
        core_values = core if isinstance(core, Mapping) else {}
        context_core = getattr(context, "core", None)
        turns = _mapping_values(getattr(context_core, "turns", ()))
        diagnostics = _mapping_values(getattr(context_core, "diagnostics", ()))
        run_id = _text(getattr(context, "run_id", None), _text(core_values.get("run_id"), "run"))
        runtime_values = _runtime_values(runtime, context_core)
        status = _text(
            runtime_values.get("report_status"),
            _text(getattr(context, "status", None), _text(core_values.get("status"), "completed")),
        )

        completed = sum(
            1 for turn in turns if _text(turn.get("status"), "") == "success"
        )
        lines: list[str] = [
            "# 系统仿真分析报告",
            "",
            f"- 分析编号：`{run_id}`",
            f"- 指令数：{len(question_values)}；已完成：{len(answer_values)}；成功：{completed}；未完成：{max(0, len(question_values) - completed)}",
            "",
            "## 本批次运行环境",
            "",
            f"- provider：`{runtime_values.get('provider', 'configured-provider')}`",
            f"- model：`{runtime_values.get('model', 'configured-model')}`",
            "- 运行协议：`application-context/1.0`",
            f"- 状态：`{status}`",
            "",
        ]
        for index, question in enumerate(question_values, start=1):
            answer = answer_values[index - 1] if index <= len(answer_values) else "模型未返回可接受的最终回答。"
            turn = turns[index - 1] if index <= len(turns) else {}
            turn_id = _text(turn.get("turn_id"), f"{run_id}-t{index:03d}")
            duration = turn.get("duration_seconds")
            status_text = "已完成" if _text(turn.get("status"), "") == "success" else "未完成"
            refs = _string_values(turn.get("result_refs", ())) + _string_values(turn.get("evidence_refs", ()))
            lines.extend(
                [
                    f"## {index}. {_reader_text(question)}",
                    "",
                    "### 回答",
                    "",
                    _formal_answer(answer),
                    "",
                    "### 仿真环境上下文",
                    "",
                    "- 当前运行上下文由应用 Kernel 维护；模型、结果和证据均来自本轮已准入引用。",
                    f"- 本题引用结果/证据：{len(refs)} 项。",
                    "- 执行边界：仅报告已登记能力返回的 PyPSA 结果，不把模型拓扑或线性调度推断为 AC/N-1 结论。",
                    "",
                    "### 智能体分析轨迹",
                    "",
                    *_trajectory_lines(diagnostics, turn_id),
                    "",
                    "### 执行状态与证据",
                    "",
                    f"- 状态：{status_text}",
                    f"- 总时长：{float(duration):.2f} 秒" if isinstance(duration, (int, float)) else "- 总时长：未记录",
                    f"- 回合标识：`{turn_id}`",
                    f"- 本题结果/证据引用：{_refs(refs)}",
                    "- 详细执行轨迹：请查看本运行的 `core/events.jsonl` 与对应回合目录。",
                    "",
                ]
            )
        if trajectories:
            lines.extend(["## 补充轨迹", "", *[f"- {_reader_text(value)}" for value in _text_values(trajectories)], ""])
        lines.extend(
            [
                "## 完整性诊断",
                "",
                f"- 完整上下文与调用轨迹：`core/context.json`、`core/events.jsonl`。",
                f"- 本批次公开引用：{_refs(reference_values)}",
                "",
            ]
        )
        if assurance_values:
            lines.extend(
                [
                    "## 证据评估（仅供参考）",
                    "",
                    "以下评估不改变答案正文、执行状态或完成计数。",
                    "",
                    *[
                        f"- 第 {index} 题：{_assurance_label(value)}"
                        for index, value in enumerate(assurance_values, start=1)
                    ],
                    "",
                ]
            )
        return "\n".join(lines).rstrip() + "\n"


def _text_values(values: Iterable[str]) -> tuple[str, ...]:
    result = tuple(values)
    if any(not isinstance(value, str) for value in result):
        raise TypeError("report values must contain text")
    return result


def _mapping_values(values: object) -> tuple[Mapping[str, object], ...]:
    if not isinstance(values, (tuple, list)):
        return ()
    return tuple(value for value in values if isinstance(value, Mapping))


def _string_values(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if isinstance(value, (tuple, list)):
        return tuple(item for item in value if isinstance(item, str))
    return ()


def _runtime_values(runtime: Mapping[str, object] | None, context_core: object | None) -> dict[str, str]:
    values: dict[str, str] = {}
    if isinstance(context_core, object):
        context_runtime = getattr(context_core, "runtime", {})
        if isinstance(context_runtime, Mapping):
            values.update({str(key): str(value) for key, value in context_runtime.items() if isinstance(value, (str, int, float))})
    if isinstance(runtime, Mapping):
        values.update({str(key): str(value) for key, value in runtime.items() if isinstance(value, (str, int, float))})
    return values


def _trajectory_lines(diagnostics: tuple[Mapping[str, object], ...], turn_id: str) -> list[str]:
    records: list[str] = []
    for item in diagnostics:
        if _text(item.get("turn_id"), "") != turn_id:
            continue
        failures = extract_tool_failures((item,))
        if failures:
            records.append(f"- {format_tool_failure(failures[0])}")
            continue
        if not isinstance(item.get("capability_id"), str) and not isinstance(item.get("tool_name"), str):
            continue
        capability = _text(item.get("capability_id"), _text(item.get("tool_name"), "已发布能力"))
        ok = item.get("ok")
        result = "完成" if ok is True else "未完成" if ok is False else "已记录"
        records.append(f"- 调用已发布能力 `{capability}`（{result}）")
    return records or ["- 未观察到与本题关联的已发布能力调用。"]


def _refs(values: Iterable[str]) -> str:
    refs = tuple(values)
    return "、".join(f"`{value}`" for value in refs) if refs else "无"


def _assurance_label(value: str) -> str:
    return {
        "lineage_verified": "已核验结果及证据来源；不代表回答语义完全正确",
        "guide_access_verified": "已读取发布指南；未核验回答语义及数值",
        "limited": "证据绑定不足，未给予来源保证",
    }.get(value.split(" — ", 1)[0], value)


def _text(value: object, fallback: str) -> str:
    return value if isinstance(value, str) and value else fallback


def _reader_text(value: str) -> str:
    return _REFERENCE.sub("", value).strip()


def _formal_answer(value: str) -> str:
    return format_report_answer(_reader_text(value))


__all__ = ["PyPSAApplicationReportShell"]
