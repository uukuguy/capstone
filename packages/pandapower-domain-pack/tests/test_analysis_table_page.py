import pytest

from pandapower_domain.analysis_result_projection import project_analysis_table_page


def calculation():
    return {"operation": "powerflow.ac", "context_ref": "context:original", "revision_ref": "revision:original",
            "datasets": {"result.res_line": {
                "fields": [{"name": "index"}, {"name": "loading_percent", "unit": "%"}],
                "rows": [{"index": i * 2, "loading_percent": None if i == 132 else i / 2} for i in range(133)],
            }}}


def test_pages_cover_complete_source_without_changing_identity_units_or_nulls():
    source = calculation()
    first = project_analysis_table_page(source, "res_line", offset=0, limit=128)
    second = project_analysis_table_page(source, "res_line", offset=first["next_offset"], limit=128)
    assert first["total_rows"] == second["total_rows"] == 133
    assert second["next_offset"] is None
    assert len(first["table"]["rows"]) == 128 and len(second["table"]["rows"]) == 5
    assert second["table"]["rows"][0]["row_id"] == "res_line:128"
    assert second["table"]["rows"][-1]["cells"] == {"index": 264, "loading_percent": None}
    assert first["table"]["columns"] == second["table"]["columns"]
    assert second["table"]["columns"][1]["unit"] == "%"
    assert source == calculation()


@pytest.mark.parametrize("offset,limit", [(-1, 32), (True, 32), (0, 129), (0, 0)])
def test_invalid_page_is_rejected(offset, limit):
    with pytest.raises(ValueError):
        project_analysis_table_page(calculation(), "res_line", offset=offset, limit=limit)


def test_unpublished_table_is_not_exposed():
    source = calculation()
    source["datasets"]["private.internal"] = {"rows": [{"secret": "private"}]}
    with pytest.raises(ValueError):
        project_analysis_table_page(source, "private.internal", offset=0, limit=32)


def test_contingency_failure_rows_remain_visible_on_later_pages():
    source = {"capability_id": "analysis.contingency.n_minus_one.run", "scenarios": [
        {"element_kind": "line", "pandapower_index": i, "status": "failed" if i == 130 else "succeeded",
         "converged": False if i == 130 else True} for i in range(131)]}
    page = project_analysis_table_page(source, "contingency_scenarios", offset=128, limit=32)
    assert page["total_rows"] == 131 and page["next_offset"] is None
    assert page["table"]["rows"][-1]["cells"]["status"] == "failed"
    assert page["table"]["rows"][-1]["cells"]["converged"] is False


@pytest.mark.parametrize("wrong_revision", [False, True])
def test_projector_page_checks_saved_result_revision(wrong_revision):
    from types import SimpleNamespace
    from pandapower_domain.result_projection import PandapowerResultProjector
    result_ref = "result:sha256:" + "a" * 64
    context_ref = "context:sha256:" + "b" * 64
    revision = "revision:sha256:" + "c" * 64
    source = {**calculation(), "result_ref": result_ref, "context_ref": context_ref, "revision_ref": revision}
    calls = []
    def verify(ref):
        calls.append(ref)
        assert ref == result_ref
        return SimpleNamespace(document=source)
    authority = SimpleNamespace(verify_result=verify)
    def read():
        return PandapowerResultProjector().project_table_page(authority=authority,
            result_ref=result_ref, expected_revision="revision:sha256:" + "d" * 64 if wrong_revision else revision,
            table_id="res_line", offset=128, limit=32)
    if wrong_revision:
        with pytest.raises(ValueError, match="revision"):
            read()
    else:
        page = read()
        assert page["result_ref"] == result_ref and page["revision_ref"] == revision
        assert len(page["table"]["rows"]) == 5
    assert calls == [result_ref]


def test_existing_powerflow_table_reads_all_original_line_rows():
    from types import SimpleNamespace
    from pandapower_domain.result_projection import PandapowerResultProjector
    result = "result:sha256:" + "a" * 64
    revision = "revision:sha256:" + "b" * 64
    source = {"result_ref": result, "revision_ref": revision, "context_ref": "context:sha256:" + "c" * 64,
        "producer_capability": "analysis.powerflow.ac.run", "branch_results": [
            {"element_kind": "line", "pandapower_index": i, "loading_percent": None if i == 132 else i,
             "pl_mw": 0.0} for i in range(133)]}
    page = PandapowerResultProjector().project_table_page(authority=SimpleNamespace(
        verify_result=lambda _: SimpleNamespace(document=source)), result_ref=result,
        expected_revision=revision, table_id="line_loading", offset=128, limit=32)
    assert page["total_rows"] == 133 and page["next_offset"] is None
    assert page["table"]["rows"][0]["row_id"] == "line:128"
    assert page["table"]["rows"][-1]["cells"]["loading_percent"] is None
    assert page["table"]["rows"][-1]["cells"]["active_loss_mw"] == 0.0
