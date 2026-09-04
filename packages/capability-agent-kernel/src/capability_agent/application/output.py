"""Kernel-owned output composition and lossless JSON rendering."""

from __future__ import annotations

import json
import math
import warnings
from collections.abc import Mapping, Sequence
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from capability_agent.application.errors import ApplicationConfigurationError


class _StrictFrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class _FrozenDict(dict[str, Any]):
    """A JSON-compatible dictionary that rejects every in-place mutation."""

    def __init__(self, values: Mapping[str, Any]) -> None:
        dict.__init__(self, values)

    def _immutable(self, *args: object, **kwargs: object) -> None:
        raise TypeError("mapping is immutable")

    __delitem__ = _immutable
    __setitem__ = _immutable
    __ior__ = _immutable  # type: ignore[reportAssignmentType]
    clear = _immutable
    pop = _immutable
    popitem = _immutable  # type: ignore[reportAssignmentType]
    setdefault = _immutable  # type: ignore[reportAssignmentType]
    update = _immutable  # type: ignore[reportAssignmentType]


def _deep_freeze(value: Any) -> Any:
    try:
        return _deep_freeze_value(value, set())
    except RecursionError as error:
        raise ApplicationConfigurationError(
            "domain output payload nesting exceeds the supported depth"
        ) from error


def _deep_freeze_value(value: Any, active_containers: set[int]) -> Any:
    if isinstance(value, Mapping):
        identity = id(value)
        if identity in active_containers:
            raise ApplicationConfigurationError(
                "domain output payload contains a container cycle"
            )
        active_containers.add(identity)
        try:
            if any(not isinstance(key, str) for key in value):
                raise ApplicationConfigurationError(
                    "domain output payload mappings require string keys"
                )
            return _FrozenDict(
                {
                    key: _deep_freeze_value(item, active_containers)
                    for key, item in value.items()
                }
            )
        finally:
            active_containers.remove(identity)
    if isinstance(value, list | tuple):
        identity = id(value)
        if identity in active_containers:
            raise ApplicationConfigurationError(
                "domain output payload contains a container cycle"
            )
        active_containers.add(identity)
        try:
            return tuple(
                _deep_freeze_value(item, active_containers) for item in value
            )
        finally:
            active_containers.remove(identity)
    if value is None or type(value) in {str, bool, int}:
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise ApplicationConfigurationError(
                "domain output payload float values must be finite"
            )
        return value
    raise ApplicationConfigurationError(
        f"domain output payload contains unsupported JSON value: "
        f"{type(value).__name__}"
    )


class CoreRunResult(_StrictFrozenModel):
    application_id: str
    application_version: str
    run_id: str
    status: str
    answer_refs: tuple[str, ...]
    report_ref: str | None
    diagnostic_refs: tuple[str, ...]


class BindingIdentity(_StrictFrozenModel):
    binding_id: str
    domain_id: str
    domain_version: str


with warnings.catch_warnings():
    warnings.filterwarnings(
        "ignore",
        message=r'Field name "schema" in .* shadows an attribute in parent',
        category=UserWarning,
    )

    class ValidatedDomainOutput(_StrictFrozenModel):
        # Public wire/attribute contract predates Pydantic's deprecated schema method.
        schema: str  # pyright: ignore[reportIncompatibleMethodOverride]
        status: str
        payload: Mapping[str, object]

        @field_validator("payload", mode="before")
        @classmethod
        def validate_json_payload(cls, value: object) -> object:
            return _deep_freeze(value)

        @model_validator(mode="after")
        def freeze_payload(self) -> "ValidatedDomainOutput":
            object.__setattr__(self, "payload", _deep_freeze(self.payload))
            return self


    class BoundDomainOutput(_StrictFrozenModel):
        domain_id: str
        domain_version: str
        # Preserve the public schema attribute and wire key, not BaseModel.schema().
        schema: str  # pyright: ignore[reportIncompatibleMethodOverride]
        status: str
        payload: Mapping[str, object]

        @model_validator(mode="after")
        def freeze_payload(self) -> "BoundDomainOutput":
            object.__setattr__(self, "payload", _deep_freeze(self.payload))
            return self


    class ApplicationResult(_StrictFrozenModel):
        # Preserve the public schema attribute and wire key, not BaseModel.schema().
        schema: str  # pyright: ignore[reportIncompatibleMethodOverride]
        core: CoreRunResult
        domains: Mapping[str, BoundDomainOutput]

        @model_validator(mode="after")
        def freeze_domains(self) -> "ApplicationResult":
            object.__setattr__(self, "domains", _FrozenDict(self.domains))
            return self


class OutputRenderer(Protocol):
    """Serialize an already validated application result."""

    def render(self, result: ApplicationResult) -> str: ...


class FrameworkOutputComposer:
    """Combine framework and independently validated binding outputs."""

    schema_id = "capability-agent-output/1.0"

    def compose(
        self,
        *,
        core: CoreRunResult,
        bindings: Sequence[BindingIdentity],
        domains: Mapping[str, ValidatedDomainOutput],
    ) -> ApplicationResult:
        identities = {binding.binding_id: binding for binding in bindings}
        if len(identities) != len(bindings):
            raise ApplicationConfigurationError("binding identities must be unique")

        binding_ids = set(identities)
        output_ids = set(domains)
        if binding_ids != output_ids:
            missing = sorted(binding_ids - output_ids)
            extra = sorted(output_ids - binding_ids)
            raise ApplicationConfigurationError(
                f"binding outputs do not match identities: missing={missing}, extra={extra}"
            )

        bound_outputs: dict[str, BoundDomainOutput] = {}
        for binding_id in sorted(identities):
            identity = identities[binding_id]
            output = domains[binding_id]
            reserved = sorted({"core", "domains"}.intersection(output.payload))
            if reserved:
                raise ApplicationConfigurationError(
                    "domain payload contains reserved top-level sections: "
                    + ", ".join(reserved)
                )
            bound_outputs[binding_id] = BoundDomainOutput(
                domain_id=identity.domain_id,
                domain_version=identity.domain_version,
                schema=output.schema,
                status=output.status,
                payload=dict(output.payload),
            )

        return ApplicationResult(
            schema=self.schema_id,
            core=core,
            domains=bound_outputs,
        )


class JsonOutputRenderer:
    """Render the complete validated result as canonical single-line JSON."""

    def render(self, result: ApplicationResult) -> str:
        return json.dumps(
            result.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ) + "\n"


__all__ = [
    "ApplicationResult",
    "BindingIdentity",
    "BoundDomainOutput",
    "CoreRunResult",
    "FrameworkOutputComposer",
    "JsonOutputRenderer",
    "OutputRenderer",
    "ValidatedDomainOutput",
]
