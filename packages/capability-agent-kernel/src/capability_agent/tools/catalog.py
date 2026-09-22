from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from capability_agent._safe_files import write_bound_text

if TYPE_CHECKING:
    from capability_agent.application.composition import PreparedBinding


_CAPABILITY_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]+$")
_TOOL_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
_TOOL_NAME_PREFIX_PATTERN = re.compile(r"^[a-z][a-z0-9_]*_$")
_SCHEMA_ID_PATTERN = re.compile(r"^[a-z][a-z0-9-]*$")
_JSON_SCHEMA_TYPES = {"array", "boolean", "integer", "null", "number", "object", "string"}
_DEFAULT_TOOL_NAME_PREFIX = "tool_"
_BINDING_ID_PATTERN = re.compile(r"^[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?$")
_PROTOCOL_VERSION_PATTERN = re.compile(r"^\d+\.\d+$")


class ToolCatalogError(ValueError):
    """Raised when semantic capability documents cannot be materialized."""


@dataclass(frozen=True, slots=True)
class ToolDocument:
    name: str
    capability: str
    description: str
    input_schema: dict[str, Any]
    projector_id: str | None = None
    result_kind: str | None = None

    def as_json(self) -> dict[str, Any]:
        document = {
            "name": self.name,
            "capability": self.capability,
            "description": self.description,
            "input_schema": self.input_schema,
        }
        if self.projector_id is not None:
            document["projector_id"] = self.projector_id
            document["result_kind"] = self.result_kind
        return document


@dataclass(frozen=True, slots=True)
class CapabilityKey:
    binding_id: str
    capability_id: str


@dataclass(frozen=True, slots=True)
class BoundToolDocument:
    name: str
    key: CapabilityKey
    description: str
    input_schema: dict[str, Any]
    authority_id: str
    protocol: str
    protocol_version: str
    projector_id: str | None = None
    result_kind: str | None = None


