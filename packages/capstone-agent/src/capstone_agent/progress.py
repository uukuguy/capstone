"""Bounded operator messages for application-neutral semantic events."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from typing import Any


_SECRET_KEYS = ("key", "token", "secret", "authorization", "password")
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
    compact = " ".join(_redact_text(str(value)).split())
    return compact if len(compact) <= limit else compact[:limit] + "…"


def _redact(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): "[REDACTED]" if any(part in str(key).lower() for part in _SECRET_KEYS)
            else _redact(item)
            for key, item in value.items()
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_redact(item) for item in value]
    if isinstance(value, str):
        return _redact_text(value)
    return value


def _detail(value: object) -> str:
    try:
        return _summary(json.dumps(_redact(value), ensure_ascii=False, allow_nan=False))
    except (TypeError, ValueError):
        return "[unavailable]"


def render_progress(event: Mapping[str, object]) -> str:
    """Present known runtime events; omit unknown or empty events."""

    message = event.get("message")
    if isinstance(message, str) and message.strip():
        return _summary(message, 400)
    kind = event.get("type")
    if kind == "tool_execution_start":
        name = _summary(event.get("toolName", event.get("capability", "unknown")))
        args = event.get("args", event.get("arguments", {}))
        return f"工具开始: {name} 输入: {_detail(args)}"
    if kind == "tool_execution_end":
        name = _summary(event.get("toolName", event.get("capability", "unknown")))
        status = "失败" if event.get("isError") else "完成"
        return f"工具{status}: {name} 输出: {_detail(event.get('result', {}))}"
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
                    return f"模型输出: {_summary(output)}"
    return ""
