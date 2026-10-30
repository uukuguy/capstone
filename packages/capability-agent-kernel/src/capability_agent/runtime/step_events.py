"""Dependency-free projection shared by full and isolated native transports."""
from collections.abc import Mapping
from typing import Any
import re

def project_runtime_action(event: Mapping[str, Any]) -> dict[str, Any] | None:
    """Project native turn boundaries without exposing messages or private reasoning."""
    kind = event.get('type')
    if kind in {'auto_retry_start', 'auto_retry_end'}:
        attempt = event.get('attempt')
        if type(attempt) is not int or not 1 <= attempt <= 16:
            return None
        value: dict[str, Any] = {'type': 'runtime_action', 'phase': 'retry_started' if kind == 'auto_retry_start' else 'retry_completed', 'retry_attempt': attempt}
        if kind == 'auto_retry_start':
            maximum, delay = event.get('maxAttempts'), event.get('delayMs')
            if type(maximum) is not int or not attempt <= maximum <= 16 or not isinstance(delay, (int, float)) or isinstance(delay, bool) or not 0 <= delay <= 3_600_000:
                return None
            value.update(retry_maximum=maximum, retry_delay_ms=delay)
        elif type(event.get('success')) is bool:
            value['retry_success'] = event['success']
        return value
    if event.get("type") in {"turn_start", "turn_end"}:
        return {"type": "runtime_action", "phase": "started" if event["type"] == "turn_start" else "completed"}
    if event.get("type") == "message_end":
        message = event.get("message")
        if isinstance(message, dict) and message.get("role") == "assistant":
            content = message.get("content")
            tools = isinstance(content, list) and any(isinstance(item, dict) and item.get("type") == "toolCall" for item in content)
            response: dict[str, Any] = {"type": "runtime_action", "phase": "response_completed", "response_kind": "tools" if tools else "text"}
            if message.get('stopReason') in {'error', 'aborted'}:
                response['response_kind'] = 'error'
                code = message.get('errorCode')
                if isinstance(code, str) and re.fullmatch(r'[a-z][a-z0-9_]{0,127}', code):
                    response['error_code'] = code
                status = message.get('errorStatus')
                if type(status) is int and 400 <= status <= 599:
                    response['error_status'] = status
            usage = message.get('usage')
            if isinstance(usage, dict):
                counts = {key: usage[key] for key in ('input', 'output', 'cacheRead', 'cacheWrite', 'totalTokens')
                          if type(usage.get(key)) is int and 0 <= usage[key] <= 100_000_000}
                if counts:
                    response['usage'] = counts
            return response
    return None
