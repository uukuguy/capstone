from __future__ import annotations

import pytest

from capstone_agent.thread_catalog import AuthorityThreadModelCatalog
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
