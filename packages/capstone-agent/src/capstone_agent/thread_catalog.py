"""Neutral adapter for Authority-owned model catalog records.

The Capstone application may select a Domain Pack and a registered Authority,
but the Thread protocol must not import either implementation.  This adapter
accepts the small public mapping returned by that selected Authority adapter
and retains only the immutable identity needed by ``ThreadCreator``.
"""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable, Mapping
import re
from typing import Any

from .model_identity import validate_model_id
from .thread_protocol import ThreadProtocolError, _document, _fields, _required, _text
from .thread_service import ThreadModelDescriptor


_FAMILY_ID = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
_REVISION = re.compile(r"^revision:[a-z0-9_-]+:[a-f0-9]{64}$")
_VERSION = re.compile(r"^[0-9]+(?:\.[0-9]+){1,3}(?:[-+][a-z0-9.-]+)?$")


def _identifier(value: Any, *, name: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ThreadProtocolError(f"{name} is invalid")
    return value


@dataclass(frozen=True, slots=True)
class ThreadModelCatalogEntry:
    """Bounded listing metadata for Web/TUI/CLI model selectors."""

    model_id: str
    authority_model_ref: str
    display_name: str
    diagram_provider_id: str
    implementation_family: str
    available: bool = True
    unavailable_reason: str | None = None


@dataclass(frozen=True, slots=True)
class ThreadCatalogProfileEntry:
    """Bounded profile metadata exposed by the public Thread catalog."""

    profile_id: str
    profile_version: str
    display_name: str
    implementation_families: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ThreadCatalogProjection:
    """Typed, bounded catalog projection shared by external clients."""

    models: tuple[ThreadModelCatalogEntry, ...]
    profiles: tuple[ThreadCatalogProfileEntry, ...]

    @classmethod
    def from_document(cls, value: Any) -> "ThreadCatalogProjection":
        document = _document(value, name="catalog")
        allowed = frozenset({"schema", "models", "profiles"})
        _fields(document, allowed, name="catalog")
        _required(document, allowed, name="catalog")
        if document["schema"] != "capstone-thread-catalog/1":
            raise ThreadProtocolError("catalog.schema is invalid")
        models = document["models"]
        profiles = document["profiles"]
        if not isinstance(models, list) or not isinstance(profiles, list) or len(models) > 128 or len(profiles) > 128:
            raise ThreadProtocolError("catalog is invalid or too large")
        return cls(
            tuple(_catalog_model_from_document(item, index=index) for index, item in enumerate(models)),
            tuple(_catalog_profile_from_document(item, index=index) for index, item in enumerate(profiles)),
        )


def _catalog_model_from_document(value: Any, *, index: int) -> ThreadModelCatalogEntry:
    document = _document(value, name=f"catalog.models[{index}]")
    fields = frozenset({"model_id", "authority_model_ref", "display_name", "diagram_provider_id", "implementation_family", "available", "unavailable_reason"})
    required_fields = fields - {"available", "unavailable_reason"}
    _fields(document, fields, name=f"catalog.models[{index}]")
    _required(document, required_fields, name=f"catalog.models[{index}]")
    try:
        model_id = validate_model_id(document["model_id"], name=f"catalog.models[{index}].model_id")
    except ValueError as error:
        raise ThreadProtocolError(str(error)) from None
    available = document.get("available", True)
    if type(available) is not bool:
        raise ThreadProtocolError(f"catalog.models[{index}].available is invalid")
    unavailable_reason = document.get("unavailable_reason")
    if unavailable_reason is not None:
        unavailable_reason = _identifier(unavailable_reason, name=f"catalog.models[{index}].unavailable_reason")
    return ThreadModelCatalogEntry(
        model_id=model_id,
        authority_model_ref=_text(document["authority_model_ref"], name=f"catalog.models[{index}].authority_model_ref"),
        display_name=_text(document["display_name"], name=f"catalog.models[{index}].display_name"),
        diagram_provider_id=_identifier(document["diagram_provider_id"], name=f"catalog.models[{index}].diagram_provider_id"),
        implementation_family=_identifier(document["implementation_family"], name=f"catalog.models[{index}].implementation_family"),
        available=available,
        unavailable_reason=unavailable_reason,
    )


def _catalog_profile_from_document(value: Any, *, index: int) -> ThreadCatalogProfileEntry:
    document = _document(value, name=f"catalog.profiles[{index}]")
    fields = frozenset({"profile_id", "profile_version", "display_name", "implementation_families"})
    _fields(document, fields, name=f"catalog.profiles[{index}]")
    _required(document, fields, name=f"catalog.profiles[{index}]")
    families = document["implementation_families"]
    version = _text(document["profile_version"], name=f"catalog.profiles[{index}].profile_version")
    if not isinstance(families, list) or len(families) > 32 or not _VERSION.fullmatch(version):
        raise ThreadProtocolError(f"catalog.profiles[{index}] is invalid")
    return ThreadCatalogProfileEntry(
        profile_id=_identifier(document["profile_id"], name=f"catalog.profiles[{index}].profile_id"),
        profile_version=version,
        display_name=_text(document["display_name"], name=f"catalog.profiles[{index}].display_name"),
        implementation_families=tuple(
            _identifier(family, name=f"catalog.profiles[{index}].implementation_families[{family_index}]")
            for family_index, family in enumerate(families)
        ),
    )


class CompositeThreadModelCatalog:
    """Route model resolution to exactly one registered Authority adapter."""

    def __init__(self, *, default_model_id: str) -> None:
        self.default_model_id = validate_model_id(default_model_id)
        self._catalogs: dict[str, AuthorityThreadModelCatalog] = {}

    def set_diagram_provider(self, provider: Callable[[str, str], Mapping[str, Any]]) -> None:
        if not callable(provider):
            raise TypeError("model diagram provider is invalid")
        # Installed only by the application composition root, never by a caller.
        self.diagram = provider

    def register(self, catalog: "AuthorityThreadModelCatalog") -> None:
        if not isinstance(catalog, AuthorityThreadModelCatalog):
            raise TypeError("catalog registration is invalid")
        model_ids = catalog.list_model_ids()
        duplicate = next((model_id for model_id in model_ids if model_id in self._catalogs), None)
        if duplicate is not None:
            raise ValueError(f"duplicate model registration: {duplicate}")
        for model_id in model_ids:
            if model_id in self._catalogs:
                raise ValueError(f"duplicate model registration: {model_id}")
            self._catalogs[model_id] = catalog

    def resolve(self, model_id: str | None) -> ThreadModelDescriptor:
        selected = self.default_model_id if model_id is None else validate_model_id(model_id)
        catalog = self._catalogs.get(selected)
        if catalog is None:
            raise LookupError(f"registered model was not found: {selected}")
        return catalog.resolve(selected)

    def list_model_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._catalogs))

    def list_models(self) -> tuple[ThreadModelDescriptor, ...]:
        return tuple(self.resolve(model_id) for model_id in self.list_model_ids())

    def list_entries(self) -> tuple[ThreadModelCatalogEntry, ...]:
        return tuple(_catalog_entry(model) for model in self.list_models())