class ToolCatalog:
    def __init__(
        self,
        tools: tuple[ToolDocument, ...],
        *,
        tool_name_prefix: str | None = None,
        protocol: str | None = None,
    ) -> None:
        tool_name_prefix = _resolve_tool_name_prefix(
            (tool.name for tool in tools), tool_name_prefix
        )
        _validate_tool_name_prefix(tool_name_prefix)
        protocol = _resolve_schema_id(
            protocol, _schema_id_from_prefix(tool_name_prefix, "tool-catalog")
        )
        for tool in tools:
            _validate_tool_name(tool.name, tool_name_prefix)
        names = [tool.name for tool in tools]
        if len(set(names)) != len(names):
            raise ToolCatalogError("tool names must be unique")
        capabilities = [tool.capability for tool in tools]
        if len(set(capabilities)) != len(capabilities):
            raise ToolCatalogError("capabilities must be unique")
        self.tools = tuple(sorted(tools, key=lambda tool: tool.name))
        self._by_name = {tool.name: tool for tool in self.tools}
        self._protocol = protocol

    @classmethod
    def from_documents(
        cls,
        documents: tuple[dict[str, object], ...] | list[dict[str, object]],
        *,
        tool_name_prefix: str | None = None,
        protocol: str | None = None,
        description_builder: Callable[[dict[str, object]], str] | None = None,
    ) -> "ToolCatalog":
        documents = tuple(documents)
        tool_name_prefix = _resolve_tool_name_prefix(
            (document.get("tool_name") for document in documents), tool_name_prefix
        )
        _validate_tool_name_prefix(tool_name_prefix)
        return cls(
            tuple(
                _materialize_tool(document, tool_name_prefix, description_builder)
                for document in documents
            ),
            tool_name_prefix=tool_name_prefix,
            protocol=protocol,
        )

    @classmethod
    def from_environment(
        cls,
        documents: tuple[dict[str, object], ...] | list[dict[str, object]],
        environment_description: dict[str, object],
        *,
        tool_name_prefix: str | None = None,
        protocol: str | None = None,
        description_builder: Callable[[dict[str, object]], str] | None = None,
    ) -> "ToolCatalog":
        documents = tuple(documents)
        tool_name_prefix = _resolve_tool_name_prefix(
            (document.get("tool_name") for document in documents), tool_name_prefix
        )
        _validate_tool_name_prefix(tool_name_prefix)
        executable = environment_description.get("executable_capabilities")
        if not isinstance(executable, list):
            raise ToolCatalogError("environment.describe result must include executable_capabilities")
        executable_ids = []
        for item in executable:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                raise ToolCatalogError("environment.describe executable_capabilities must contain ids")
            executable_ids.append(item["id"])

        by_id = {str(document.get("id")): document for document in documents}
        missing = [capability_id for capability_id in executable_ids if capability_id not in by_id]
        if missing:
            raise ToolCatalogError(f"missing capability documents: {', '.join(missing)}")
        selected = [by_id[capability_id] for capability_id in executable_ids]
        environment_by_id = {
            str(item["id"]): item for item in executable if isinstance(item, dict) and isinstance(item.get("id"), str)
        }
        for document in selected:
            capability_id = str(document["id"])
            if document.get("availability") != "published":
                raise ToolCatalogError(f"executable capability {capability_id} is not published")
            announced = environment_by_id[capability_id]
            for field in ("availability", "context_effect"):
                if field in announced and announced[field] != document.get(field):
                    raise ToolCatalogError(f"environment {field} does not match capability document: {capability_id}")
        return cls.from_documents(
            selected,
            tool_name_prefix=tool_name_prefix,
            protocol=protocol,
            description_builder=description_builder,
        )

    def require(self, name: str) -> ToolDocument:
        try:
            return self._by_name[name]
        except KeyError as exc:
            raise KeyError(f"unknown tool: {name}") from exc

    def materialize(self, path: Path) -> Path:
        path = Path(path)
        body = {
            "protocol": self._protocol,
            "version": "1.0",
            "tools": [tool.as_json() for tool in self.tools],
        }
        fingerprint = "sha256:" + hashlib.sha256(_canonical_json(body).encode("utf-8")).hexdigest()
        payload = {"fingerprint": fingerprint, **body}
        try:
            write_bound_text(path, _canonical_json(payload) + "\n")
        except OSError as exc:
            raise ToolCatalogError("tool catalog could not be materialized safely") from exc
        return path


@dataclass(frozen=True, slots=True)
class CoreToolCatalog:
    namespace: str
    tools: tuple[ToolDocument, ...]

    @classmethod
    def default(cls, *, namespace: str = "agent_") -> "CoreToolCatalog":
        if namespace != "agent_":
            raise ToolCatalogError("generic core tool namespace must be agent_")
        _validate_tool_name_prefix(namespace)
        return cls(
            namespace=namespace,
            tools=(_decision_tool(namespace), _context_tool(namespace)),
        )


