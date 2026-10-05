"""Neutral, bounded catalog for the federated Capstone Thread application.

Authority adapters export metadata only.  The API process consumes these
documents without importing either simulator stack; family workers later use
the pinned ``implementation_family`` in the Thread context to claim work.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
import json
import re
from typing import Any

from capstone_model_capability_spi import (
    ModelCapabilityDescriptor,
    ModelCapabilitySelection,
)

from .model_identity import validate_model_id
from .thread_catalog import AuthorityThreadModelCatalog, CompositeThreadModelCatalog
from .thread_service import ThreadModelDescriptor


FEDERATED_CATALOG_SCHEMA = "capstone-federated-catalog/1"
_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
_REVISION = re.compile(r"^revision:[a-z0-9_-]+:[a-f0-9]{64}$")
_VERSION = re.compile(r"^[0-9]+(?:\.[0-9]+){1,3}(?:[-+][a-z0-9.-]+)?$")
_MAX_DOCUMENT_BYTES = 512 * 1024
_MAX_MODELS = 128
_MAX_PROFILES = 128


def _identifier(value: Any, name: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"{name} is invalid")
    return value


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 256:
        raise ValueError(f"{name} is invalid")
    return value


def _document(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object")
    return dict(value)


@dataclass(frozen=True, slots=True)
class FederatedModelRecord:
    model_id: str
    authority_model_ref: str
    display_name: str
    diagram_provider_id: str
    implementation_family: str
    revision_ref: str
    available: bool = True
    unavailable_reason: str | None = None

    def descriptor(self) -> ThreadModelDescriptor:
        return ThreadModelDescriptor(
            model_id=self.model_id,
            model_revision=self.revision_ref,
            implementation_family=self.implementation_family,
            authority_model_ref=self.authority_model_ref,
            display_name=self.display_name,
            diagram_provider_id=self.diagram_provider_id,
            available=self.available,
            unavailable_reason=self.unavailable_reason,
        )

    def to_document(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "authority_model_ref": self.authority_model_ref,
            "display_name": self.display_name,
            "diagram_provider_id": self.diagram_provider_id,
            "implementation_family": self.implementation_family,
            "revision_ref": self.revision_ref,
            **({"available": False, "unavailable_reason": self.unavailable_reason or "model_unavailable"} if not self.available else {}),
        }


@dataclass(frozen=True, slots=True)
class FederatedProfileRecord:
    profile_id: str
    profile_version: str
    display_name: str
    implementation_families: tuple[str, ...]
    default: bool

    @property
    def reference(self) -> tuple[str, str]:
        return (self.profile_id, self.profile_version)

    def to_document(self) -> dict[str, object]:
        return {
            "profile_id": self.profile_id,
            "profile_version": self.profile_version,
            "display_name": self.display_name,
            "implementation_families": list(self.implementation_families),
            "default": self.default,
        }


@dataclass(frozen=True, slots=True)
class MetadataCapabilityProfileInfo:
    """Profile metadata shape consumed by the neutral Thread projection."""

    descriptor: ModelCapabilityDescriptor
    display_name: str
    implementation_families: tuple[str, ...]


class MetadataCapabilityCatalog:
    """Capability selection over exported metadata, without executable packs."""

    def __init__(self, profiles: Iterable[FederatedProfileRecord]) -> None:
        records = tuple(profiles)
        self._profiles = {record.reference: record for record in records}
        self._family_defaults: dict[str, ModelCapabilitySelection] = {}
        for record in records:
            if record.default:
                for family in record.implementation_families:
                    if family in self._family_defaults:
                        raise ValueError(f"duplicate default profile for implementation family: {family}")
                    self._family_defaults[family] = ModelCapabilitySelection((record.reference,))

    def profiles_for_family(
        self, implementation_family: str,
    ) -> tuple[MetadataCapabilityProfileInfo, ...]:
        _identifier(implementation_family, "implementation_family")
        return tuple(
            MetadataCapabilityProfileInfo(
                descriptor=ModelCapabilityDescriptor(
                    record.profile_id, record.profile_version,
                ),
                display_name=record.display_name,
                implementation_families=record.implementation_families,
            )
            for record in self._profiles.values()
            if implementation_family in record.implementation_families
        )

    def selection_for_profiles(
        self, references: Iterable[tuple[str, str]],
    ) -> ModelCapabilitySelection:
        selection = ModelCapabilitySelection(tuple(references))
        self._validate(selection, None)
        return selection

    def resolve(
        self, model: ThreadModelDescriptor,
        selection: ModelCapabilitySelection | None = None,
    ) -> ModelCapabilitySelection:
        if not isinstance(model, ThreadModelDescriptor):
            raise TypeError("model must be a ThreadModelDescriptor")
        if selection is not None:
            self._validate(selection, model.implementation_family)
            return selection
        return self._family_defaults.get(
            model.implementation_family, ModelCapabilitySelection.empty(),
        )

    def _validate(
        self, selection: ModelCapabilitySelection, family: str | None,
    ) -> None:
        for reference in selection.enabled_profiles:
            record = self._profiles.get(reference)
            if record is None:
                raise ValueError(f"profile {reference[0]} is not registered")
            if family is not None and family not in record.implementation_families:
                raise ValueError(
                    f"profile {reference[0]} is not compatible with implementation family {family}",
                )

    def to_documents(self) -> list[dict[str, object]]:
        return [record.to_document() for record in self._profiles.values()]


@dataclass(frozen=True, slots=True)
class FederatedThreadCatalog:
    model_catalog: CompositeThreadModelCatalog
    capability_catalog: MetadataCapabilityCatalog
    models: tuple[FederatedModelRecord, ...]
    profiles: tuple[FederatedProfileRecord, ...]
    default_model_id: str

    def to_document(self) -> dict[str, object]:
        return {
            "schema": FEDERATED_CATALOG_SCHEMA,
            "default_model_id": self.default_model_id,
            "models": [record.to_document() for record in self.models],
            "profiles": [record.to_document() for record in self.profiles],
        }


def _parse_model(value: Any, index: int) -> FederatedModelRecord:
    document = _document(value, f"models[{index}]")
    expected = {
        "model_id", "authority_model_ref", "display_name", "diagram_provider_id",
        "implementation_family", "revision_ref",
    }
    if set(document) - (expected | {"available", "unavailable_reason"}) or expected - set(document):
        raise ValueError(f"models[{index}] fields are invalid")
    available = document.get("available", True)
    reason = document.get("unavailable_reason")
    if type(available) is not bool:
        raise ValueError(f"models[{index}].available is invalid")
    if reason is not None:
        reason = _identifier(reason, f"models[{index}].unavailable_reason")
    model_id = validate_model_id(document["model_id"], name=f"models[{index}].model_id")
    revision = document["revision_ref"]
    if not isinstance(revision, str) or not _REVISION.fullmatch(revision):
        raise ValueError(f"models[{index}].revision_ref is invalid")
    return FederatedModelRecord(
        model_id=model_id,
        authority_model_ref=_text(document["authority_model_ref"], f"models[{index}].authority_model_ref"),
        display_name=_text(document["display_name"], f"models[{index}].display_name"),
        diagram_provider_id=_identifier(document["diagram_provider_id"], f"models[{index}].diagram_provider_id"),
        implementation_family=_identifier(document["implementation_family"], f"models[{index}].implementation_family"),
        revision_ref=revision,
        available=available,
        unavailable_reason=reason,
    )


def _parse_profile(value: Any, index: int) -> FederatedProfileRecord:
    document = _document(value, f"profiles[{index}]")
    expected = {"profile_id", "profile_version", "display_name", "implementation_families", "default"}
    if set(document) != expected:
        raise ValueError(f"profiles[{index}] fields are invalid")
    version = document["profile_version"]
    families = document["implementation_families"]
    if not isinstance(version, str) or not _VERSION.fullmatch(version):
        raise ValueError(f"profiles[{index}].profile_version is invalid")
    if not isinstance(families, list) or not families or len(families) > 16:
        raise ValueError(f"profiles[{index}].implementation_families is invalid")
    default = document.get("default", False)
    if type(default) is not bool:
        raise ValueError(f"profiles[{index}].default is invalid")
    normalized = tuple(dict.fromkeys(_identifier(item, f"profiles[{index}].implementation_families") for item in families))
    if len(normalized) != len(families):
        raise ValueError(f"profiles[{index}] contains duplicate implementation families")
    return FederatedProfileRecord(
        profile_id=_identifier(document["profile_id"], f"profiles[{index}].profile_id"),
        profile_version=version,
        display_name=_text(document["display_name"], f"profiles[{index}].display_name"),
        implementation_families=normalized,
        default=default,
    )


def build_catalog_from_documents(
    documents: Iterable[Mapping[str, Any]], *, default_model_id: str | None = None,
    expected_families: Iterable[str] | None = None,
) -> FederatedThreadCatalog:
    """Validate and merge bounded Authority adapter exports."""

    model_records: list[FederatedModelRecord] = []
    profile_records: list[FederatedProfileRecord] = []
    seen_models: set[str] = set()
    seen_profiles: set[tuple[str, str]] = set()
    source_defaults: list[str] = []
    document_count = 0
    expected = tuple(expected_families) if expected_families is not None else None
    for source_index, source in enumerate(documents):
        document_count += 1
        if document_count > 16:
            raise ValueError("federated catalog has too many sources")
        root = _document(source, "federated catalog")
        if set(root) != {"schema", "default_model_id", "models", "profiles"}:
            raise ValueError("federated catalog fields are invalid")
        if root.get("schema") != FEDERATED_CATALOG_SCHEMA:
            raise ValueError("federated catalog schema is invalid")
        expected_family = expected[source_index] if expected is not None and source_index < len(expected) else None
        source_defaults.append(
            validate_model_id(root["default_model_id"], name="default_model_id"),
        )
        models = root.get("models")
        profiles = root.get("profiles")
        if not isinstance(models, list) or not isinstance(profiles, list):
            raise ValueError("federated catalog models/profiles are invalid")
        if len(models) > _MAX_MODELS or len(profiles) > _MAX_PROFILES:
            raise ValueError("federated catalog is too large")
        source_model_ids: set[str] = set()
        for index, item in enumerate(models):
            record = _parse_model(item, index)
            if expected_family is not None and record.implementation_family != expected_family:
                raise ValueError(f"catalog source family mismatch: expected {expected_family}")
            if record.model_id in seen_models:
                raise ValueError(f"duplicate model registration: {record.model_id}")
            seen_models.add(record.model_id)
            source_model_ids.add(record.model_id)
            model_records.append(record)
        if source_defaults[-1] not in source_model_ids:
            raise ValueError("catalog default_model_id is not registered")
        for index, item in enumerate(profiles):
            record = _parse_profile(item, index)
            if expected_family is not None and any(
                family != expected_family for family in record.implementation_families
            ):
                raise ValueError(f"catalog profile family mismatch: expected {expected_family}")
            if record.reference in seen_profiles:
                raise ValueError(f"duplicate profile registration: {record.profile_id}")
            seen_profiles.add(record.reference)
            profile_records.append(record)
    if expected is not None and document_count != len(expected):
        raise ValueError("expected catalog source families do not match sources")
    if len(model_records) > _MAX_MODELS or len(profile_records) > _MAX_PROFILES:
        raise ValueError("federated catalog is too large")
    if default_model_id is None:
        if not source_defaults:
            raise ValueError("federated catalog has no sources")
        default_model_id = source_defaults[0]
    default_model_id = validate_model_id(default_model_id)
    if default_model_id not in seen_models:
        raise ValueError("default_model_id is not registered")
    if not profile_records or not any(record.default for record in profile_records):
        raise ValueError("federated catalog must have a default profile")
    families = {record.implementation_family for record in model_records}
    for profile in profile_records:
        if not families.intersection(profile.implementation_families):
            raise ValueError(f"profile {profile.profile_id} is incompatible with registered models")
    for family in families:
        if not any(record.default and family in record.implementation_families for record in profile_records):
            raise ValueError(f"implementation family has no default profile: {family}")

    records_by_id = {record.model_id: record for record in model_records}
    catalog = CompositeThreadModelCatalog(default_model_id=default_model_id)
    catalog.register(
        AuthorityThreadModelCatalog(
            default_model_id=default_model_id,
            model_ids=tuple(records_by_id),
            resolver=lambda model_id: records_by_id[model_id].to_document(),
        ),
    )
    result = FederatedThreadCatalog(
        model_catalog=catalog,
        capability_catalog=MetadataCapabilityCatalog(profile_records),
        models=tuple(model_records), profiles=tuple(profile_records),
        default_model_id=default_model_id,
    )
    encoded = json.dumps(result.to_document(), ensure_ascii=False, allow_nan=False).encode("utf-8")
    if len(encoded) > _MAX_DOCUMENT_BYTES:
        raise ValueError("federated catalog is too large")
    return result


__all__ = [
    "FEDERATED_CATALOG_SCHEMA", "FederatedThreadCatalog",
    "MetadataCapabilityCatalog", "MetadataCapabilityProfileInfo",
    "build_catalog_from_documents",
]
