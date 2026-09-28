"""Bounded operator messages for application-neutral semantic events."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence


_REFERENCE = re.compile(r"\b[a-z][a-z0-9_-]*:(?:[a-z0-9_.-]+:)?sha256:[0-9a-f]{64}\b|\b[0-9a-f]{64}\b")
_INPUT_FIELDS = ("model_id", "model", "network", "dataset", "operation", "case_id", "element", "index", "limit")
_RESULT_FIELDS = ("model", "dataset", "operation", "status", "converged", "row_count", "returned_row_count", "total_active_loss")
_SECRET_TEXT = (
    re.compile(r"\bAuthorization\s*:\s*Bearer\s+[^\s,;，；。)）]+", re.IGNORECASE),
    re.compile(
        r"\b(?:access[_ -]?token|refresh[_ -]?token|api[_ -]?key|secret|password)"
        r"\s*[:=]\s*[^\s,;，；。)）]+",
        re.IGNORECASE,
    ),
)


def _redact_text(value: str) -> str:
    for pattern in _SECRET_TEXT:
        value = pattern.sub("[REDACTED]", value)
    return value


def _summary(value: object, limit: int = 200) -> str:
    compact = " ".join(_REFERENCE.sub("[引用]", _redact_text(str(value))).split())
    return compact if len(compact) <= limit else compact[:limit] + "…"


def summarize_answer(value: object, *, has_references: bool = False) -> str:
    """Return a compact reader-facing summary while retaining the full answer."""

    text = " ".join(str(value).split()) if value is not None else ""
    if not text:
        return "本步未返回回答。"
    del has_references  # Kept for protocol compatibility; the summary is answer-based.
    # Models sometimes prepend an English planning sentence before the formal
    # Chinese answer. Drop that narration from the process view only.
    first_cjk = re.search(r"[\u3400-\u9fff]", text)
    if first_cjk is not None and first_cjk.start() > 0:
        prefix = text[: first_cjk.start()].casefold()
        if any(marker in prefix for marker in ("i'll", "i will", "let me", "now", "first")):
            text = text[first_cjk.start() :]
    heading = re.search(r"#{1,6}\s+", text)
    if heading is not None and heading.start() > 0:
        prefix = text[: heading.start()].casefold()
        if any(marker in prefix for marker in ("我先", "先查", "现在", "接下来", "i'll", "i will", "now")):
            text = text[heading.start() :]
    text = re.sub(r"[*_`#]+", "", text)
    text = re.sub(r"\s*[•·]\s*", "；", text).strip(" ；")
    # Tables and long Markdown sections are useful in the report but make a
    # poor timeline summary. Prefer the lead sentence or paragraph instead.
    if "|" in text:
        lead = text.split("|", 1)[0].strip()
        if lead:
            text = lead
    sentence = re.search(r"[。！？.!?](?:\s|$)", text)
    if sentence is not None and sentence.end() <= 160:
        text = text[: sentence.end()]
    return _summary(text, 160)


def _detail(value: object, fields: tuple[str, ...]) -> str:
    if not isinstance(value, Mapping):
        return "已记录"
    details: list[str] = []
    for key in fields:
        item = value.get(key)
        if isinstance(item, bool | int | float) or isinstance(item, str) and item and len(item) <= 64:
            details.append(f"{key}={_summary(item, 64)}")
        elif key == "total_active_loss" and isinstance(item, Mapping):
            amount = item.get("value")
            unit = item.get("unit")
            if isinstance(amount, int | float) and isinstance(unit, str):
                details.append(f"total_active_loss={amount:.4g} {unit}")
        if len(details) == 3:
            break
    counts = value.get("counts")
    if len(details) < 3 and isinstance(counts, Mapping):
        for name, count in counts.items():
            if isinstance(name, str) and re.fullmatch(r"[a-z_]{1,24}", name) and type(count) is int:
                details.append(f"{name}={count}")
            if len(details) == 3:
                break
    return "，".join(details) if details else "已记录"


def render_progress(event: Mapping[str, object]) -> str:
    """Present known runtime events; omit unknown or empty events."""

    message = event.get("message")
    if isinstance(message, str) and message.strip():
        return _summary(message, 400)
    kind = event.get("type")
    if kind == "tool_execution_start":
        name = _summary(event.get("toolName", event.get("capability", "unknown")))
        args = event.get("args", event.get("arguments", {}))
        return f"工具开始: {name} 输入: {_detail(args, _INPUT_FIELDS)}"
    if kind in {"tool_execution_end", "tool_result"}:
        name = _summary(event.get("toolName", event.get("capability", "unknown")))
        status = "失败" if event.get("isError") or event.get("ok") is False else "完成"
        return f"工具{status}: {name} 结果: {_detail(event.get('result', {}), _RESULT_FIELDS)}"
    if kind == "prompt_ack" or kind == "response" and event.get("command") == "prompt":
        return "模型请求已接收" if event.get("success") is not False else "模型请求失败"
    if kind == "assistant_message":
        output = event.get("text")
        if isinstance(output, str) and output.strip():
            return "正在整理本步回答"
    if kind == "application_report_checkpoint":
        return (
            f"报告已刷新（已完成 {event.get('completed_questions', '?')} 题）："
            f"{_summary(event.get('report_path', ''))}"
        )
    if kind == "application_provider_resolved":
        return (
            f"模型已就绪 provider={_summary(event.get('provider', '?'))} "
            f"model={_summary(event.get('model', '?'))}"
        )
    if kind == "application_waiting":
        return "仍在等待模型或工具响应"
    if kind == "auto_retry_start":
        return f"模型请求重试: {_summary(event.get('errorMessage', 'unknown error'))}"
    if kind == "agent_end":
        return "模型执行结束，正在整理结果"
    if kind == "message_end":
        value = event.get("message")
        if isinstance(value, Mapping) and value.get("role") == "assistant":
            content = value.get("content")
            if isinstance(content, Sequence) and not isinstance(content, (str, bytes, bytearray)):
                output = "".join(
                    str(item.get("text", "")) for item in content
                    if isinstance(item, Mapping) and item.get("type") == "text"
                )
                if output:
                    return "正在整理本步回答"
    return ""
