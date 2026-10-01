"""Strict Python projection of the public Thread catalog."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from capstone_agent.model_identity import validate_model_id

from capstone_agent.thread_protocol import ThreadProtocolError, _document, _fields, _required, _text


_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
_VERSION = re.compile(r"^[0-9]+(?:\.[0-9]+){1,3}(?:[-+][a-z0-9.-]+)?$")


def _identifier(value: Any, *, name: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ThreadProtocolError(f"{name} is invalid")
    return value


@dataclass(frozen=True, slots=True)
class ThreadCatalogModel:
    model_id: str
    authority_model_ref: str
    display_name: str
    diagram_provider_id: str
    implementation_family: str

    @classmethod
    def from_document(cls, value: Any, *, index: int) -> ThreadCatalogModel:
        document = _document(value, name=f"catalog.models[{index}]")
        fields = frozenset({"model_id", "authority_model_ref", "display_name", "diagram_provider_id", "implementation_family"})
        _fields(document, fields, name=f"catalog.models[{index}]")
        _required(document, fields, name=f"catalog.models[{index}]")
        try:
            model_id = validate_model_id(document["model_id"], name=f"catalog.models[{index}].model_id")
        except ValueError as error:
            raise ThreadProtocolError(str(error)) from None
        return cls(
            model_id=model_id,
            authority_model_ref=_text(document["authority_model_ref"], name=f"catalog.models[{index}].authority_model_ref"),
            display_name=_text(document["display_name"], name=f"catalog.models[{index}].display_name"),
            diagram_provider_id=_identifier(document["diagram_provider_id"], name=f"catalog.models[{index}].diagram_provider_id"),
            implementation_family=_identifier(document["implementation_family"], name=f"catalog.models[{index}].implementation_family"),
        )


@dataclass(frozen=True, slots=True)
class ThreadCatalogProfile:
    profile_id: str
    profile_version: str
    display_name: str
    implementation_families: tuple[str, ...]

    @classmethod
    def from_document(cls, value: Any, *, index: int) -> ThreadCatalogProfile:
        document = _document(value, name=f"catalog.profiles[{index}]")
        fields = frozenset({"profile_id", "profile_version", "display_name", "implementation_families"})
        _fields(document, fields, name=f"catalog.profiles[{index}]")
        _required(document, fields, name=f"catalog.profiles[{index}]")
        families = document["implementation_families"]
        if not isinstance(families, list) or len(families) > 32:
            raise ThreadProtocolError(f"catalog.profiles[{index}].implementation_families is invalid")
        version = _text(document["profile_version"], name=f"catalog.profiles[{index}].profile_version")
        if not _VERSION.fullmatch(version):
            raise ThreadProtocolError(f"catalog.profiles[{index}].profile_version is invalid")
        return cls(
            profile_id=_identifier(document["profile_id"], name=f"catalog.profiles[{index}].profile_id"),
            profile_version=version,
            display_name=_text(document["display_name"], name=f"catalog.profiles[{index}].display_name"),
            implementation_families=tuple(
                _identifier(family, name=f"catalog.profiles[{index}].implementation_families[{family_index}]")
                for family_index, family in enumerate(families)
            ),
        )


@dataclass(frozen=True, slots=True)
class ThreadCatalog:
    models: tuple[ThreadCatalogModel, ...]
    profiles: tuple[ThreadCatalogProfile, ...]

    @classmethod
    def from_document(cls, value: Any) -> ThreadCatalog:
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
            tuple(ThreadCatalogModel.from_document(item, index=index) for index, item in enumerate(models)),
            tuple(ThreadCatalogProfile.from_document(item, index=index) for index, item in enumerate(profiles)),
        )


__all__ = ["ThreadCatalog", "ThreadCatalogModel", "ThreadCatalogProfile"]
