from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from pydantic import JsonValue


@dataclass(frozen=True)
class ToolResultEvent:
    capability: str
    result: Mapping[str, JsonValue]
    evidence_refs: tuple[str, ...]
    ok: bool = True
    error: Mapping[str, JsonValue] | None = None


def contains_all(answer: str, arguments: Mapping[str, object]) -> bool:
    values = arguments.get("values", [])
    return (
        isinstance(values, Sequence)
        and not isinstance(values, (str, bytes, bytearray))
        and all(str(value).casefold() in answer.casefold() for value in values)
    )


def truthful_limitation(answer: str, arguments: Mapping[str, object]) -> bool:
    lowered = answer.casefold()
    return any(term in lowered for term in ("不存在", "未找到", "不支持", "limitation", "not found"))


def declared_fields_match(actual: object, expected: object) -> bool:
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(
            key in actual and declared_fields_match(actual[key], value) for key, value in expected.items()
        )
    if isinstance(expected, list):
        return (
            isinstance(actual, list)
            and len(actual) == len(expected)
            and all(declared_fields_match(actual_item, expected_item) for actual_item, expected_item in zip(actual, expected))
        )
    return actual == expected


def result_matches(event: ToolResultEvent, arguments: Mapping[str, JsonValue]) -> bool:
    return event.ok is True and declared_fields_match(event.result, dict(arguments))


def _typed_fields_match(actual: object, expected: object) -> bool:
    if isinstance(expected, Mapping):
        return isinstance(actual, Mapping) and all(
            key in actual and _typed_fields_match(actual[key], value) for key, value in expected.items()
        )
    if isinstance(expected, list):
        return isinstance(actual, list) and len(actual) == len(expected) and all(
            _typed_fields_match(left, right) for left, right in zip(actual, expected)
        )
    return type(actual) is type(expected) and actual == expected


def _finite_number(value: object) -> int | float:
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        raise ValueError("Tolerance values must be finite JSON numbers")
    return value


def result_matches_with_tolerance(event: ToolResultEvent, arguments: Mapping[str, JsonValue]) -> bool:
    """Match typed fields exactly and finite numbers at explicitly configured paths."""
    if event.ok is not True or set(arguments) != {"matches", "numeric_tolerances"}:
        return False
    matches = arguments["matches"]
    tolerances = arguments["numeric_tolerances"]
    if not isinstance(matches, Mapping) or not _typed_fields_match(event.result, matches):
        return False
    if not isinstance(tolerances, Mapping) or not tolerances:
        return False
    try:
        for path, limits in tolerances.items():
            if (
                not isinstance(path, str)
                or not path
                or not isinstance(limits, Mapping)
                or set(limits) != {"expected", "abs_tol", "rel_tol"}
            ):
                return False
            actual = _finite_number(_path_value(event.result, path))
            expected = _finite_number(limits["expected"])
            absolute = _finite_number(limits["abs_tol"])
            relative = _finite_number(limits["rel_tol"])
            if absolute < 0 or relative < 0 or not math.isclose(actual, expected, abs_tol=absolute, rel_tol=relative):
                return False
    except (KeyError, IndexError, TypeError, ValueError, OverflowError):
        return False
    return True


def error_matches(event: ToolResultEvent, arguments: Mapping[str, JsonValue]) -> bool:
    if event.ok is not False or event.error is None:
        return False
    return declared_fields_match(event.error, dict(arguments))


def result_satisfies(event: ToolResultEvent, arguments: Mapping[str, JsonValue]) -> bool:
    if event.ok is not True:
        return False
    matches = arguments.get("matches", {})
    nonempty_paths = arguments.get("nonempty_paths", [])
    minimums = arguments.get("minimums", {})
    if not isinstance(matches, Mapping) or not declared_fields_match(event.result, dict(matches)):
        return False
    if not isinstance(nonempty_paths, Sequence) or isinstance(nonempty_paths, (str, bytes, bytearray)):
        return False
    if not isinstance(minimums, Mapping):
        return False
    try:
        if any(not _path_value(event.result, str(path)) for path in nonempty_paths):
            return False
        return all(
            _numeric(_path_value(event.result, str(path))) >= _numeric(value)
            for path, value in minimums.items()
        )
    except (KeyError, IndexError, TypeError, ValueError):
        return False


def _numeric(value: object) -> float:
    if not isinstance(value, int | float | str):
        raise TypeError("value is not numeric")
    return float(value)


def topology_branch_endpoints(event: ToolResultEvent, arguments: Mapping[str, JsonValue]) -> bool:
    result = dict(event.result)
    branch = result.get("branch")
    if isinstance(branch, Mapping):
        normalized_branch = dict(branch)
        normalized_branch.setdefault("namespace", "pandapower_index")
        if "identifier" not in normalized_branch and isinstance(normalized_branch.get("name"), str):
            normalized_branch["identifier"] = normalized_branch["name"]
        result["branch"] = normalized_branch
    return event.capability == "topology.branch.endpoints.get" and declared_fields_match(result, dict(arguments))


ORACLES = {
    "contains_all": contains_all,
    "error_matches": error_matches,
    "result_matches": result_matches,
    "result_matches_with_tolerance": result_matches_with_tolerance,
    "result_satisfies": result_satisfies,
    "truthful_limitation": truthful_limitation,
    "topology_branch_endpoints": topology_branch_endpoints,
}


def _path_value(value: object, path: str) -> object:
    current = value
    for component in path.split("."):
        if isinstance(current, Mapping):
            current = current[component]
        elif isinstance(current, Sequence) and not isinstance(current, (str, bytes, bytearray)):
            current = current[int(component)]
        else:
            raise TypeError(component)
    return current
