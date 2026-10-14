import pytest

from capstone_agent.result_projection import ResultTable


def document():
    return {"table_id": "res_line", "title": "Lines", "columns": [{"column_id": "value", "label": "Value"}],
            "rows": [{"row_id": "row_one", "cells": {"value": None}}],
            "pagination": {"manifest_ref": "table-manifest:sha256:" + "a" * 64, "total_rows": 133, "page_size": 32}}


def test_pagination_survives_public_roundtrip_without_losing_preview():
    parsed = ResultTable.from_document(document())
    assert parsed.pagination.total_rows == 133
    assert parsed.to_document() == document()


@pytest.mark.parametrize("change", [{"manifest_ref": "https://untrusted.example/data"}, {"page_size": 129},
                                   {"total_rows": True}, {"total_rows": 0}, {"endpoint": "private"}])
def test_invalid_pagination_is_rejected(change):
    value = document()
    value["pagination"].update(change)
    with pytest.raises(ValueError):
        ResultTable.from_document(value)


def test_old_tables_remain_unchanged():
    value = document()
    value.pop("pagination")
    assert ResultTable.from_document(value).to_document() == value
