from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from types import SimpleNamespace

from capability_agent.application.workspace import ApplicationWorkspace
from grid_agent.compat.v1_0_1_report import PandapowerApplicationReportShell


def test_capstone_report_uses_resolved_runtime_and_admitted_evidence(tmp_path: Path) -> None:
    workspace = ApplicationWorkspace.create(tmp_path, run_id="run-report", binding_ids=("grid",))
    document = {"capability_id": "analysis.powerflow.ac.run", "evidence_type": "analysis_result",
                "facts": {"converged": True}, "provenance": {"engine": "pandapower"}}
    raw = json.dumps(document, ensure_ascii=False, separators=(",", ":")).encode()
    digest = hashlib.sha256(raw).hexdigest()
    reference = f"evidence:sha256:{digest}"
    evidence_path = workspace.domains_path / "grid/evidence/analysis" / f"analysis-evidence-{digest}.json"
    evidence_path.parent.mkdir(parents=True)
    evidence_path.write_bytes(raw)
    context = SimpleNamespace(
        run_id=workspace.run_id, revision=1, state_hash="hash", status="completed",
        core=SimpleNamespace(input={}, runtime={}, turns=[{
            "turn_id": "run-report-t001", "status": "success", "evidence_refs": [reference],
        }]),
        domains={"grid": SimpleNamespace(state={})},
    )

    report = PandapowerApplicationReportShell().render(
        questions=("运行交流潮流。",), answers=("潮流已收敛。",),
        workspace=workspace, context=context,
        runtime={"provider": "deepseek", "model": "deepseek-flash"},
    )

    assert "provider：`deepseek`" in report
    assert "model：`deepseek-flash`" in report
    assert "本题没有可追溯的仿真证据" not in report
    assert "查看证据工件" in report
    assert "证据工件不可用" not in report
    assert f"analysis-evidence-{digest}.json" in report
    href = re.search(r"\[查看证据工件\]\(([^)]+)\)", report)
    assert href is not None
    assert (workspace.output_path / href.group(1)).is_file()


def test_capstone_report_includes_direct_tool_failure_cause(tmp_path: Path) -> None:
    workspace = ApplicationWorkspace.create(tmp_path, run_id="run-failure", binding_ids=("grid",))
    context = SimpleNamespace(
        run_id=workspace.run_id,
        revision=1,
        state_hash="hash",
        status="completed",
        core=SimpleNamespace(
            input={},
            runtime={},
            turns=[{"turn_id": "run-failure-t001", "status": "success"}],
            diagnostics=[
                {
                    "event_type": "tool.failed",
                    "turn_id": "run-failure-t001",
                    "capability_id": "asset.read",
                    "error_code": "model_not_found",
                    "error_message": "registered model is unavailable",
                },
            ],
        ),
        domains={"grid": SimpleNamespace(state={})},
    )

    report = PandapowerApplicationReportShell().render(
        questions=("读取模型。",),
        answers=("模型读取失败。",),
        workspace=workspace,
        context=context,
    )

    assert "失败原因：registered model is unavailable（错误码 model_not_found）" in report


def test_capstone_report_separates_answer_summary_from_formal_answer(tmp_path: Path) -> None:
    workspace = ApplicationWorkspace.create(tmp_path, run_id="run-summary", binding_ids=("grid",))
    context = SimpleNamespace(
        run_id=workspace.run_id,
        revision=1,
        state_hash="hash",
        status="completed",
        core=SimpleNamespace(
            input={},
            runtime={},
            turns=[{
                "turn_id": "run-summary-t001",
                "status": "success",
                "answer_summary": "已完成线路负载核对。",
            }],
            diagnostics=[],
        ),
        domains={"grid": SimpleNamespace(state={})},
    )

    report = PandapowerApplicationReportShell().render(
        questions=("检查线路负载。",),
        answers=("线路负载处于可接受范围。",),
        workspace=workspace,
        context=context,
    )

    assert report.index("### 回答摘要") < report.index("### 正式回答")
    assert "已完成线路负载核对。" in report