@dataclass(frozen=True, slots=True)
class BoundDomainCatalog:
    binding_id: str
    tool_namespace: str
    tools: tuple[BoundToolDocument, ...]
    authority_id: str
    protocol: str
    protocol_version: str
    guide_tool_name: str | None = None
    context_tool_name: str | None = None

    @classmethod
    def fixture(
        cls,
        binding_id: str,
        tool_namespace: str,
        documents: tuple[dict[str, object], ...] | list[dict[str, object]],
        *,
        authority_id: str | None = None,
        protocol: str | None = None,
        protocol_version: str = "1.0",
        guide_tool_name: str | None = None,
        context_tool_name: str | None = None,
    ) -> "BoundDomainCatalog":
        authority_id = authority_id or f"{binding_id}ctl"
        protocol = protocol or f"{binding_id}-capability"
        catalog = ToolCatalog.from_documents(
            tuple(documents),
            tool_name_prefix=tool_namespace,
        )
        return cls._bind(
            binding_id=binding_id,
            tool_namespace=tool_namespace,
            catalog=catalog,
            authority_id=authority_id,
            protocol=protocol,
            protocol_version=protocol_version,
            guide_tool_name=guide_tool_name,
            context_tool_name=context_tool_name,
        )

    @classmethod
    def from_prepared(
        cls,
        prepared: PreparedBinding,
        *,
        guide_tool_name: str | None = None,
        context_tool_name: str | None = None,
    ) -> "BoundDomainCatalog":
        binding = prepared.binding
        runtime = prepared.runtime
        manifest = binding.profile.manifest
        if guide_tool_name is None:
            guide_tool_name = f"{binding.tool_namespace}guide_open"
        if (
            runtime.authority.authority_id != manifest.authority_id
            or runtime.environment_description.get("protocol") != manifest.protocol
            or runtime.environment_description.get("protocol_version")
            != manifest.protocol_version
        ):
            raise ToolCatalogError("prepared binding routing metadata does not agree")
        catalog = ToolCatalog.from_environment(
            runtime.capability_documents,
            runtime.environment_description,
            tool_name_prefix=binding.tool_namespace,
            protocol=_schema_id_from_prefix(binding.tool_namespace, "tool-catalog"),
            description_builder=binding.profile.tool_description_builder,
        )
        return cls._bind(
            binding_id=binding.binding_id,
            tool_namespace=binding.tool_namespace,
            catalog=catalog,
            authority_id=manifest.authority_id,
            protocol=manifest.protocol,
            protocol_version=manifest.protocol_version,
            guide_tool_name=guide_tool_name,
            context_tool_name=context_tool_name,
        )

    @classmethod
    def _bind(
        cls,
        *,
        binding_id: str,
        tool_namespace: str,
        catalog: ToolCatalog,
        authority_id: str,
        protocol: str,
        protocol_version: str,
        guide_tool_name: str | None,
        context_tool_name: str | None,
    ) -> "BoundDomainCatalog":
        _validate_binding_metadata(
            binding_id=binding_id,
            authority_id=authority_id,
            protocol=protocol,
            protocol_version=protocol_version,
        )
        for label, tool_name in (
            ("guide_tool_name", guide_tool_name),
            ("context_tool_name", context_tool_name),
        ):
            if tool_name is not None:
                try:
                    _validate_tool_name(tool_name, tool_namespace)
                except ToolCatalogError as exc:
                    raise ToolCatalogError(f"{label} is invalid") from exc
        return cls(
            binding_id=binding_id,
            tool_namespace=tool_namespace,
            tools=tuple(
                BoundToolDocument(
                    name=tool.name,
                    key=CapabilityKey(binding_id, tool.capability),
                    description=tool.description,
                    input_schema=tool.input_schema,
                    authority_id=authority_id,
                    protocol=protocol,
                    protocol_version=protocol_version,
                    projector_id=tool.projector_id,
                    result_kind=tool.result_kind,
                )
                for tool in catalog.tools
            ),
            authority_id=authority_id,
            protocol=protocol,
            protocol_version=protocol_version,
            guide_tool_name=guide_tool_name,
            context_tool_name=context_tool_name,
        )


