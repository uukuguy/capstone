from __future__ import annotations

import json

from grid_agent.thread_catalog_export import build_catalog_document, main


def test_pandapower_export_is_ieee39_only_and_has_profile_metadata() -> None:
    document = build_catalog_document()

    assert document["schema"] == "capstone-federated-catalog/1"
    assert document["default_model_id"] == "ieee39"
    assert [model["model_id"] for model in document["models"]] == ["ieee39"]
    model = document["models"][0]
    assert model["implementation_family"] == "pandapower"
    assert model["authority_model_ref"] == "gridctl:ieee39"
    assert model["display_name"] == "IEEE 39-bus system"
    assert model["diagram_provider_id"] == "gridctl"
    assert str(model["revision_ref"]).startswith("revision:sha256:")
    assert document["profiles"] == [
        {
            "profile_id": "pandapower-static-analysis",
            "profile_version": "1.0.1",
            "display_name": "Pandapower Static Analysis",
            "implementation_families": ["pandapower"],
            "default": True,
        },
    ]


def test_pandapower_export_main_writes_one_json_document(capsys) -> None:
    assert main([]) == 0
    output = capsys.readouterr()
    assert output.err == ""
    assert list(json.JSONDecoder().raw_decode(output.out)[1:]) == [len(output.out.rstrip())]
