from __future__ import annotations

from capstone_agent.progress import render_progress


def test_progress_renders_tools_and_redacts_credentials() -> None:
    message = render_progress({
        "type": "tool_execution_start", "toolName": "grid_powerflow_run",
        "args": {"network": "case39", "api_key": "secret-value"},
    })

    assert "grid_powerflow_run" in message
    assert "case39" in message
    assert "secret-value" not in message
    assert "bearer-secret" not in render_progress({
        "type": "tool_execution_end", "toolName": "grid_powerflow_run",
        "result": {"detail": "Authorization: Bearer bearer-secret"},
    })


def test_progress_renders_report_checkpoint() -> None:
    message = render_progress({
        "type": "application_report_checkpoint",
        "completed_questions": 2, "total_questions": 3,
        "report_path": "runs/run-1/output/report.md",
    })

    assert "已完成 2 题" in message
    assert "runs/run-1/output/report.md" in message


def test_progress_summarizes_semantic_tool_events_without_hashes_or_rows() -> None:
    digest = "a" * 64
    started = render_progress({
        "type": "tool_execution_start", "toolName": "grid_model_dataset_query",
        "args": {"context_ref": f"context:sha256:{digest}", "dataset": "network.bus",
                 "filters": [{"field": "in_service", "operator": "eq", "value": True}]},
    })
    completed = render_progress({
        "type": "tool_result", "toolName": "grid_model_dataset_query", "ok": True,
        "result": {"dataset_ref": f"dataset:sha256:{digest}", "dataset": "network.bus",
                   "row_count": 39, "returned_row_count": 39,
                   "rows": [{"index": i, "in_service": True} for i in range(39)]},
    })
    assert "grid_model_dataset_query" in started
    assert "network.bus" in started
    assert "工具完成" in completed
    assert "39" in completed
    assert digest not in started + completed
    assert '"rows"' not in completed
    assert len(started) < 150 and len(completed) < 150


def test_progress_reports_prompt_and_assistant_message() -> None:
    assert render_progress({"type": "response", "command": "prompt", "success": True}) == "模型请求已接收"
    assert "模型输出" in render_progress({"type": "assistant_message", "text": "正在核对网络数据"})


def test_progress_summarizes_small_named_counts() -> None:
    message = render_progress({
        "type": "tool_result", "toolName": "grid_context_open", "ok": True,
        "result": {"model": "ieee39", "counts": {"buses": 39, "lines": 35, "transformers": 11}},
    })
    assert "ieee39" in message
    assert "buses=39" in message
    assert "lines=35" in message
