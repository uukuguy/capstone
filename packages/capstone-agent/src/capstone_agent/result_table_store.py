"""Immutable private table pages shared by the API and worker processes."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from typing import Any

from .artifacts import MAX_ARTIFACT_BYTES, ObjectStore
from .result_projection import ResultProjection, ResultTable


class ResultTableStore:
    def __init__(self, objects: ObjectStore) -> None:
        self._objects = objects

    @staticmethod
    def _grant(projection: ResultProjection, table_id: str) -> dict[str, str]:
        if projection.result_ref is None or not any(t.table_id == table_id for t in projection.tables):
            raise ValueError("result table is not in the task grant")
        return {"thread_id": projection.thread_id, "run_id": projection.run_id,
                "turn_id": projection.turn_id, "attempt_id": projection.attempt_id,
                "result_id": projection.result_id, "result_ref": projection.result_ref,
                "model_context_id": projection.model_context_id, "model_id": projection.model_id,
                "model_revision": projection.model_revision, "table_id": table_id}

    def _save(self, kind: str, document: Mapping[str, Any]) -> str:
        content = json.dumps(document, sort_keys=True, ensure_ascii=False,
                             allow_nan=False, separators=(",", ":")).encode()
        if len(content) > MAX_ARTIFACT_BYTES:
            raise ValueError("result table object exceeds byte limit")
        digest = hashlib.sha256(content).hexdigest()
        self._objects.put(f"thread-result-tables/{kind}/{digest}", content, "application/json")
        return f"{kind}:sha256:{digest}"

    def _load(self, kind: str, reference: str) -> dict[str, Any]:
        match = re.fullmatch(re.escape(kind) + r":sha256:([a-f0-9]{64})", reference)
        if match is None:
            raise ValueError("result table reference is invalid")
        digest = match[1]
        content = self._objects.get(f"thread-result-tables/{kind}/{digest}", MAX_ARTIFACT_BYTES)
        if len(content) > MAX_ARTIFACT_BYTES or hashlib.sha256(content).hexdigest() != digest:
            raise ValueError("result table integrity check failed")
        document = json.loads(content)
        if not isinstance(document, dict):
            raise ValueError("result table object is invalid")
        return document

    def publish(self, projection: ResultProjection, table_id: str,
                pages: Iterable[Mapping[str, Any]]) -> str:
        """Publish the manifest last; an incomplete write grants no table."""
        grant = self._grant(projection, table_id)
        original = next(t for t in projection.tables if t.table_id == table_id)
        cursor = 0
        total = None
        closed = False
        references = []
        row_ids: set[str] = set()
        source_context = None
        for source in pages:
            if closed or source.get("result_ref") != projection.result_ref or source.get("revision_ref") != projection.model_revision:
                raise ValueError("result table source identity does not match its grant")
            if type(source.get("offset")) is not int or source["offset"] != cursor:
                raise ValueError("result table pages are not contiguous")
            count = source.get("total_rows")
            if type(count) is not int or count < 0 or (total is not None and total != count):
                raise ValueError("result table row count is inconsistent")
            total = count
            table = ResultTable.from_document(source.get("table"))
            if table.table_id != table_id or table.columns != original.columns or table.title != original.title:
                raise ValueError("result table columns or identity changed")
            ids = {r.row_id for r in table.rows}
            if ids & row_ids:
                raise ValueError("result table row identity is duplicated")
            row_ids.update(ids)
            end = cursor + len(table.rows)
            expected_next = end if end < total else None
            if end > total or (end == cursor and total != 0) or source.get("next_offset") != expected_next:
                raise ValueError("result table cursor does not match its rows")
            context = source.get("context_ref")
            if not isinstance(context, str) or not re.fullmatch(r"context:sha256:[a-f0-9]{64}", context):
                raise ValueError("result table source context is invalid")
            if source_context is not None and context != source_context:
                raise ValueError("result table source context changed between pages")
            source_context = context
            page = {"schema": "capstone-result-table-page/1", "grant": grant,
                    "table": table.to_document(), "total_rows": total, "offset": cursor,
                    "next_offset": expected_next, "context_ref": context}
            reference = self._save("table-page", page)
            references.append({"offset": cursor, "reference": reference})
            cursor = end
            closed = expected_next is None
        if not closed or total is None or cursor != total:
            raise ValueError("result table pages are incomplete")
        return self._save("table-manifest", {"schema": "capstone-result-table-manifest/1",
            "grant": grant, "total_rows": total, "pages": references})

    def read(self, projection: ResultProjection, table_id: str, manifest_ref: str, *,
             offset: int = 0) -> dict[str, Any]:
        if type(offset) is not int or offset < 0:
            raise ValueError("result table cursor is invalid")
        grant = self._grant(projection, table_id)
        manifest = self._load("table-manifest", manifest_ref)
        if manifest.get("schema") != "capstone-result-table-manifest/1" or manifest.get("grant") != grant:
            raise ValueError("result table manifest identity does not match its grant")
        entry = next((p for p in manifest["pages"] if p["offset"] == offset), None)
        if entry is None:
            raise ValueError("result table cursor is unavailable")
        page = self._load("table-page", entry["reference"])
        if page.get("schema") != "capstone-result-table-page/1" or page.get("grant") != grant:
            raise ValueError("result table page identity does not match its grant")
        return page
