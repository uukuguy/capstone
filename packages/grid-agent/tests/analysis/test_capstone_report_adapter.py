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
