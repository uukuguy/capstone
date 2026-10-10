"""Bounded, admitted result projections shared by Thread clients."""

from __future__ import annotations

import math
import re
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from typing import Any

from .model_identity import validate_model_id

RESULT_PROJECTION_SCHEMA = "capstone-result-projection/1.0"
MAX_RESULT_PROJECTIONS = 64
# Authorities may namespace their immutable references (for example
# ``pypsa-result:sha256:…``) while keeping the public kind explicit.
_REF = re.compile(r"^(?:[a-z][a-z0-9_-]{0,31}-)?(result|evidence|revision):sha256:[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_.:-]{0,127}$")
_STATUSES = frozenset({"completed", "partial", "unavailable"})
_SEVERITIES = frozenset({"info", "warning", "error"})
_MAX_SUMMARY = 32
_MAX_TABLES = 12
_MAX_COLUMNS = 32
_MAX_ROWS = 128
_MAX_ELEMENTS = 128
_MAX_OVERLAY_VALUES = 256
_MAX_TEXT = 256


def _document(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping) or isinstance(value, (str, bytes, bytearray)):
        raise ValueError(f"{name} must be an object")
    return dict(value)


def _text(value: Any, name: str, *, max_length: int = _MAX_TEXT) -> str:
    if not isinstance(value, str) or not value or len(value) > max_length:
        raise ValueError(f"{name} is invalid")
    return value


def _identifier(value: Any, name: str) -> str:
    text = _text(value, name)
    if _IDENTIFIER.fullmatch(text) is None:
        raise ValueError(f"{name} is invalid")
    return text


def _element_identifier(value: Any, name: str) -> str:
    text = _text(value, name, max_length=128)
    if any(ord(char) < 0x20 for char in text):
        raise ValueError(f"{name} is invalid")
    return text


def _model_identifier(value: Any, name: str) -> str:
    text = _text(value, name)
    try:
        return validate_model_id(text, name=name)
    except ValueError as exc:
        raise ValueError(f"{name} is invalid") from exc


def _ref(value: Any, name: str, *, kind: str | None = None) -> str:
    text = _text(value, name, max_length=256)
    match = _REF.fullmatch(text)
    if match is None or (kind is not None and match.group(1) != kind):
        raise ValueError(f"{name} is invalid")
    return text


def validate_artifact_reference(value: object, *, kind: str) -> str:
    """Validate the same immutable reference grammar as public projections."""
    return _ref(value, f"{kind} reference", kind=kind)


def compact_projection_validation_hint(document: Mapping[str, object]) -> dict[str, object]:
    """Retain only validated presentation targets, not the whole model graph."""
    raw = dict(document)
    hint = raw.pop('_diagram_element_ids', None)
    if hint is None:
        return raw
    if not isinstance(hint, (list, tuple)) or any(not isinstance(item, str) for item in hint):
        raise ValueError('projection target validation hint is invalid')
    projection = ResultProjection.from_document(raw)
    targets = {element.element_id for element in projection.element_refs}
    targets.update(row.element_ref.element_id for table in projection.tables for row in table.rows
                   if row.element_ref is not None)
    if projection.overlay is not None:
        targets.update(value.element_id for value in projection.overlay.values)
    if not targets.issubset(hint):
        raise ValueError('projection target is outside the validated diagram')
    raw['_diagram_element_ids'] = sorted(targets)
    return raw


