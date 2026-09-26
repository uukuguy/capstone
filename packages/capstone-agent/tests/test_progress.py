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
