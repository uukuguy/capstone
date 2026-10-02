"""Trusted, bounded application Case definitions."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from collections.abc import Iterable, Mapping
from pathlib import Path


_CATALOG_SCHEMA = "capstone-catalog/1.0"
_MAX_APPLICATIONS = 128
_MAX_CASES_PER_APPLICATION = 128
_MAX_STEPS = 32
_MAX_INSTRUCTION_CHARS = 4096
_MAX_TEXT_CHARS = 4096
_MAX_TITLE_CHARS = 256
_VERSION = re.compile(r"^[0-9]+(?:\.[0-9]+){0,3}(?:[-+][a-z0-9.-]+)?$")


@dataclass(frozen=True, slots=True)
class CaseStepDefinition:
    """One trusted, ordered user instruction in a Case."""

    ordinal: int
    title: str
    instruction: str
    instruction_digest: str


@dataclass(frozen=True, slots=True)
class CaseDefinition:
    """An immutable application-level Case definition."""

    case_id: str
    case_version: str
    case_revision: str
    display_name: str
    description: str
    model_ids: tuple[str, ...]
    steps: tuple[CaseStepDefinition, ...]


class CaseCatalog:
    """Resolve only Cases present in a trusted server-built catalog."""

    def __init__(self, definitions: Iterable[CaseDefinition]) -> None:
        cases: dict[tuple[str, str], CaseDefinition] = {}
        for definition in definitions:
            key = (definition.case_id, definition.case_version)
            if key in cases:
                raise ValueError(f"duplicate case id/version: {definition.case_id}")
            cases[key] = definition
        self._definitions = cases

    @classmethod
    def from_registered_catalog(cls, document: Mapping[str, object]) -> "CaseCatalog":
        """Parse the exact public projection emitted by ``catalog.build_catalog``."""

        document = _mapping(document, name="catalog")
        _fields(document, {"schema", "applications"}, name="catalog")
        if document.get("schema") != _CATALOG_SCHEMA:
            raise ValueError("catalog schema is invalid")
        applications = document.get("applications")
        if not isinstance(applications, list) or not applications:
            raise ValueError("catalog applications are invalid")
        if len(applications) > _MAX_APPLICATIONS:
            raise ValueError("catalog has too many applications")

        trusted = _trusted_catalog_projection()
        trusted_application_values = trusted.get("applications")
        if not isinstance(trusted_application_values, list):
            raise RuntimeError("trusted catalog projection is invalid")
        trusted_applications: dict[str, Mapping[str, object]] = {}
        for raw_trusted_application in trusted_application_values:
            trusted_application = _mapping(
                raw_trusted_application,
                name="trusted catalog application",
            )
            trusted_application_id = trusted_application.get("application_id")
            if not isinstance(trusted_application_id, str):
                raise RuntimeError("trusted catalog application identity is invalid")
            trusted_applications[trusted_application_id] = trusted_application
        definitions: list[CaseDefinition] = []
        seen_applications: set[str] = set()
        for app_index, raw_application in enumerate(applications):
            application = _mapping(raw_application, name=f"catalog.applications[{app_index}]")
            _fields(application, {"application_id", "title", "cases"},
                    name=f"catalog.applications[{app_index}]")
            application_id = _text(
                application.get("application_id"),
                name=f"catalog.applications[{app_index}].application_id",
            )
            if application_id in seen_applications:
                raise ValueError(f"duplicate application id: {application_id}")
            seen_applications.add(application_id)
            trusted_application = trusted_applications.get(application_id)
            if trusted_application is None or application.get("title") != trusted_application.get("title"):
                raise ValueError(
                    f"catalog.applications[{app_index}] is not a registered projection"
                )
            _text(application.get("title"), name=f"catalog.applications[{app_index}].title")
            cases = application.get("cases")
            if not isinstance(cases, list) or not cases or len(cases) > _MAX_CASES_PER_APPLICATION:
                raise ValueError(f"catalog.applications[{app_index}].cases is invalid")
            trusted_case_values = trusted_application.get("cases")
            if not isinstance(trusted_case_values, list):
                raise RuntimeError("trusted catalog cases are invalid")
            trusted_cases: dict[str, Mapping[str, object]] = {}
            for raw_trusted_case in trusted_case_values:
                trusted_case = _mapping(raw_trusted_case, name="trusted catalog case")
                trusted_case_id = trusted_case.get("case_id")
                if not isinstance(trusted_case_id, str):
                    raise RuntimeError("trusted catalog case identity is invalid")
                trusted_cases[trusted_case_id] = trusted_case
            for case_index, raw_case in enumerate(cases):
                case = _mapping(
                    raw_case,
                    name=f"catalog.applications[{app_index}].cases[{case_index}]",
                )
                case_id = case.get("case_id")
                if not isinstance(case_id, str) or case_id not in trusted_cases:
                    raise ValueError(
                        f"catalog.applications[{app_index}].cases[{case_index}] "
                        "is not a registered projection"
                    )
                definition = _case_from_document(
                    case,
                    name=f"catalog.applications[{app_index}].cases[{case_index}]",
                )
                if case != trusted_cases[case_id]:
                    raise ValueError(
                        f"catalog.applications[{app_index}].cases[{case_index}] "
                        "is not a registered projection"
                    )
                definitions.append(definition)
        return cls(definitions)

    def get(self, case_id: str, version: str | None = None) -> CaseDefinition:
        """Return a registered Case or fail closed for an unknown identity."""

        if not isinstance(case_id, str) or not case_id.strip():
            raise LookupError(f"registered case was not found: {case_id}")
        if version is not None and (not isinstance(version, str) or not version.strip()):
            raise LookupError(f"registered case was not found: {case_id}@{version}")
        if version is not None:
            definition = self._definitions.get((case_id, version))
            if definition is None:
                raise LookupError(f"registered case was not found: {case_id}@{version}")
            return definition
        matches: list[CaseDefinition] = [
            definition for (registered_id, _registered_version), definition in self._definitions.items()
            if registered_id == case_id
        ]
        if not matches:
            raise LookupError(f"registered case was not found: {case_id}")
        if len(matches) > 1:
            raise LookupError(f"registered case version is ambiguous: {case_id}")
        return matches[0]


def _case_from_document(value: object, *, name: str) -> CaseDefinition:
    case = _mapping(value, name=name)
    expected_fields = {
        "case_id",
        "case_version",
        "title",
        "summary",
        "model_origin",
        "model_ids",
        "scenario_assumption",
        "interpretation_boundary",
        "step_titles",
        "instructions",
    }
    _fields(case, expected_fields, name=name)
    if set(case) != expected_fields:
        raise ValueError(f"{name} does not match the registered projection")
    case_id = _text(case.get("case_id"), name=f"{name}.case_id", max_chars=256)
    case_version = _text(case.get("case_version"), name=f"{name}.case_version", max_chars=64)
    if _VERSION.fullmatch(case_version) is None:
        raise ValueError(f"{name}.case_version is invalid")
    display_name = _text(case.get("title"), name=f"{name}.title", max_chars=_MAX_TITLE_CHARS)
    description = _text(case.get("summary"), name=f"{name}.summary", max_chars=_MAX_TEXT_CHARS)
    model_ids = _model_ids(case, name=name)

    instructions = case.get("instructions")
    if not isinstance(instructions, list) or not instructions:
        raise ValueError(f"{name}.instructions has invalid step count")
    if len(instructions) > _MAX_STEPS:
        raise ValueError(f"{name}.instructions has too many steps")
    parsed_instructions = [
        _instruction(raw_instruction, name=f"{name}.instructions[{index}]")
        for index, raw_instruction in enumerate(instructions)
    ]
    step_titles = _step_titles(case.get("step_titles"), instructions, name=name)
    steps: list[CaseStepDefinition] = []
    for index, (instruction, embedded_title) in enumerate(parsed_instructions, start=1):
        title = step_titles[index - 1] if step_titles is not None else embedded_title
        if title is None:
            title = _derive_step_title(instruction, ordinal=index)
        digest = hashlib.sha256(instruction.encode("utf-8")).hexdigest()
        steps.append(CaseStepDefinition(index, title, instruction, digest))

    revision_payload = {
        "case_id": case_id,
        "case_version": case_version,
        "model_ids": list(model_ids),
        "steps": [
            {"ordinal": step.ordinal, "title": step.title, "instruction": step.instruction}
            for step in steps
        ],
    }
    revision_bytes = json.dumps(
        revision_payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    case_revision = "case:sha256:" + hashlib.sha256(revision_bytes).hexdigest()
    return CaseDefinition(
        case_id=case_id,
        case_version=case_version,
        case_revision=case_revision,
        display_name=display_name,
        description=description,
        model_ids=model_ids,
        steps=tuple(steps),
    )


def _model_ids(case: Mapping[str, object], *, name: str) -> tuple[str, ...]:
    raw = case.get("model_ids")
    if not isinstance(raw, list) or not raw or len(raw) > 32:
        raise ValueError(f"{name}.model_ids is invalid")
    result: list[str] = []
    for index, value in enumerate(raw):
        model_id = _text(value, name=f"{name}.model_ids[{index}]", max_chars=256)
        if any(char.isspace() for char in model_id):
            raise ValueError(f"{name}.model_ids[{index}] is invalid")
        if model_id in result:
            raise ValueError(f"{name}.model_ids contains duplicates")
        result.append(model_id)
    return tuple(result)


def _step_titles(
    raw_titles: object,
    instructions: list[object],
    *,
    name: str,
) -> tuple[str, ...] | None:
    if raw_titles is not None:
        if not isinstance(raw_titles, list) or len(raw_titles) != len(instructions):
            raise ValueError(f"{name}.step_titles is invalid")
        return tuple(
            _text(value, name=f"{name}.step_titles[{index}]", max_chars=_MAX_TITLE_CHARS)
            for index, value in enumerate(raw_titles)
        )
    return None


def _instruction(value: object, *, name: str) -> tuple[str, str | None]:
    if isinstance(value, Mapping):
        raise ValueError(f"{name} must be text")
    return _text(value, name=name, max_chars=_MAX_INSTRUCTION_CHARS), None


def _derive_step_title(instruction: str, *, ordinal: int) -> str:
    compact = " ".join(instruction.split())
    for marker in ("。", ".", "！", "!", "？", "?"):
        if marker in compact:
            compact = compact.split(marker, 1)[0] + marker
            break
    prefix = f"Step {ordinal}: "
    available = _MAX_TITLE_CHARS - len(prefix)
    if len(compact) > available:
        if available <= 3:
            compact = compact[:available]
        else:
            compact = compact[: available - 3].rstrip() + "..."
    return prefix + compact


def _trusted_catalog_projection() -> Mapping[str, object]:
    from capstone_agent.catalog import trusted_catalog_projection

    return trusted_catalog_projection(Path(__file__).resolve().parents[4])


def _mapping(value: object, *, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object")
    return value


def _fields(value: Mapping[str, object], allowed: set[str], *, name: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise ValueError(f"{name} has unknown field: {', '.join(sorted(unknown))}")


def _text(value: object, *, name: str, max_chars: int = _MAX_TEXT_CHARS) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > max_chars:
        raise ValueError(f"{name} is invalid")
    return value


__all__ = ["CaseCatalog", "CaseDefinition", "CaseStepDefinition"]
