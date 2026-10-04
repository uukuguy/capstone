from __future__ import annotations

import json

from pypsa_agent.thread_catalog_export import build_catalog_document, main


def test_pypsa_export_contains_all_registered_records() -> None:
    document = build_catalog_document()

    assert document["schema"] == "capstone-federated-catalog/1"
    assert document["default_model_id"] == "regional-six-bus"
    models = document["models"]
    assert len(models) == 21
    assert len({model["model_id"] for model in models}) == 21
    assert all(model["implementation_family"] == "pypsa" for model in models)
    assert all(str(model["revision_ref"]).startswith("revision:sha256:") for model in models)
    assert all(model["diagram_provider_id"] == "pypsa" for model in models)
    assert document["profiles"] == [
        {
            "profile_id": "pypsa-business-cases",
            "profile_version": "1.0.0",
            "display_name": "PyPSA Business Cases",
            "implementation_families": ["pypsa"],
            "default": True,
        },
    ]


def test_pypsa_export_main_writes_one_json_document(capsys) -> None:
    assert main([]) == 0
    output = capsys.readouterr()
    assert output.err == ""
    parsed, end = json.JSONDecoder().raw_decode(output.out)
    assert output.out[end:].strip() == ""
    assert parsed["schema"] == "capstone-federated-catalog/1"