class CompositeToolCatalog:
    def __init__(
        self,
        *,
        core_tools: tuple[ToolDocument, ...],
        domain_tools: tuple[BoundToolDocument, ...],
        auxiliary_tool_names: tuple[str, ...] = (),
        guide_tool_bindings: tuple[tuple[str, str], ...] = (),
    ) -> None:
        self.core_tools = core_tools
        self.domain_tools = domain_tools
        self.auxiliary_tool_names = frozenset(auxiliary_tool_names)
        self.guide_tool_bindings = dict(guide_tool_bindings)
        self._by_name = {
            tool.name: tool for tool in (*self.core_tools, *self.domain_tools)
        }

    @classmethod
    def build(
        cls,
        *,
        core: CoreToolCatalog,
        domains: tuple[BoundDomainCatalog, ...],
    ) -> "CompositeToolCatalog":
        if core.namespace != "agent_" or any(
            not tool.name.startswith("agent_") for tool in core.tools
        ):
            raise ToolCatalogError("generic core tools must use the agent_ namespace")
        binding_ids = [domain.binding_id for domain in domains]
        if len(set(binding_ids)) != len(binding_ids):
            raise ToolCatalogError("binding IDs must be unique")
        namespaces = [domain.tool_namespace for domain in domains]
        if len(set(namespaces)) != len(namespaces):
            raise ToolCatalogError("tool namespaces must be unique")
        if any(namespace == core.namespace for namespace in namespaces):
            raise ToolCatalogError("reserved core namespace cannot be used by a domain")

        core_names = [tool.name for tool in core.tools]
        domain_tools = tuple(tool for domain in domains for tool in domain.tools)
        routing_names = [
            tool.name for tool in domain_tools
        ] + [
            name
            for domain in domains
            for name in (domain.guide_tool_name, domain.context_tool_name)
            if name is not None
        ]
        if any(name.startswith(core.namespace) for name in routing_names):
            raise ToolCatalogError("reserved core namespace cannot be used by a domain")
        final_names = [*core_names, *routing_names]
        if len(set(final_names)) != len(final_names):
            raise ToolCatalogError("final tool names must be unique")
        if len(domains) != 1:
            raise ToolCatalogError("composite catalog requires exactly one domain binding")
        return cls(
            core_tools=tuple(sorted(core.tools, key=lambda tool: tool.name)),
            guide_tool_bindings=tuple(
                (domain.guide_tool_name, domain.binding_id)
                for domain in domains if domain.guide_tool_name is not None
            ),
            domain_tools=tuple(sorted(domain_tools, key=lambda tool: tool.name)),
            auxiliary_tool_names=tuple(
                name
                for domain in domains
                for name in (domain.guide_tool_name, domain.context_tool_name)
                if name is not None
            ),
        )

    def is_auxiliary(self, name: str) -> bool:
        return name in self.auxiliary_tool_names

    def require(self, name: str) -> ToolDocument | BoundToolDocument:
        try:
            return self._by_name[name]
        except KeyError as exc:
            raise KeyError(f"unknown tool: {name}") from exc



def _materialize_tool(
    document: dict[str, object],
    tool_name_prefix: str,
    description_builder: Callable[[dict[str, object]], str] | None = None,
) -> ToolDocument:
    _validate_document(document, tool_name_prefix)
    input_schema = document["input_schema"]
    context_effect = document["context_effect"]
    assert isinstance(input_schema, dict)
    assert isinstance(context_effect, dict)
    return ToolDocument(
        name=str(document["tool_name"]),
        capability=str(document["id"]),
        description=(
            description_builder(document)
            if description_builder is not None
            else describe_tool_document(document)
        ),
        input_schema=input_schema,
        projector_id=str(context_effect["projector"]),
        result_kind=context_effect["result_kind"],
    )


def _decision_tool(tool_name_prefix: str) -> ToolDocument:
    bounded_text = {"type": "string", "minLength": 1, "maxLength": 500}
    tool_name = f"{tool_name_prefix}record_decision"
    return ToolDocument(
        name=tool_name,
        capability=tool_name,
        description=(
            "Declare bounded agent intent and its next action. "
            "This declaration is agent intent, not simulator truth, and cannot "
            "create results, facts, or evidence."
        ),
        input_schema={
            "type": "object",
            "additionalProperties": False,
            "required": ["intent", "decision", "next_action", "refs"],
            "properties": {
                "intent": dict(bounded_text),
                "decision": dict(bounded_text),
                "next_action": dict(bounded_text),
                "refs": {
                    "type": "array",
                    "items": {"type": "string", "minLength": 1},
                    "maxItems": 20,
                },
            },
        },
    )


def _context_tool(tool_name_prefix: str) -> ToolDocument:
    tool_name = f"{tool_name_prefix}context_get"
    return ToolDocument(
        name=tool_name,
        capability=tool_name,
        description=(
            "Return the controller-generated bounded read-only application "
            "context view. This view is execution context, not domain truth."
        ),
        input_schema={
            "type": "object",
            "additionalProperties": False,
            "properties": {},
        },
    )


