from __future__ import annotations

from capability_agent.application.reporting import GenericReportShell


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
