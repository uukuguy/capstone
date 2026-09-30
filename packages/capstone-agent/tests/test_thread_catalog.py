from __future__ import annotations

import pytest

from capstone_agent.thread_catalog import AuthorityThreadModelCatalog, CompositeThreadModelCatalog
from capstone_agent.thread_service import ThreadModelDescriptor


def test_authority_catalog_normalizes_only_public_model_identity() -> None:
    catalog = AuthorityThreadModelCatalog(
        default_model_id="ieee39",
        resolver=lambda model_id: {
            "model_id": model_id,
            "revision_ref": "revision:sha256:" + "a" * 64,
            "engine": "pandapower",
            "private_network_object": object(),
        },
    )

    assert catalog.resolve(None) == ThreadModelDescriptor(
        model_id="ieee39",
        model_revision="revision:sha256:" + "a" * 64,
        implementation_family="pandapower",
    )


def test_authority_catalog_rejects_missing_or_untrusted_shape() -> None:
    cases = (
        {},
        {"model_id": "ieee39", "revision_ref": "not-a-revision", "engine": "pandapower"},
        {"model_id": "ieee39", "revision_ref": "revision:sha256:" + "a" * 64},
        {"model_id": "ieee39", "revision_ref": "revision:sha256:" + "a" * 64, "engine": ""},
    )
    for result in cases:
        catalog = AuthorityThreadModelCatalog(default_model_id="ieee39", resolver=lambda _: result)
        with pytest.raises(ValueError):
            catalog.resolve("ieee39")


def test_authority_catalog_does_not_allow_authority_to_change_requested_model_id() -> None:
    catalog = AuthorityThreadModelCatalog(
        default_model_id="ieee39",
        resolver=lambda _: {
            "model_id": "case9",
            "revision_ref": "revision:sha256:" + "a" * 64,
            "engine": "pandapower",
        },
    )

    with pytest.raises(ValueError, match="model_id"):
        catalog.resolve("ieee39")


def test_authority_catalog_accepts_real_pypsa_model_id_and_metadata() -> None:
    catalog = AuthorityThreadModelCatalog(
        default_model_id="pypsa-example/scigrid_de",
        model_ids=("pypsa-example/scigrid_de",),
        resolver=lambda model_id: {
            "model_id": model_id,
            "revision_ref": "revision:sha256:" + "b" * 64,
            "implementation_family": "pypsa",
            "authority_model_ref": "pypsa-model:scigrid_de",
            "display_name": "SciGrid-DE",
            "diagram_provider_id": "pypsa-authority",
        },
    )

    resolved = catalog.resolve(None)
    assert resolved.model_id == "pypsa-example/scigrid_de"
    assert resolved.authority_model_ref == "pypsa-model:scigrid_de"
    assert resolved.diagram_provider_id == "pypsa-authority"
    assert catalog.list_model_ids() == ("pypsa-example/scigrid_de",)


def test_composite_catalog_routes_by_registered_model_id_and_rejects_duplicates() -> None:
    def make(model_id: str, family: str, digest: str, ref: str):
        return AuthorityThreadModelCatalog(
            default_model_id=model_id, model_ids=(model_id,),
            resolver=lambda selected: {
                "model_id": selected, "revision_ref": "revision:sha256:" + digest * 64,
                "engine": family, "display_name": selected,
                "authority_model_ref": ref, "diagram_provider_id": family,
            },
        )

    composite = CompositeThreadModelCatalog(default_model_id="ieee39")
    pandapower = make("ieee39", "pandapower", "a", "gridctl:ieee39")
    pypsa = make("pypsa-example/scigrid_de", "pypsa", "b", "pypsa:scigrid_de")
    composite.register(pandapower)
    composite.register(pypsa)
    assert composite.list_model_ids() == ("ieee39", "pypsa-example/scigrid_de")
    assert composite.resolve("pypsa-example/scigrid_de").implementation_family == "pypsa"
    with pytest.raises(ValueError, match="duplicate"):
        composite.register(pandapower)
