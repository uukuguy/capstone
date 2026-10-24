"""Bounded private Thread catalog and history projections."""

from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from .application_capacity import limits, require_capacity
from .thread_protocol import EventEnvelope, ThreadProtocolError, ThreadSnapshot


def validate_limit(limit: int, maximum: int) -> None:
    if type(limit) is not int or not 1 <= limit <= maximum:
        raise ThreadProtocolError("page limit is invalid")


def thread_descriptor(snapshot: ThreadSnapshot, *, created_at: str, archived: bool, updated_at: str | None = None) -> dict[str, Any]:
    return {
        "thread_id": snapshot.thread_id,
        "model_id": None if snapshot.active_model_context is None else snapshot.active_model_context.model_id,
        "implementation_family": None if snapshot.active_model_context is None else snapshot.active_model_context.implementation_family,
        "created_at": created_at,
        "updated_at": updated_at or (created_at if snapshot.last_event_seq == 0 else None),
        "archived": archived,
        "last_event_seq": snapshot.last_event_seq,
        **({'session_title': snapshot.session_title.to_document()} if snapshot.session_title else {}),
        **({'session_type': snapshot.session_type} if snapshot.session_type else {}),
        **({'minimum_protocol_version': 2} if snapshot.minimum_protocol_version == 2 else {}),
    }


def thread_list_page(rows: Sequence[Mapping[str, Any]], limit: int) -> dict[str, Any]:
    selected = rows[:limit]
    more = len(rows) > limit
    return {
        "schema": "capstone-thread-list/1", "threads": selected,
        "has_more": more,
        "next_before_thread_id": selected[-1]["thread_id"] if more else None,
    }


def history_cursor(snapshot: ThreadSnapshot, before: int | None) -> int:
    if before is None:
        return snapshot.last_event_seq + 1
    if type(before) is not int or not 1 <= before <= snapshot.last_event_seq + 1:
        raise ThreadProtocolError("history cursor is invalid")
    return before


def history_page(thread_id: str, before: int, events: list[EventEnvelope], limit: int) -> dict[str, Any]:
    """Consume descending eligible events; return a bounded ascending page."""
    selected: list[dict[str, Any]] = []
    size = 1024
    for event in events[:limit]:
        document = event.to_document()
        event_size = len(json.dumps(document, ensure_ascii=False).encode()) + 2
        if size + event_size > limits.event_page_bytes:
            if not selected:
                require_capacity('event_page_bytes', size + event_size, phase='history_page')
            break
        size += event_size
        selected.append(document)
    return {
        "schema": "capstone-thread-history/1", "thread_id": thread_id,
        "before_event_seq": before,
        "next_before_event_seq": selected[-1]["event_seq"] if selected else before,
        "has_more": len(events) > len(selected), "events": list(reversed(selected)),
    }


def network_context_page(snapshot: ThreadSnapshot, events: list[EventEnvelope]) -> dict[str, Any]:
    page = {
        "schema": "capstone-thread-network-events/1", "thread_id": snapshot.thread_id,
        "model_context_id": None if snapshot.active_model_context is None else snapshot.active_model_context.id,
        "events": [event.to_document() for event in sorted(events, key=lambda event: event.event_seq)],
    }
    require_capacity('ui_network_event_items', len(events), phase='network_context')
    require_capacity('event_page_bytes', len(json.dumps(page, ensure_ascii=False).encode()), phase='network_context')
    return page
