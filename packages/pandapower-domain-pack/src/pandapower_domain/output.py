"""Validated pandapower domain-output payload."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence


PANDAPOWER_OUTPUT_SCHEMA = "pandapower-static-analysis-output/1.1"
_REFERENCE = re.compile(r"^artifact:sha256:[0-9a-f]{64}$")
_PAYLOAD_KEYS = frozenset(
    {
        "mode",
        "instruction_count",
        "completed_count",
        "failed_count",
        "report_artifact_ref",
    }
)


class PandapowerOutputValidationError(ValueError):
    """A domain payload does not satisfy the pandapower output contract."""


class PandapowerOutputContract:
    """Build and validate only fields owned by the pandapower binding."""

    schema_id = PANDAPOWER_OUTPUT_SCHEMA
    domain_id = "pandapower-static-analysis"
    domain_version = "1.0.1"

    def __init__(self, *, allowed_references: Sequence[str] | None = None) -> None:
        self.allowed_references = (
            None if allowed_references is None else frozenset(allowed_references)
        )

    def build(
        self,
        *,
        binding_id: str,
        context: object,
        committed_answers: tuple[object, ...],
    ) -> Mapping[str, object]:
        if binding_id != "grid":
            raise PandapowerOutputValidationError(
                "pandapower output requires the grid binding"
            )
        _require_context_binding(context, binding_id)
        instruction_count = _instruction_count(context, committed_answers)
        completed_count = sum(
            1 for answer in committed_answers if _answer_status(answer) == "success"
        )
        failed_count = instruction_count - completed_count
        report_ref = _report_reference(context)
        if report_ref is not None:
            self._require_admitted_report_reference(report_ref, context)
        payload = {
            "mode": "continuous-static-analysis",
            "instruction_count": instruction_count,
            "completed_count": completed_count,
            "failed_count": failed_count,
            "report_artifact_ref": report_ref,
        }
        self._validate_payload(payload, allowed_references=self._admitted_references(context))
        return payload

    def validate(self, payload: Mapping[str, object]) -> None:
        self._validate_payload(
            payload,
            allowed_references=self.allowed_references,
        )

    def _validate_payload(
        self,
        payload: Mapping[str, object],
        *,
        allowed_references: frozenset[str] | None,
    ) -> None:
        if not isinstance(payload, Mapping):
            raise PandapowerOutputValidationError("pandapower output must be an object")
        if set(payload) != _PAYLOAD_KEYS:
            raise PandapowerOutputValidationError(
                "pandapower output fields do not match the domain contract"
            )
        if payload["mode"] != "continuous-static-analysis":
            raise PandapowerOutputValidationError("pandapower output mode is invalid")
        counts: list[int] = []
        for field in ("instruction_count", "completed_count", "failed_count"):
            value = payload[field]
            if type(value) is not int or value < 0:
                raise PandapowerOutputValidationError(
                    f"pandapower output {field} is invalid"
                )
            counts.append(value)
        if counts[1] + counts[2] != counts[0]:
            raise PandapowerOutputValidationError(
                "pandapower output counts are inconsistent"
            )
        report_ref = payload["report_artifact_ref"]
        if report_ref is not None:
            if not isinstance(report_ref, str) or not _REFERENCE.fullmatch(report_ref):
                raise PandapowerOutputValidationError(
                    "pandapower report reference is invalid"
                )
            if allowed_references is None:
                raise PandapowerOutputValidationError(
                    "pandapower report reference admission is unavailable"
                )
            if report_ref not in allowed_references:
                raise PandapowerOutputValidationError(
                    "pandapower report reference is not admitted for this run"
                )
        if any(
            isinstance(value, Mapping) and ("core" in value or "domains" in value)
            for value in payload.values()
        ):
            raise PandapowerOutputValidationError(
                "pandapower payload cannot contain framework sections"
            )

    def _require_admitted_report_reference(
        self, report_ref: object, context: object
    ) -> None:
        if not isinstance(report_ref, str) or not _REFERENCE.fullmatch(report_ref):
            raise PandapowerOutputValidationError(
                "pandapower report reference is required before output composition"
            )
        allowed = self._admitted_references(context)
        if report_ref not in allowed:
            raise PandapowerOutputValidationError(
                "pandapower report reference is not admitted for this run"
            )

    def _admitted_references(self, context: object) -> frozenset[str]:
        if self.allowed_references is not None:
            return self.allowed_references
        return _context_admitted_references(context)

    def build_envelope(
        self,
        *,
        binding_id: str,
        context: object,
        committed_answers: tuple[object, ...],
        status: str = "completed",
    ) -> Mapping[str, object]:
        """Return the binding envelope for callers outside the Kernel runner."""

        payload = self.build(
            binding_id=binding_id,
            context=context,
            committed_answers=committed_answers,
        )
        return {
            "domain_id": self.domain_id,
            "domain_version": self.domain_version,
            "schema": self.schema_id,
            "status": status,
            "payload": dict(payload),
        }


def _instruction_count(context: object, answers: tuple[object, ...]) -> int:
    raw = _context_mapping(context)
    for source in (raw, raw.get("state")):
        if isinstance(source, Mapping):
            value = source.get("instruction_count")
            if type(value) is int and value >= 0:
                return value
            input_value = source.get("input")
            if isinstance(input_value, Mapping):
                value = input_value.get("instruction_count")
                if type(value) is int and value >= 0:
                    return value
    return len(answers)


def _report_reference(context: object) -> str | None:
    raw = _context_mapping(context)
    for source in (raw, raw.get("state")):
        if isinstance(source, Mapping):
            if "report_artifact_ref" in source:
                value = source["report_artifact_ref"]
                if value is None:
                    return None
                if not isinstance(value, str):
                    raise PandapowerOutputValidationError(
                        "pandapower report reference is invalid"
                    )
                return value
    return None


def _require_context_binding(context: object, binding_id: str) -> None:
    raw = _context_mapping(context)
    for source in (raw, raw.get("state")):
        if not isinstance(source, Mapping):
            continue
        value = source.get("binding_id")
        if value is not None and value != binding_id:
            raise PandapowerOutputValidationError(
                "pandapower output context has a foreign binding"
            )


def _context_admitted_references(context: object) -> frozenset[str]:
    raw = _context_mapping(context)
    references: set[str] = set()
    for source in (raw, raw.get("state")):
        if not isinstance(source, Mapping):
            continue
        for key in ("admitted_artifact_refs", "admitted_refs", "allowed_references"):
            values = source.get(key)
            if isinstance(values, str):
                values = (values,)
            if isinstance(values, Sequence):
                references.update(
                    value for value in values if isinstance(value, str)
                )
        artifacts = source.get("artifacts")
        if isinstance(artifacts, Mapping):
            for artifact in artifacts.values():
                if isinstance(artifact, Mapping):
                    reference = artifact.get("artifact_ref")
                    if isinstance(reference, str):
                        references.add(reference)
    return frozenset(references)


def _context_mapping(context: object) -> dict[str, object]:
    dump = getattr(context, "model_dump", None)
    if callable(dump):
        try:
            value = dump(mode="python")
        except TypeError:
            value = dump()
        if isinstance(value, Mapping):
            return {str(key): item for key, item in value.items()}
    if isinstance(context, Mapping):
        return {str(key): item for key, item in context.items()}
    return {}


def _answer_status(answer: object) -> str:
    if isinstance(answer, Mapping):
        value = answer.get("status")
    else:
        value = getattr(answer, "status", "success")
    return value if isinstance(value, str) else "success"


__all__ = [
    "PANDAPOWER_OUTPUT_SCHEMA",
    "PandapowerOutputContract",
    "PandapowerOutputValidationError",
]
