from __future__ import annotations

import pytest

from capstone_agent.federated_catalog import (
    FEDERATED_CATALOG_SCHEMA,
    MetadataCapabilityCatalog,
    build_catalog_from_documents,
)
from capstone_agent.thread_catalog import CompositeThreadModelCatalog
from capstone_agent.thread_service import ThreadModelDescriptor


REVISION_A = "revision:sha256:" + "a" * 64
REVISION_B = "revision:sha256:" + "b" * 64


def test_authority_diagram_limit_disables_catalog_selection_and_server_switch() -> None:
    from capstone_agent.thread_service import ThreadCreator
    from test_thread_attempts import _service
    document = _document()
    document["models"].append({**document["models"][0], "model_id": "oversized", "available": False, "unavailable_reason": "diagram_limit"})
    assembly = build_catalog_from_documents((document,), default_model_id="ieee39")
    service = _service()
    service.set_model_catalog(assembly.model_catalog)
    snapshot = service.snapshot("thr_attempts")
    model = next(item for item in service.catalog(snapshot.thread_id)["models"] if item["model_id"] == "oversized")
    assert model["available"] is False and model["unavailable_reason"] == "diagram_limit"
    receipt = service.submit_command({
        "schema": "capstone-command/1", "command_id": "cmd_oversized", "idempotency_key": "idem_oversized",
        "thread_id": snapshot.thread_id, "run_id": snapshot.run.run_id, "kind": "switch_model",
        "expected_event_seq": snapshot.last_event_seq, "payload": {"model_id": "oversized"},
    })
    assert receipt.status == "rejected" and receipt.rejection == "diagram_limit"
    with pytest.raises(ValueError, match="diagram_limit"):
        ThreadCreator(service, assembly.model_catalog).create("oversized")


def _document(
    *,
    family: str = "pandapower",
    model_id: str = "ieee39",
    revision_ref: str = REVISION_A,
    profile_id: str = "pandapower-static-analysis",
    default: bool = True,
) -> dict[str, object]:
    return {
        "schema": FEDERATED_CATALOG_SCHEMA,
        "default_model_id": model_id,
        "models": [
            {
                "model_id": model_id,
                "authority_model_ref": f"authority:{model_id}",
                "display_name": model_id,
                "diagram_provider_id": family,
                "implementation_family": family,
                "revision_ref": revision_ref,
            },
        ],
        "profiles": [
            {
                "profile_id": profile_id,
                "profile_version": "1.0.0",
                "display_name": profile_id,
                "implementation_families": [family],
                "default": default,
            },
        ],
    }


def test_build_catalog_from_documents_routes_models_and_default_profiles() -> None:
    catalog = build_catalog_from_documents(
        (
            _document(),
            _document(
                family="pypsa",
                model_id="regional-six-bus",
                revision_ref=REVISION_B,
                profile_id="pypsa-business-cases",
            ),
        ),
        default_model_id="ieee39",
    )

    assert isinstance(catalog.model_catalog, CompositeThreadModelCatalog)
    assert catalog.model_catalog.resolve(None).model_id == "ieee39"
    pypsa = catalog.model_catalog.resolve("regional-six-bus")
    assert pypsa.implementation_family == "pypsa"
    assert pypsa.authority_model_ref == "authority:regional-six-bus"
    assert catalog.capability_catalog.resolve(pypsa).enabled_profiles == (
        ("pypsa-business-cases", "1.0.0"),
    )
    assert catalog.capability_catalog.profiles_for_family("pandapower")[0].display_name == (
        "pandapower-static-analysis"
    )
    assert catalog.capability_catalog.profiles_for_family("pandapower")[0].descriptor.reference == (
        "pandapower-static-analysis", "1.0.0",
    )


def test_metadata_capability_catalog_rejects_incompatible_explicit_selection() -> None:
    document = _document()
    pypsa = _document(
        family="pypsa",
        model_id="regional-six-bus",
        revision_ref=REVISION_B,
        profile_id="pypsa-business-cases",
    )
    catalog = build_catalog_from_documents(
        (document, pypsa),
        default_model_id="ieee39",
    )
    model = catalog.model_catalog.resolve("ieee39")
    selection = catalog.capability_catalog.selection_for_profiles(
        (("pypsa-business-cases", "1.0.0"),),
    )

    with pytest.raises(ValueError, match="compatible"):
        catalog.capability_catalog.resolve(model, selection)


def test_federated_catalog_rejects_duplicates_missing_defaults_and_invalid_bounds() -> None:
    duplicate = _document()
    with pytest.raises(ValueError, match="duplicate model"):
        build_catalog_from_documents((duplicate, duplicate), default_model_id="ieee39")

    missing_default_model = _document()
    missing_default_model["default_model_id"] = "missing"
    with pytest.raises(ValueError, match="default_model_id"):
        build_catalog_from_documents((missing_default_model,), default_model_id="ieee39")

    missing_profile_default = _document(default=False)
    with pytest.raises(ValueError, match="default profile"):
        build_catalog_from_documents((missing_profile_default,), default_model_id="ieee39")

    oversized = _document()
    oversized["models"] = [*oversized["models"]] * 129  # type: ignore[index]
    with pytest.raises(ValueError, match="too large"):
        build_catalog_from_documents((oversized,), default_model_id="ieee39")

    incompatible = _document()
    incompatible["profiles"] = [
        *incompatible["profiles"],  # type: ignore[index]
        {
            "profile_id": "other-family",
            "profile_version": "1.0.0",
            "display_name": "Other",
            "implementation_families": ["other"],
            "default": False,
        },
    ]
    with pytest.raises(ValueError, match="incompatible"):
        build_catalog_from_documents((incompatible,), default_model_id="ieee39")


def test_metadata_capability_catalog_only_accepts_thread_descriptors() -> None:
    catalog = build_catalog_from_documents((_document(),), default_model_id="ieee39")
    with pytest.raises(TypeError):
        catalog.capability_catalog.resolve(object())  # type: ignore[arg-type]
    assert isinstance(
        catalog.capability_catalog.resolve(
            ThreadModelDescriptor("ieee39", REVISION_A, "pandapower"),
        ),
        object,
    )


def test_federated_catalog_export_shape_is_bounded_and_versioned() -> None:
    catalog = build_catalog_from_documents((_document(),), default_model_id="ieee39")
    assert isinstance(catalog.capability_catalog, MetadataCapabilityCatalog)
    assert catalog.to_document()["schema"] == FEDERATED_CATALOG_SCHEMA
