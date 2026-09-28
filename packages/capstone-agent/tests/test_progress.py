from __future__ import annotations

from capstone_agent.progress import render_progress, summarize_answer


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
    assert render_progress({"type": "assistant_message", "text": "正在核对网络数据"}) == "正在整理本步回答"


def test_summarize_answer_hides_model_process_narration() -> None:
    answer = "I'll inspect the model first. Now I will validate it.\n\n已完成：模型包含 6 个母线。"
    assert summarize_answer(answer, has_references=True) == "已完成：模型包含 6 个母线。"


def test_summarize_answer_always_keeps_process_output_compact() -> None:
    answer = "基于当前潮流结果，负载率最高的三条线路如下：线路 21、线路 11、线路 26。"
    assert summarize_answer(answer, has_references=True) == answer


def test_summarize_answer_uses_lead_sentence_before_markdown_table() -> None:
    answer = "基于当前潮流结果，负载率最高的三条线路如下： | 排名 | 线路 | 负载率 |"
    assert summarize_answer(answer, has_references=True) == "基于当前潮流结果，负载率最高的三条线路如下："


def test_summarize_answer_drops_chinese_planning_prefix_before_heading() -> None:
    answer = "我先查阅已发布指南并打开注册网络。## 网络核对结果\n\n已完成核查。"
    assert summarize_answer(answer, has_references=True) == "网络核对结果 已完成核查。"


def test_progress_summarizes_small_named_counts() -> None:
    message = render_progress({
        "type": "tool_result", "toolName": "grid_context_open", "ok": True,
        "result": {"model": "ieee39", "counts": {"buses": 39, "lines": 35, "transformers": 11}},
    })
    assert "ieee39" in message
    assert "buses=39" in message
    assert "lines=35" in message
