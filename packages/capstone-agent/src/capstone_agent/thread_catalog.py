"""Neutral adapter for Authority-owned model catalog records.

The Capstone application may select a Domain Pack and a registered Authority,
but the Thread protocol must not import either implementation.  This adapter
accepts the small public mapping returned by that selected Authority adapter
and retains only the immutable identity needed by ``ThreadCreator``.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from typing import Any

from .thread_service import ThreadModelDescriptor


_MODEL_ID = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
_REVISION = re.compile(r"^revision:[a-z0-9_-]+:[a-f0-9]{64}$")


class AuthorityThreadModelCatalog:
    """Convert one selected Authority's model record into a safe descriptor.

    ``resolver`` is supplied by the application-selected Authority adapter. It
    may return additional private data, but this boundary copies no such data
    into the Thread snapshot and never exposes the raw record to callers.
    """

    def __init__(self, *, default_model_id: str, resolver: Callable[[str], Mapping[str, Any]]) -> None:
        if not isinstance(default_model_id, str) or not _MODEL_ID.fullmatch(default_model_id):
            raise ValueError("default_model_id is invalid")
        if not callable(resolver):
            raise TypeError("resolver must be callable")
        self.default_model_id = default_model_id
        self._resolver = resolver

    def resolve(self, model_id: str | None) -> ThreadModelDescriptor:
        selected = self.default_model_id if model_id is None else model_id
        if not isinstance(selected, str) or not _MODEL_ID.fullmatch(selected):
            raise ValueError("model_id is invalid")
        record = self._resolver(selected)
        if not isinstance(record, Mapping):
            raise ValueError("Authority model record is invalid")
        resolved_id = record.get("model_id")
        revision = record.get("revision_ref")
        family = record.get("implementation_family", record.get("engine"))
        if resolved_id != selected:
            raise ValueError("Authority model record model_id does not match request")
        if not isinstance(revision, str) or not _REVISION.fullmatch(revision):
            raise ValueError("Authority model record revision_ref is invalid")
        if not isinstance(family, str) or not _MODEL_ID.fullmatch(family):
            raise ValueError("Authority model record implementation family is invalid")
        return ThreadModelDescriptor(
            model_id=resolved_id,
            model_revision=revision,
            implementation_family=family,
        )


__all__ = ["AuthorityThreadModelCatalog"]
