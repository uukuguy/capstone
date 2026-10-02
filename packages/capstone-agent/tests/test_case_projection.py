from __future__ import annotations

import pytest

from capstone_agent.thread_protocol import CaseExecutionSnapshot, ThreadProtocolError


def fixture(status: str, *, execution_id: str = "case_exec_a") -> dict[str, object]:
    return {
        "display_name": "IEEE-39 潮流与线路筛查", "status": status,
        "completed_steps": 1 if status in {"running", "blocked", "cancelled", "completed"} else 0,
        "total_steps": 2, "current_step": 2 if status in {"running", "blocked"} else None,
        "steps": [
            {"ordinal": 1, "title": "打开 IEEE-39 模型", "status": "completed", "duration_ms": 1200,
             "details": {"turn_id": "turn_a", "attempt_id": execution_id, "result_refs": ["result:a"], "evidence_refs": ["evidence:a"]}},
            {"ordinal": 2, "title": "执行交流潮流", "status": "running" if status == "running" else "failed" if status == "blocked" else "pending", "duration_ms": None,
             "details": {"turn_id": "turn_b", "attempt_id": execution_id, "result_refs": [], "evidence_refs": []}},
        ],
        "actions": ([{"action_id": "retry_case_step", "label": "重试此步骤", "enabled": True}, {"action_id": "cancel_case", "label": "停止案例", "enabled": True}] if status == "blocked" else [{"action_id": "cancel_case", "label": "停止案例", "enabled": True}] if status == "running" else [{"action_id": "view_case_details", "label": "查看案例过程", "enabled": True}] if status == "completed" else []),
        "disabled_reasons": ["运行被中断"] if status == "blocked" else [],
    }


@pytest.mark.parametrize("status", ["created", "running", "blocked", "cancelled", "completed"])
def test_case_projection_has_bounded_shared_shape(status: str) -> None:
    projection = CaseExecutionSnapshot.from_document(fixture(status))
    assert projection.display_name == "IEEE-39 潮流与线路筛查"
    assert projection.total_steps == 2
    assert projection.steps[0].title == "打开 IEEE-39 模型"
    assert projection.steps[0].details["turn_id"] == "turn_a"


def test_internal_identity_changes_do_not_change_user_projection() -> None:
    first = CaseExecutionSnapshot.from_document(fixture("blocked", execution_id="case_exec_a"))
    second = CaseExecutionSnapshot.from_document(fixture("blocked", execution_id="case_exec_b"))
    assert first.to_document()["display_name"] == second.to_document()["display_name"]
    assert first.to_document()["steps"][0]["title"] == second.to_document()["steps"][0]["title"]
    assert first.to_document()["steps"][0]["details"] != second.to_document()["steps"][0]["details"]


def test_case_projection_rejects_unknown_or_malformed_public_fields() -> None:
    document = fixture("running")
    document["provider_token"] = "secret"
    with pytest.raises(ThreadProtocolError):
        CaseExecutionSnapshot.from_document(document)


def test_case_projection_bounds_duration_and_case_text() -> None:
    document = fixture("running")
    document["steps"][0]["duration_ms"] = 86_400_001
    with pytest.raises(ThreadProtocolError):
        CaseExecutionSnapshot.from_document(document)

    document = fixture("running")
    document["display_name"] = "x" * 257
    with pytest.raises(ThreadProtocolError):
        CaseExecutionSnapshot.from_document(document)
