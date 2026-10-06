"""Bounded private Thread catalog and history projections."""

from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from .network_diagram import MAX_EVENT_PAGE_BYTES
from .thread_protocol import EventEnvelope, ThreadProtocolError, ThreadSnapshot


def validate_limit(limit: int, maximum: int) -> None:
    if type(limit) is not int or not 1 <= limit <= maximum:
        raise ThreadProtocolError("page limit is invalid")


def thread_descriptor(snapshot: ThreadSnapshot, *, created_at: str, archived: bool, title: str | None = None) -> dict[str, Any]:
    return {
        "thread_id": snapshot.thread_id,
        "model_id": snapshot.active_model_context.model_id,
        "implementation_family": snapshot.active_model_context.implementation_family,
        "created_at": created_at,
        "archived": archived,
        "last_event_seq": snapshot.last_event_seq,
        "title": title,
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
    if type(before) is not int or not snapshot.base_event_seq < before <= snapshot.last_event_seq + 1:
        raise ThreadProtocolError("history cursor is invalid")
    return before


def history_page(thread_id: str, before: int, events: list[EventEnvelope], limit: int) -> dict[str, Any]:
    """Consume descending eligible events; return a bounded ascending page."""
    selected: list[dict[str, Any]] = []
    size = 1024
    for event in events[:limit]:
        document = event.to_document()
        event_size = len(json.dumps(document, ensure_ascii=False).encode()) + 2
        if size + event_size > MAX_EVENT_PAGE_BYTES:
            if not selected:
                raise ThreadProtocolError("event exceeds the page size limit")
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
        "model_context_id": snapshot.active_model_context.id,
        "events": [event.to_document() for event in sorted(events, key=lambda event: event.event_seq)],
    }
    if len(events) > 4 or len(json.dumps(page, ensure_ascii=False).encode()) > MAX_EVENT_PAGE_BYTES:
        raise ThreadProtocolError("network context projection exceeds its limit")
    return page