class AuthorityThreadModelCatalog:
    """Convert one selected Authority's model record into a safe descriptor.

    ``resolver`` is supplied by the application-selected Authority adapter. It
    may return additional private data, but this boundary copies no such data
    into the Thread snapshot and never exposes the raw record to callers.
    """

    def __init__(
        self, *, default_model_id: str, resolver: Callable[[str], Mapping[str, Any]],
        model_ids: tuple[str, ...] | list[str] | None = None,
    ) -> None:
        validate_model_id(default_model_id, name="default_model_id")
        if not callable(resolver):
            raise TypeError("resolver must be callable")
        self.default_model_id = default_model_id
        self._resolver = resolver
        normalized = tuple(dict.fromkeys((*(model_ids or ()), default_model_id)))
        self._model_ids = tuple(validate_model_id(model_id) for model_id in normalized)
        self._bounded = model_ids is not None

    def list_model_ids(self) -> tuple[str, ...]:
        return self._model_ids

    def set_diagram_provider(self, provider: Callable[[str, str], Mapping[str, Any]]) -> None:
        if not callable(provider):
            raise TypeError("model diagram provider is invalid")
        self.diagram = provider

    def list_entries(self) -> tuple[ThreadModelCatalogEntry, ...]:
        return tuple(_catalog_entry(self.resolve(model_id)) for model_id in self._model_ids)

    def resolve(self, model_id: str | None) -> ThreadModelDescriptor:
        selected = self.default_model_id if model_id is None else model_id
        validate_model_id(selected)
        if self._bounded and selected not in self._model_ids:
            raise LookupError(f"registered model was not found: {selected}")
        record = self._resolver(selected)
        if not isinstance(record, Mapping):
            raise ValueError("Authority model record is invalid")
        resolved_id = record.get("model_id")
        revision = record.get("revision_ref")
        family = record.get("implementation_family", record.get("engine"))
        if not isinstance(resolved_id, str):
            raise ValueError("Authority model record model_id does not match request")
        validate_model_id(resolved_id)
        if resolved_id != selected:
            raise ValueError("Authority model record model_id does not match request")
        if not isinstance(revision, str) or not _REVISION.fullmatch(revision):
            raise ValueError("Authority model record revision_ref is invalid")
        if not isinstance(family, str) or not _FAMILY_ID.fullmatch(family):
            raise ValueError("Authority model record implementation family is invalid")
        metadata = {
            "authority_model_ref": record.get("authority_model_ref"),
            "display_name": record.get("display_name"),
            "diagram_provider_id": record.get("diagram_provider_id"),
        }
        if any(
            value is not None and (not isinstance(value, str) or not value.strip())
            for value in metadata.values()
        ):
            raise ValueError("Authority model record metadata is invalid")
        return ThreadModelDescriptor(
            model_id=resolved_id,
            model_revision=revision,
            implementation_family=family,
            authority_model_ref=metadata["authority_model_ref"],
            display_name=metadata["display_name"],
            diagram_provider_id=metadata["diagram_provider_id"],
            available=record.get("available", True),
            unavailable_reason=record.get("unavailable_reason"),
        )


def _catalog_entry(model: ThreadModelDescriptor) -> ThreadModelCatalogEntry:
    return ThreadModelCatalogEntry(
        model_id=model.model_id,
        authority_model_ref=model.authority_model_ref or model.model_id,
        display_name=model.display_name or model.model_id,
        diagram_provider_id=model.diagram_provider_id or model.implementation_family,
        implementation_family=model.implementation_family,
        available=model.available,
        unavailable_reason=model.unavailable_reason,
    )


__all__ = [
    "AuthorityThreadModelCatalog",
    "CompositeThreadModelCatalog",
    "ThreadCatalogProjection",
    "ThreadCatalogProfileEntry",
    "ThreadModelCatalogEntry",
]
