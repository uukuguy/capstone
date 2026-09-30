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
from .thread_service import ThreadModelDescriptor


_FAMILY_ID = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
_REVISION = re.compile(r"^revision:[a-z0-9_-]+:[a-f0-9]{64}$")


@dataclass(frozen=True, slots=True)
class ThreadModelCatalogEntry:
    """Bounded listing metadata for Web/TUI/CLI model selectors."""

    model_id: str
    authority_model_ref: str
    display_name: str
    diagram_provider_id: str
    implementation_family: str


class CompositeThreadModelCatalog:
    """Route model resolution to exactly one registered Authority adapter."""

    def __init__(self, *, default_model_id: str) -> None:
        self.default_model_id = validate_model_id(default_model_id)
        self._catalogs: dict[str, AuthorityThreadModelCatalog] = {}

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
        )


def _catalog_entry(model: ThreadModelDescriptor) -> ThreadModelCatalogEntry:
    return ThreadModelCatalogEntry(
        model_id=model.model_id,
        authority_model_ref=model.authority_model_ref or model.model_id,
        display_name=model.display_name or model.model_id,
        diagram_provider_id=model.diagram_provider_id or model.implementation_family,
        implementation_family=model.implementation_family,
    )


__all__ = [
    "AuthorityThreadModelCatalog",
    "CompositeThreadModelCatalog",
    "ThreadModelCatalogEntry",
]