def _validate_document(
    document: dict[str, object], tool_name_prefix: str
) -> None:
    required = (
        "id",
        "tool_name",
        "availability",
        "context_effect",
        "purpose",
        "applies_to",
        "not_for",
        "input_schema",
        "requires",
        "produces",
        "common_next",
        "recovery",
    )
    for field in required:
        if field not in document:
            raise ToolCatalogError(f"capability document missing {field}")
    if not isinstance(document["id"], str) or not _CAPABILITY_ID_PATTERN.fullmatch(document["id"]):
        raise ToolCatalogError("capability id is invalid")
    _validate_tool_name(document["tool_name"], tool_name_prefix)
    if document["availability"] != "published":
        raise ToolCatalogError(f"capability {document['id']} is not published")
    context_effect = document["context_effect"]
    if not isinstance(context_effect, dict):
        raise ToolCatalogError("context_effect must be an object")
    required_context_fields = {
        "requires_state",
        "consumes_state",
        "produces_state",
        "invalidates_state",
        "result_kind",
        "projector",
    }
    if set(context_effect) != required_context_fields:
        raise ToolCatalogError("context_effect fields are invalid")
    for field in ("requires_state", "consumes_state", "produces_state", "invalidates_state"):
        if not isinstance(context_effect[field], list) or not all(isinstance(item, str) for item in context_effect[field]):
            raise ToolCatalogError(f"context_effect.{field} must be a list of strings")
    if context_effect["result_kind"] is not None and not isinstance(context_effect["result_kind"], str):
        raise ToolCatalogError("context_effect.result_kind must be a string or null")
    if not isinstance(context_effect["projector"], str) or not context_effect["projector"]:
        raise ToolCatalogError("context_effect.projector is required")
    if not isinstance(document["purpose"], str) or not document["purpose"].strip():
        raise ToolCatalogError("purpose is required")
    for field in ("applies_to", "not_for", "requires", "produces", "common_next"):
        values = document[field]
        if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
            raise ToolCatalogError(f"{field} must be a list of strings")
    if not isinstance(document["recovery"], dict) or not all(
        isinstance(error, str)
        and isinstance(actions, list)
        and all(isinstance(action, str) for action in actions)
        for error, actions in document["recovery"].items()
    ):
        raise ToolCatalogError("recovery must map error strings to action lists")
    input_schema = document["input_schema"]
    if not isinstance(input_schema, dict):
        raise ToolCatalogError("input_schema must be a JSON object")
    _validate_json_schema(input_schema, path="input_schema")


def _resolve_tool_name_prefix(
    names: Any,
    tool_name_prefix: str | None,
) -> str:
    if tool_name_prefix is not None:
        return tool_name_prefix
    for name in names:
        if isinstance(name, str):
            separator = name.find("_")
            if separator > 0:
                return name[: separator + 1]
    return _DEFAULT_TOOL_NAME_PREFIX


def _resolve_schema_id(schema_id: str | None, default: str) -> str:
    value = default if schema_id is None else schema_id
    if not isinstance(value, str) or not _SCHEMA_ID_PATTERN.fullmatch(value):
        raise ToolCatalogError("protocol is invalid")
    return value


def _schema_id_from_prefix(tool_name_prefix: str, suffix: str) -> str:
    namespace = tool_name_prefix.removesuffix("_").replace("_", "-")
    if not namespace or namespace == "tool":
        namespace = "capability"
    return f"{namespace}-{suffix}"


def _validate_tool_name_prefix(tool_name_prefix: str) -> None:
    if not isinstance(tool_name_prefix, str) or not _TOOL_NAME_PREFIX_PATTERN.fullmatch(
        tool_name_prefix
    ):
        raise ToolCatalogError("tool_name_prefix is invalid")


def _validate_tool_name(tool_name: object, tool_name_prefix: str) -> None:
    if isinstance(tool_name, str) and not tool_name.startswith(tool_name_prefix):
        raise ToolCatalogError("tool_name must begin with tool_name_prefix")
    if (
        not isinstance(tool_name, str)
        or not _TOOL_NAME_PATTERN.fullmatch(tool_name)
        or len(tool_name) == len(tool_name_prefix)
    ):
        raise ToolCatalogError("tool_name is invalid")


