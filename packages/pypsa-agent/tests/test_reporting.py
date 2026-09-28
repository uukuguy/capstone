from __future__ import annotations

from types import SimpleNamespace

from pypsa_agent.reporting import PyPSAApplicationReportShell


def test_pypsa_report_uses_reader_report_sections_and_turn_metadata() -> None:
    context = SimpleNamespace(
        run_id="run-1",
        core=SimpleNamespace(
            runtime={},
            turns=(
                {
                    "turn_id": "run-1-t001",
                    "status": "success",
                    "duration_seconds": 2.5,
                    "result_refs": ["pypsa-result:sha256:" + "a" * 64],
                    "evidence_refs": ["pypsa-evidence:sha256:" + "b" * 64],
                },
            ),
            diagnostics=(
                {
                    "turn_id": "run-1-t001",
                    "tool_name": "pypsa_model_open",
                    "capability_id": "model.open",
                    "ok": True,
                },
            ),
            produced_refs=(),
        ),
    )
    report = PyPSAApplicationReportShell().render(
        questions=("打开区域六母线模型。",),
        answers=("模型已打开。",),
        assurances=("lineage_verified",),
        references=("pypsa-result:sha256:" + "a" * 64,),
        context=context,
        core={"run_id": "run-1", "status": "completed"},
        domains={},
        runtime={"provider": "deepseek", "model": "deepseek-flash"},
    )

    assert report.startswith("# 系统仿真分析报告\n")
    assert "## 1. 打开区域六母线模型。" in report
    assert "### 仿真环境上下文" in report
    assert "### 智能体分析轨迹" in report
    assert "model.open" in report
    assert "总时长：2.50 秒" in report
    assert "## 完整性诊断" in report
    assert "Guarantee scope" not in report


def test_pypsa_report_keeps_formal_answer_and_drops_planning_preamble() -> None:
    report = PyPSAApplicationReportShell().render(
        questions=("分析区域负荷增长。",),
        answers=(
            "I'll inspect the model first. Now I will calculate the result.\n\n"
            "## 区域负荷增长分析\n\n结果显示负荷增长后仍满足约束。",
        ),
        context=SimpleNamespace(
            run_id="run-2",
            core=SimpleNamespace(runtime={}, turns=(), diagnostics=()),
        ),
        core={"run_id": "run-2", "status": "completed"},
    )

    answer = report.split("### 正式回答\n\n", 1)[1].split("\n\n### 仿真环境上下文", 1)[0]
    assert answer.startswith("##### 区域负荷增长分析")
    assert "I'll inspect" not in answer

    bold_report = PyPSAApplicationReportShell().render(
        questions=("检查基准情景。",),
        answers=("I'll inspect the model first.**基准情景分析结果**\n\n结果已核验。",),
    )
    bold_answer = bold_report.split("### 正式回答\n\n", 1)[1].split("\n\n### 仿真环境上下文", 1)[0]
    assert bold_answer.startswith("**基准情景分析结果**")
    assert "I'll inspect" not in bold_answer

    markdown_report = PyPSAApplicationReportShell().render(
        questions=("检查网络结构。",),
        answers=(
            "I'll gather context. Now I'll validate the network.# 网络结构\n\n"
            "## 模型校验\n\n校验通过。",
        ),
    )
    markdown_answer = markdown_report.split("### 正式回答\n\n", 1)[1].split("\n\n### 仿真环境上下文", 1)[0]
    assert markdown_answer.startswith("#### 网络结构")
    assert "##### 模型校验" in markdown_answer


def test_pypsa_report_shows_answer_summary_before_formal_answer() -> None:
    report = PyPSAApplicationReportShell().render(
        questions=("检查基准情景。",),
        answers=("正式回答内容。",),
        context=SimpleNamespace(
            run_id="run-summary",
            core=SimpleNamespace(
                runtime={},
                turns=({"answer_summary": "已完成基准情景核对。", "status": "success"},),
                diagnostics=(),
            ),
        ),
    )

    assert report.index("### 回答摘要") < report.index("### 正式回答")
    assert "已完成基准情景核对。" in report


def test_pypsa_report_includes_direct_tool_failure_cause() -> None:
    report = PyPSAApplicationReportShell().render(
        questions=("执行交流校验。",),
        answers=("线性调度已完成；交流校验未形成证据。",),
        context=SimpleNamespace(
            run_id="run-3",
            core=SimpleNamespace(
                runtime={},
                turns=({"turn_id": "run-3-t001", "status": "success"},),
                diagnostics=(
                    {
                        "event_type": "tool.failed",
                        "turn_id": "run-3-t001",
                        "capability_id": "operations.ac_validate",
                        "error_code": "invalid_dispatch_ref",
                        "error_message": "dispatch result has no bounded schedule",
                    },
                ),
            ),
        ),
    )

    assert "失败原因：dispatch result has no bounded schedule（错误码 invalid_dispatch_ref）" in report
