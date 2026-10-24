"""Dependency-free projection shared by full and isolated native transports."""
from collections.abc import Mapping
from typing import Any

def project_runtime_action(event: Mapping[str, Any]) -> dict[str, Any] | None:
    """Project native turn boundaries without exposing messages or private reasoning."""
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
            usage = message.get('usage')
            if isinstance(usage, dict):
                counts = {key: usage[key] for key in ('input', 'output', 'cacheRead', 'cacheWrite', 'totalTokens')
                          if type(usage.get(key)) is int and 0 <= usage[key] <= 100_000_000}
                if counts:
                    response['usage'] = counts
            return response
    return None
