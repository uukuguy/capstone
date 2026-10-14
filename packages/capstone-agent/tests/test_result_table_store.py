from dataclasses import replace

import pytest

from capstone_agent.artifacts import MemoryObjectStore
from capstone_agent.result_projection import ResultProjection
from capstone_agent.result_table_store import ResultTableStore


def projection():
    return ResultProjection.from_document({
        "schema": "capstone-result-projection/1.0", "result_id": "result_one",
        "result_ref": "result:sha256:" + "a" * 64, "evidence_refs": ["evidence:sha256:" + "d" * 64],
        "thread_id": "thr_one", "run_id": "run_one", "turn_id": "turn_one", "attempt_id": "attempt_one",
        "model_context_id": "ctx_one", "model_id": "network_one", "model_revision": "revision:sha256:" + "b" * 64,
        "source": {"capability_id": "analysis.run", "domain_pack_id": "pack_one", "implementation_family": "family_one"},
        "status": "completed", "summary": [], "element_refs": [], "overlay": None,
        "tables": [{"table_id": "res_line", "title": "Lines", "columns": [{"column_id": "value", "label": "Value", "unit": "%"}], "rows": []}],
    })


def pages():
    parent = projection()
    for offset, size in [(0, 128), (128, 5)]:
        yield {"result_ref": parent.result_ref, "revision_ref": parent.model_revision,
               "context_ref": "context:sha256:" + "c" * 64, "total_rows": 133,
               "offset": offset, "next_offset": 128 if offset == 0 else None,
               "table": {"table_id": "res_line", "title": "Lines",
                 "columns": [{"column_id": "value", "label": "Value", "unit": "%"}],
                 "rows": [{"row_id": f"row_{i}", "cells": {"value": None if i == 132 else i}} for i in range(offset, offset + size)]}}


def test_other_process_can_read_complete_pages_with_original_grant():
    objects = MemoryObjectStore()
    manifest = ResultTableStore(objects).publish(projection(), "res_line", pages())
    page = ResultTableStore(objects).read(projection(), "res_line", manifest, offset=128)
    assert page["total_rows"] == 133 and page["next_offset"] is None
    assert len(page["table"]["rows"]) == 5
    assert page["table"]["rows"][-1]["cells"]["value"] is None
    with pytest.raises(ValueError, match="identity"):
        ResultTableStore(objects).read(replace(projection(), thread_id="thr_other"), "res_line", manifest, offset=128)


def test_changed_object_bytes_are_rejected():
    objects = MemoryObjectStore()
    manifest = ResultTableStore(objects).publish(projection(), "res_line", pages())
    key = next(k for k, v in objects.contents.items() if b'"offset":128' in v)
    objects.contents[key] += b" "
    with pytest.raises(ValueError, match="integrity"):
        ResultTableStore(objects).read(projection(), "res_line", manifest, offset=128)


def test_noncontiguous_pages_do_not_publish_manifest():
    objects = MemoryObjectStore()
    bad = list(pages())
    bad[1]["offset"] = 129
    with pytest.raises(ValueError):
        ResultTableStore(objects).publish(projection(), "res_line", bad)
    assert not any(b'"schema":"capstone-result-table-manifest/1"' in v for v in objects.contents.values())


def test_pages_from_different_source_contexts_are_rejected():
    objects = MemoryObjectStore()
    bad = list(pages())
    bad[1]["context_ref"] = "context:sha256:" + "e" * 64
    with pytest.raises(ValueError, match="context"):
        ResultTableStore(objects).publish(projection(), "res_line", bad)