def _finite(value: Any, name: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return value


def _scalar(value: Any, name: str) -> str | int | float | bool | None:
    if value is None or isinstance(value, (str, bool)):
        if isinstance(value, str) and len(value) > _MAX_TEXT:
            raise ValueError(f"{name} is too long")
        return value
    if isinstance(value, (int, float)):
        return _finite(value, name)
    raise ValueError(f"{name} must be scalar")


@dataclass(frozen=True, slots=True)
class ResultMetric:
    metric_id: str
    label: str
    value: str | int | float | bool | None
    unit: str | None = None
    severity: str | None = None

    @classmethod
    def from_document(cls, value: Any) -> "ResultMetric":
        document = _document(value, "result metric")
        allowed = {"metric_id", "label", "value", "unit", "severity"}
        unknown = set(document) - allowed
        if unknown:
            raise ValueError("result metric has unknown fields")
        required = {"metric_id", "label", "value"}
        if required - set(document):
            raise ValueError("result metric is missing fields")
        severity = document.get("severity")
        if severity is not None and severity not in _SEVERITIES:
            raise ValueError("result metric.severity is invalid")
        return cls(
            metric_id=_identifier(document["metric_id"], "result metric.metric_id"),
            label=_text(document["label"], "result metric.label"),
            value=_scalar(document["value"], "result metric.value"),
            unit=None if document.get("unit") is None else _text(document["unit"], "result metric.unit"),
            severity=severity,
        )

    def to_document(self) -> dict[str, Any]:
        document: dict[str, Any] = {
            "metric_id": self.metric_id, "label": self.label, "value": self.value,
        }
        if self.unit is not None:
            document["unit"] = self.unit
        if self.severity is not None:
            document["severity"] = self.severity
        return document


@dataclass(frozen=True, slots=True)
class ResultElementRef:
    element_kind: str
    element_id: str

    @classmethod
    def from_document(cls, value: Any) -> "ResultElementRef":
        document = _document(value, "result element reference")
        if set(document) != {"element_kind", "element_id"}:
            raise ValueError("result element reference fields are invalid")
        return cls(
            _identifier(document["element_kind"], "result element kind"),
            _element_identifier(document["element_id"], "result element id"),
        )

    def to_document(self) -> dict[str, str]:
        return {"element_kind": self.element_kind, "element_id": self.element_id}


@dataclass(frozen=True, slots=True)
class ResultColumn:
    column_id: str
    label: str
    unit: str | None = None

    @classmethod
    def from_document(cls, value: Any) -> "ResultColumn":
        document = _document(value, "result column")
        if set(document) - {"column_id", "label", "unit"} or {"column_id", "label"} - set(document):
            raise ValueError("result column fields are invalid")
        return cls(
            _identifier(document["column_id"], "result column.column_id"),
            _text(document["label"], "result column.label"),
            None if document.get("unit") is None else _text(document["unit"], "result column.unit"),
        )

    def to_document(self) -> dict[str, str]:
        document = {"column_id": self.column_id, "label": self.label}
        if self.unit is not None:
            document["unit"] = self.unit
        return document


@dataclass(frozen=True, slots=True)
class ResultRow:
    row_id: str
    cells: Mapping[str, str | int | float | bool | None]
    element_ref: ResultElementRef | None = None

    @classmethod
    def from_document(cls, value: Any, *, column_ids: Collection[str]) -> "ResultRow":
        document = _document(value, "result row")
        if set(document) - {"row_id", "cells", "element_ref"} or {"row_id", "cells"} - set(document):
            raise ValueError("result row fields are invalid")
        cells_document = _document(document["cells"], "result row.cells")
        if set(cells_document) - set(column_ids):
            raise ValueError("result row contains an unknown column")
        cells = {key: _scalar(item, f"result row.cells.{key}") for key, item in cells_document.items()}
        element = None if document.get("element_ref") is None else ResultElementRef.from_document(document["element_ref"])
        return cls(_element_identifier(document["row_id"], "result row.row_id"), cells, element)

    def to_document(self) -> dict[str, Any]:
        document: dict[str, Any] = {"row_id": self.row_id, "cells": dict(self.cells)}
        if self.element_ref is not None:
            document["element_ref"] = self.element_ref.to_document()
        return document


@dataclass(frozen=True, slots=True)
class ResultTable:
    table_id: str
    title: str
    columns: tuple[ResultColumn, ...]
    rows: tuple[ResultRow, ...]

    @classmethod
    def from_document(cls, value: Any) -> "ResultTable":
        document = _document(value, "result table")
        if set(document) != {"table_id", "title", "columns", "rows"}:
            raise ValueError("result table fields are invalid")
        raw_columns = document["columns"]
        raw_rows = document["rows"]
        if not isinstance(raw_columns, list) or not raw_columns or len(raw_columns) > _MAX_COLUMNS:
            raise ValueError("result table.columns is invalid")
        if not isinstance(raw_rows, list) or len(raw_rows) > _MAX_ROWS:
            raise ValueError("result table.rows is invalid")
        columns = tuple(ResultColumn.from_document(item) for item in raw_columns)
        column_ids = tuple(column.column_id for column in columns)
        if len(set(column_ids)) != len(column_ids):
            raise ValueError("result table columns contain duplicates")
        rows = tuple(ResultRow.from_document(item, column_ids=column_ids) for item in raw_rows)
        if len({row.row_id for row in rows}) != len(rows):
            raise ValueError("result table rows contain duplicates")
        return cls(_identifier(document["table_id"], "result table.table_id"), _text(document["title"], "result table.title"), columns, rows)

    def to_document(self) -> dict[str, Any]:
        return {
            "table_id": self.table_id, "title": self.title,
            "columns": [column.to_document() for column in self.columns],
            "rows": [row.to_document() for row in self.rows],
        }


@dataclass(frozen=True, slots=True)
class ResultOverlayValue:
    element_id: str
    value: int | float

    @classmethod
    def from_document(cls, value: Any) -> "ResultOverlayValue":
        document = _document(value, "result overlay value")
        if set(document) != {"element_id", "value"}:
            raise ValueError("result overlay value fields are invalid")
        return cls(_element_identifier(document["element_id"], "result overlay element_id"), _finite(document["value"], "result overlay.value"))

    def to_document(self) -> dict[str, Any]:
        return {"element_id": self.element_id, "value": self.value}


@dataclass(frozen=True, slots=True)
class ResultOverlay:
    metric: str
    unit: str
    source_ref: str
    values: tuple[ResultOverlayValue, ...]

    @classmethod
    def from_document(cls, value: Any) -> "ResultOverlay":
        document = _document(value, "result overlay")
        if set(document) != {"metric", "unit", "source_ref", "values"}:
            raise ValueError("result overlay fields are invalid")
        raw_values = document["values"]
        if not isinstance(raw_values, list) or len(raw_values) > _MAX_OVERLAY_VALUES:
            raise ValueError("result overlay.values is invalid")
        values = tuple(ResultOverlayValue.from_document(item) for item in raw_values)
        if len({item.element_id for item in values}) != len(values):
            raise ValueError("result overlay values contain duplicates")
        return cls(_identifier(document["metric"], "result overlay.metric"), _text(document["unit"], "result overlay.unit"), _ref(document["source_ref"], "result overlay.source_ref", kind="result"), values)

    def to_document(self) -> dict[str, Any]:
        return {"metric": self.metric, "unit": self.unit, "source_ref": self.source_ref, "values": [item.to_document() for item in self.values]}


@dataclass(frozen=True, slots=True)
class ResultSource:
    capability_id: str
    domain_pack_id: str
    implementation_family: str

    @classmethod
    def from_document(cls, value: Any) -> "ResultSource":
        document = _document(value, "result source")
        if set(document) != {"capability_id", "domain_pack_id", "implementation_family"}:
            raise ValueError("result source fields are invalid")
        return cls(
            _identifier(document["capability_id"], "result source.capability_id"),
            _identifier(document["domain_pack_id"], "result source.domain_pack_id"),
            _identifier(document["implementation_family"], "result source.implementation_family"),
        )

    def to_document(self) -> dict[str, str]:
        return {"capability_id": self.capability_id, "domain_pack_id": self.domain_pack_id, "implementation_family": self.implementation_family}


@dataclass(frozen=True, slots=True)
class ResultProjection:
    result_id: str
    result_ref: str | None
    evidence_refs: tuple[str, ...]
    thread_id: str
    run_id: str
    turn_id: str
    attempt_id: str
    model_context_id: str
    model_id: str
    model_revision: str
    source: ResultSource
    status: str
    summary: tuple[ResultMetric, ...]
    tables: tuple[ResultTable, ...]
    element_refs: tuple[ResultElementRef, ...]
    overlay: ResultOverlay | None
    unavailable_reason: str | None = None

    @classmethod
    def from_document(cls, value: Any) -> "ResultProjection":
        document = _document(value, "result projection")
        allowed = {"schema", "result_id", "result_ref", "evidence_refs", "thread_id", "run_id", "turn_id", "attempt_id", "model_context_id", "model_id", "model_revision", "source", "status", "summary", "tables", "element_refs", "overlay", "unavailable_reason"}
        if set(document) - allowed or not {"schema", "result_id", "result_ref", "evidence_refs", "thread_id", "run_id", "turn_id", "attempt_id", "model_context_id", "model_id", "model_revision", "source", "status", "summary", "tables", "element_refs", "overlay"} <= set(document):
            raise ValueError("result projection fields are invalid")
        if document["schema"] != RESULT_PROJECTION_SCHEMA:
            raise ValueError("result projection schema is invalid")
        status = _text(document["status"], "result projection.status")
        if status not in _STATUSES:
            raise ValueError("result projection.status is invalid")
        raw_summary, raw_tables, raw_elements = document["summary"], document["tables"], document["element_refs"]
        if not isinstance(raw_summary, list) or len(raw_summary) > _MAX_SUMMARY:
            raise ValueError("result projection.summary is invalid")
        if not isinstance(raw_tables, list) or len(raw_tables) > _MAX_TABLES:
            raise ValueError("result projection.tables is invalid")
        if not isinstance(raw_elements, list) or len(raw_elements) > _MAX_ELEMENTS:
            raise ValueError("result projection.element_refs is invalid")
        summary = tuple(ResultMetric.from_document(item) for item in raw_summary)
        if len({item.metric_id for item in summary}) != len(summary):
            raise ValueError("result projection summary contains duplicates")
        tables = tuple(ResultTable.from_document(item) for item in raw_tables)
        if len({item.table_id for item in tables}) != len(tables):
            raise ValueError("result projection tables contain duplicates")
        elements = tuple(ResultElementRef.from_document(item) for item in raw_elements)
        if len({(item.element_kind, item.element_id) for item in elements}) != len(elements):
            raise ValueError("result projection element_refs contain duplicates")
        result_ref = None if document["result_ref"] is None else _ref(document["result_ref"], "result projection.result_ref", kind="result")
        raw_evidence_refs = document["evidence_refs"]
        if not isinstance(raw_evidence_refs, list) or len(raw_evidence_refs) > _MAX_ELEMENTS:
            raise ValueError("result projection.evidence_refs is invalid")
        evidence_refs = tuple(_ref(item, "result projection.evidence_refs", kind="evidence") for item in raw_evidence_refs)
        if status in {"completed", "partial"} and (result_ref is None or not evidence_refs):
            raise ValueError("available result projection requires result and evidence references")
        reason = document.get("unavailable_reason")
        if reason is not None:
            reason = _text(reason, "result projection.unavailable_reason")
        if status == "unavailable" and not reason:
            raise ValueError("unavailable result projection requires a reason")
        if status == "completed" and reason is not None:
            raise ValueError("completed result projection cannot have an unavailable reason")
        if status == "unavailable" and (summary or tables or elements or document["overlay"] is not None):
            raise ValueError("unavailable result projection cannot contain result data")
        overlay = None if document["overlay"] is None else ResultOverlay.from_document(document["overlay"])
        return cls(
            _identifier(document["result_id"], "result projection.result_id"), result_ref, evidence_refs,
            _identifier(document["thread_id"], "result projection.thread_id"), _identifier(document["run_id"], "result projection.run_id"),
            _identifier(document["turn_id"], "result projection.turn_id"), _identifier(document["attempt_id"], "result projection.attempt_id"),
            _identifier(document["model_context_id"], "result projection.model_context_id"), _model_identifier(document["model_id"], "result projection.model_id"),
            _ref(document["model_revision"], "result projection.model_revision", kind="revision"), ResultSource.from_document(document["source"]), status,
            summary, tables, elements, overlay, reason,
        )

    def to_document(self) -> dict[str, Any]:
        document: dict[str, Any] = {
            "schema": RESULT_PROJECTION_SCHEMA, "result_id": self.result_id, "result_ref": self.result_ref,
            "evidence_refs": list(self.evidence_refs), "thread_id": self.thread_id, "run_id": self.run_id,
            "turn_id": self.turn_id, "attempt_id": self.attempt_id, "model_context_id": self.model_context_id,
            "model_id": self.model_id, "model_revision": self.model_revision, "source": self.source.to_document(),
            "status": self.status, "summary": [item.to_document() for item in self.summary],
            "tables": [item.to_document() for item in self.tables], "element_refs": [item.to_document() for item in self.element_refs],
            "overlay": None if self.overlay is None else self.overlay.to_document(),
        }
        if self.unavailable_reason is not None:
            document["unavailable_reason"] = self.unavailable_reason
        return document


def normalize_result_projection(
    value: Any,
    *,
    admitted_refs: Collection[str],
    diagram_ids: Collection[str] | None = None,
    expected_model_revision: str | None = None,
) -> dict[str, Any]:
    """Validate a projection against current-run refs and optional diagram identity."""

    projection = ResultProjection.from_document(value)
    admitted = set(admitted_refs)
    refs = (() if projection.result_ref is None else (projection.result_ref,)) + projection.evidence_refs
    if any(reference not in admitted for reference in refs):
        raise ValueError("result projection contains a reference that is not admitted")
    if expected_model_revision is not None and projection.model_revision != expected_model_revision:
        raise ValueError("result projection model revision does not match the active diagram")
    known_ids = None if diagram_ids is None else set(diagram_ids)
    elements = {(item.element_kind, item.element_id) for item in projection.element_refs}
    for table in projection.tables:
        for row in table.rows:
            if row.element_ref is not None:
                elements.add((row.element_ref.element_kind, row.element_ref.element_id))
    if known_ids is not None and any(element_id not in known_ids for _, element_id in elements):
        raise ValueError("result projection references an unknown diagram element")
    if projection.overlay is not None:
        if projection.overlay.source_ref not in admitted:
            raise ValueError("result projection overlay source is not admitted")
        if known_ids is not None and any(item.element_id not in known_ids for item in projection.overlay.values):
            raise ValueError("result projection overlay references an unknown diagram element")
    return projection.to_document()
