from __future__ import annotations

import json

from grid_agent.thread_catalog_export import build_catalog_document, main
from grid_simulator.model_catalog import load_model_catalog
from capstone_agent.model_identity import page_id_for_model
from capstone_agent.thread_protocol import ModelContextSnapshot, RunSnapshot, ThreadSnapshot


def test_pandapower_export_covers_authority_catalog_and_has_profile_metadata() -> None:
    document = build_catalog_document()

    assert document["schema"] == "capstone-federated-catalog/1"
    assert document["default_model_id"] == "ieee39"
    assert {model["model_id"] for model in document["models"]} == {
        model["model_id"] for model in load_model_catalog()
    }
    assert "case24_ieee_rts" in {model["model_id"] for model in document["models"]}
    page_ids = set()
    for row in document["models"]:
        page_id = page_id_for_model(row["model_id"])
        assert page_id not in page_ids
        page_ids.add(page_id)
        snapshot = ThreadSnapshot(
            "thr_catalog", RunSnapshot("run_catalog", "open"),
            ModelContextSnapshot("ctx_catalog", row["model_id"], row["revision_ref"], row["implementation_family"], "sel_0"),
            page_id, None, 0, 0,
        )
        assert ThreadSnapshot.from_document(snapshot.to_document()) == snapshot
    model = next(row for row in document["models"] if row["model_id"] == "ieee39")
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