def _validate_binding_metadata(
    *,
    binding_id: str,
    authority_id: str,
    protocol: str,
    protocol_version: str,
) -> None:
    if not isinstance(binding_id, str) or not _BINDING_ID_PATTERN.fullmatch(binding_id):
        raise ToolCatalogError("binding_id is invalid")
    for label, value in (("authority_id", authority_id), ("protocol", protocol)):
        if not isinstance(value, str) or not _CAPABILITY_ID_PATTERN.fullmatch(value):
            raise ToolCatalogError(f"{label} is invalid")
    if (
        not isinstance(protocol_version, str)
        or not _PROTOCOL_VERSION_PATTERN.fullmatch(protocol_version)
    ):
        raise ToolCatalogError("protocol_version is invalid")


def _validate_json_schema(schema: dict[str, Any], *, path: str) -> None:
    schema_type = schema.get("type")
    if schema_type is not None:
        if isinstance(schema_type, str):
            if schema_type not in _JSON_SCHEMA_TYPES:
                raise ToolCatalogError(f"{path} has invalid type")
        elif isinstance(schema_type, list):
            if not all(isinstance(item, str) and item in _JSON_SCHEMA_TYPES for item in schema_type):
                raise ToolCatalogError(f"{path} has invalid type")
        else:
            raise ToolCatalogError(f"{path} has invalid type")
    properties = schema.get("properties")
    if properties is not None:
        if not isinstance(properties, dict):
            raise ToolCatalogError(f"{path}.properties must be an object")
        for name, child in properties.items():
            if not isinstance(name, str) or not isinstance(child, dict):
                raise ToolCatalogError(f"{path}.properties must contain schemas")
            _validate_json_schema(child, path=f"{path}.properties.{name}")
    for keyword in ("items", "not"):
        child = schema.get(keyword)
        if child is not None:
            if not isinstance(child, dict):
                raise ToolCatalogError(f"{path}.{keyword} must be a schema")
            _validate_json_schema(child, path=f"{path}.{keyword}")
    for keyword in ("oneOf", "anyOf", "allOf"):
        children = schema.get(keyword)
        if children is not None:
            if not isinstance(children, list) or not all(isinstance(child, dict) for child in children):
                raise ToolCatalogError(f"{path}.{keyword} must be a list of schemas")
            for index, child in enumerate(children):
                _validate_json_schema(child, path=f"{path}.{keyword}.{index}")


def describe_tool_document(document: dict[str, object]) -> str:
    """Build the neutral reader-facing description for one capability document."""

    not_for = list(_strings(document["not_for"]))
    not_for.extend(_extension_limitations(document))
    applies_to = list(_strings(document["applies_to"]))
    terms = document.get("terms")
    if isinstance(terms, dict):
        applies_to.extend(_strings(terms.get("zh", [])))
        applies_to.extend(_strings(terms.get("en", [])))
    return "\n".join(
        (
            f"Purpose: {document['purpose']}",
            f"Use for: {_list_text(applies_to)}",
            f"Do not use for: {_list_text(not_for)}",
            f"Requires: {_list_text(_strings(document['requires']))}",
            f"Produces: {_list_text(_strings(document['produces']))}",
            f"Common next capabilities: {_list_text(_strings(document['common_next']))}",
            f"Recovery: {_recovery_text(document['recovery'])}",
        )
    )


def _description(document: dict[str, object]) -> str:
    """Backward-compatible private alias for the neutral description builder."""

    return describe_tool_document(document)


def _extension_limitations(value: object) -> tuple[str, ...]:
    limitations: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            if key == "limitations":
                limitations.extend(_strings(child))
            elif isinstance(child, (Mapping, list, tuple)):
                limitations.extend(_extension_limitations(child))
    elif isinstance(value, (list, tuple)):
        for child in value:
            limitations.extend(_extension_limitations(child))
    return tuple(limitations)


def _strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value if isinstance(item, str))


def _list_text(values: list[str] | tuple[str, ...]) -> str:
    return ", ".join(values) if values else "none"


def _recovery_text(value: object) -> str:
    if not isinstance(value, dict) or not value:
        return "none"
    parts = []
    for error in sorted(value):
        actions = value[error]
        parts.append(f"{error} -> {_list_text(_strings(actions))}")
    return "; ".join(parts)


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
