from __future__ import annotations

from capability_agent.application.reporting import (
    GenericReportShell,
    extract_tool_failures,
    format_tool_failure,
)


def test_report_shell_keeps_framework_records_and_delegates_domain_summary() -> None:
    class Presentation:
        def render_report(self, context: object) -> str:
            return "alpha summary"

    report = GenericReportShell().render(
        questions=("first",),
        answers=("answer",),
        trajectories=("trajectory-ref",),
        references=("result-ref",),
        context=object(),
        presentation=Presentation(),
    )

    assert "first" in report
    assert "answer" in report
    assert "trajectory-ref" in report
    assert "result-ref" in report
    assert "alpha summary" in report


def test_tool_failure_formatter_keeps_code_and_direct_cause() -> None:
    failures = extract_tool_failures(
        (
            {
                "event_type": "tool.failed",
                "turn_id": "run-1-t001",
                "capability_id": "operations.ac_validate",
                "error_code": "invalid_dispatch_ref",
                "error_message": "dispatch result has no bounded schedule",
            },
        )
    )

    assert len(failures) == 1
    assert format_tool_failure(failures[0]) == (
        "调用已发布能力 `operations.ac_validate` 失败；"
        "失败原因：dispatch result has no bounded schedule（错误码 invalid_dispatch_ref）"
    )
