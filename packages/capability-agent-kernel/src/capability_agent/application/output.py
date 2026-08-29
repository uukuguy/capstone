"""Kernel-owned output composition and lossless JSON rendering."""

from __future__ import annotations

import json
import warnings
from collections.abc import Mapping, Sequence
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from capability_agent.application.errors import ApplicationConfigurationError


class _StrictFrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


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
        schema: str
        status: str
        payload: dict[str, object]


    class BoundDomainOutput(_StrictFrozenModel):
        domain_id: str
        domain_version: str
        schema: str
        status: str
        payload: dict[str, object]


    class ApplicationResult(_StrictFrozenModel):
        schema: str
        core: CoreRunResult
        domains: dict[str, BoundDomainOutput]


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
