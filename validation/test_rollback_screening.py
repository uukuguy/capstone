from validation.deployment.checks import check_answer


def test_sourced_metadata_references_are_not_a_solver_run():
    payload = {"answer": "当前电网概况来自模型元数据。", "result_refs": ["source-result"],
               "evidence_refs": ["source-evidence"]}
    assert check_answer("model-overview", payload) == []


def test_topology_answer_requires_source_not_solver_output():
    assert check_answer("source-backed-answer", {"answer": "已查明支路端点。",
        "evidence_refs": ["topology-source"]}) == []
    assert check_answer("source-backed-answer", {"answer": "已查明支路端点。"}) == ["source_evidence_missing"]


def test_process_prefix_is_detected_without_requiring_one_specific_verb():
    assert "process_prefix" in check_answer("model-overview", {
        "answer": "I'll start by reading the model.## 当前电网概况"})
