from __future__ import annotations

import pytest

from capstone_agent.thread_protocol import ThreadProtocolError
from validation.thread.catalog import ThreadCatalog


def _document() -> dict[str, object]:
    return {
        "schema": "capstone-thread-catalog/1",
        "models": [{
            "model_id": "pypsa-example/scigrid_de",
            "authority_model_ref": "pypsa:scigrid_de",
            "display_name": "SciGrid-DE",
            "diagram_provider_id": "pypsa",
            "implementation_family": "pypsa",
        }],
        "profiles": [{
            "profile_id": "pypsa-business-cases",
            "profile_version": "1.0.0",
            "display_name": "PyPSA Business Cases",
            "implementation_families": ["pypsa"],
        }],
    }


def test_catalog_parser_preserves_model_and_profile_identity() -> None:
    catalog = ThreadCatalog.from_document(_document())
    assert catalog.models[0].model_id == "pypsa-example/scigrid_de"
    assert catalog.profiles[0].implementation_families == ("pypsa",)


def test_catalog_parser_rejects_unknown_fields_and_bad_versions() -> None:
    document = _document()
    document["models"] = [{**document["models"][0], "private_authority_object": {}}]  # type: ignore[index]
    with pytest.raises(ThreadProtocolError):
        ThreadCatalog.from_document(document)
    document = _document()
    document["profiles"] = [{**document["profiles"][0], "profile_version": "latest"}]  # type: ignore[index]
    with pytest.raises(ThreadProtocolError):
        ThreadCatalog.from_document(document)
