"""Typed, bounded predicates shared by model and result dataset queries."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class InvalidDatasetPredicate(ValueError):
    """A published filter cannot be applied to its described field type."""


_ORDER_OPERATORS = frozenset({"gt", "gte", "lt", "lte"})
_OPERATORS = _ORDER_OPERATORS | {"eq", "ne", "in"}


def validate_predicates(
    predicates: list[dict[str, Any]], field_types: Mapping[str, str]
) -> None:
    for predicate in predicates:
        field = str(predicate["field"])
        operator = str(predicate["operator"])
        expected = predicate.get("value")
        if operator not in _OPERATORS:
            raise InvalidDatasetPredicate("filter operator is unavailable")
        field_type = field_types[field]
        if operator == "in":
            if not isinstance(expected, list) or any(
                value is not None and not _compatible(field_type, value)
                for value in expected
            ):
                raise InvalidDatasetPredicate("filter value is incompatible with field type")
        elif operator in _ORDER_OPERATORS and (
            field_type == "boolean"
            or not _compatible(field_type, expected)
            or expected is None
        ):
            raise InvalidDatasetPredicate("filter value is incompatible with field type")


def predicate_matches(actual: Any, operator: str, expected: Any) -> bool:
    if operator == "eq":
        return actual == expected
    if operator == "ne":
        return actual != expected
    if operator == "in":
        return actual in expected
    if actual is None:
        return False
    try:
        if operator == "gt":
            return actual > expected
        if operator == "gte":
            return actual >= expected
        if operator == "lt":
            return actual < expected
        if operator == "lte":
            return actual <= expected
    except TypeError:
        raise InvalidDatasetPredicate("filter value is incompatible with field type") from None
    raise InvalidDatasetPredicate("filter operator is unavailable")


def _compatible(field_type: str, value: Any) -> bool:
    if field_type in {"number", "integer"}:
        return type(value) in {int, float}
    if field_type == "boolean":
        return type(value) is bool
    if field_type in {"string", "asset_ref"}:
        return type(value) is str
    return False
