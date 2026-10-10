from __future__ import annotations

import json
from pathlib import Path

import pytest


def report(*, findings=None, verdict="ok", errors=0, warnings=0):
    return {"status": "success", "audit_status": verdict,
            "counts": {"errors": errors, "warnings": warnings, "info": 0},
            "findings": findings or []}


def test_structural_operation_has_closed_options_and_explicit_unavailable(grid, context_ref, monkeypatch):
    monkeypatch.delenv("CAPSTONE_POWERMCP_MANAGED_ROOT", raising=False)
    described = grid.call("analysis.operation.describe", {"operation": "diagnostic.structural"})
    assert described["options_schema"] == {"type": "object", "additionalProperties": False, "properties": {}}
    assert described["availability"]["status"] == "unavailable"
    error = grid.call_error("analysis.run", {"context_ref": context_ref, "operation": "diagnostic.structural", "options": {}})
    assert error.code == "analysis_prerequisite_missing"
    assert error.details["availability"] == "unavailable"
    assert list(grid.workspace.results_dir.glob("result-*.json")) == []


def test_completed_audit_errors_are_model_bound_results_with_truthful_provenance(grid, context_ref, monkeypatch):
    from grid_simulator import powermcp_runner
    finding = {"severity": "error", "code": "DISCONNECTED_BUS", "message": "Bus is not supplied.", "element": "bus", "index": 0}
    monkeypatch.setattr(powermcp_runner, "prepared_runtime", lambda: ({"identity": "test"}, Path("/private/unused")))
    monkeypatch.setattr(powermcp_runner, "invoke_snapshot", lambda *args: {"report": report(findings=[finding], verdict="error", errors=1),
        "coverage": powermcp_runner.COVERAGE, "provenance": {"backend": "PowerMCP", "input_sha256": args[2]}})
    before = grid.call("context.get", {"context_ref": context_ref})
    result = grid.call("analysis.run", {"context_ref": context_ref, "operation": "diagnostic.structural", "options": {}})
    assert result["status"] == "succeeded"
    assert result["summary"]["audit_status"] == "error"
    assert result["revision_ref"] == before["revision_ref"]
    assert result["summary"]["coverage"]["topology"] == "checked"
    described = grid.call("result.dataset.describe", {"result_ref": result["result_ref"], "dataset": "result.res_structural_audit"})
    assert all(field["provenance"].startswith(("PowerMCP.", "gridctl.")) for field in described["fields"])
    assert grid.call("context.get", {"context_ref": context_ref}) == before
    assert len(result["evidence_refs"]) == 1


@pytest.mark.parametrize("change", [
    {"counts": {"errors": True, "warnings": 0, "info": 0}},
    {"counts": {"errors": 1, "warnings": 0, "info": 0}},
    {"status": "error"}, {"audit_status": "complete"}, {"unknown": "raw"},
    {"findings": [{"severity": "error", "code": "DISCONNECTED_BUS", "message": "x", "element": "bus", "index": 999999}]},
])
def test_rejects_malformed_or_foreign_findings(change):
    from grid_simulator.powermcp_runner import validate_report
    import pandapower.networks as pn
    with pytest.raises(ValueError):
        validate_report({**report(), **change}, pn.case39())


def test_report_validation_does_not_mutate_model():
    from grid_simulator.powermcp_runner import validate_report
    import pandapower as pp
    import pandapower.networks as pn
    net = pn.case39()
    before = pp.to_json(net)
    validate_report(report(), net)
    assert pp.to_json(net) == before


def test_structural_operation_rejects_model_selected_backend(grid, context_ref):
    error = grid.call_error("analysis.run", {"context_ref": context_ref, "operation": "diagnostic.structural", "options": {"server": "/tmp/other"}})
    assert error.code == "analysis_options_invalid"


def test_backend_failure_does_not_publish_private_error_details(grid, context_ref, monkeypatch):
    from grid_simulator import powermcp_runner
    def fail(*args):
        raise RuntimeError("private-source-path /tmp/private-authority-snapshot")
    monkeypatch.setattr(powermcp_runner, "audit_network", fail)
    error = grid.call_error("analysis.run", {"context_ref": context_ref, "operation": "diagnostic.structural", "options": {}})
    assert error.code == "analysis_failed"
    assert "private-source-path" not in error.model_dump_json()
    assert "pandapower" not in error.message


def test_runner_timeout_cleans_process(tmp_path):
    from grid_simulator.powermcp_runner import run_bounded
    import sys
    with pytest.raises(TimeoutError):
        run_bounded([sys.executable, "-I", "-c", "import time; time.sleep(5)"], cwd=tmp_path, timeout=.05)


def test_runner_rejects_oversized_output(tmp_path):
    from grid_simulator.powermcp_runner import run_bounded
    import sys
    with pytest.raises(ValueError, match="output limit"):
        run_bounded([sys.executable, "-I", "-c", "print('x' * 3000000)"], cwd=tmp_path, timeout=5)


def test_timeout_stops_the_sdk_separate_server_session(tmp_path):
    from grid_simulator.powermcp_runner import run_bounded
    import os
    import signal
    import sys
    import time
    code = "import subprocess,sys,pathlib,time; p=subprocess.Popen([sys.executable,'-I','-c','import time; time.sleep(5)'],start_new_session=True); pathlib.Path('mcp-server.pid').write_text(str(p.pid)); time.sleep(5)"
    started = time.monotonic()
    with pytest.raises(TimeoutError):
        run_bounded([sys.executable, "-I", "-c", code], cwd=tmp_path, timeout=.4)
    pid = int((tmp_path / "mcp-server.pid").read_text())
    try:
        assert time.monotonic() - started < 2
        with pytest.raises(ProcessLookupError):
            os.kill(pid, 0)
    finally:
        try:
            os.killpg(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def test_stale_context_revision_rejected_before_external_call(grid, context_ref, monkeypatch):
    from grid_simulator import powermcp_runner
    calls = []
    monkeypatch.setattr(powermcp_runner, "invoke_snapshot", lambda *args: calls.append(args))
    context_file = next(grid.workspace.contexts_dir.glob("*.json"))
    document = json.loads(context_file.read_text())
    document["revision_ref"] = "revision:sha256:" + "0" * 64
    context_file.write_text(json.dumps(document))
    response = grid._invoke("analysis.run", {"context_ref": context_ref, "operation": "diagnostic.structural", "options": {}})
    assert response.ok is False
    assert not calls


def test_real_mcp_uses_the_registered_snapshot_and_persists_replayable_receipt(grid, context_ref, monkeypatch):
    import os
    if os.environ.get("CAPSTONE_POWERMCP_TESTS") != "1":
        pytest.skip("explicit isolated PowerMCP runtime check")
    root = Path(__file__).resolve().parents[3] / ".grid-agent/runtime/agent-resources"
    monkeypatch.setenv("CAPSTONE_POWERMCP_MANAGED_ROOT", str(root))
    result = grid.call("analysis.run", {"context_ref": context_ref, "operation": "diagnostic.structural", "options": {}})
    assert result["status"] == "succeeded"
    provenance = result["summary"]["provenance"]
    assert provenance["runtime_versions"]["pandapower"] == "3.4.0"
    assert provenance["upstream_commit"] == "63341e67ce6ae5650396ab92b2be7f86e3409da1"
    assert [call["tool"] for call in provenance["calls"]] == ["load_network", "audit_network"]
    assert result["summary"]["coverage"]["topology"] == "checked"
    document = json.loads(next(grid.workspace.results_dir.glob("result-*.json")).read_text())
    assert document["metadata"]["provenance"] == provenance


def test_real_audit_error_on_an_authority_created_model_is_successful(grid, monkeypatch):
    import os
    if os.environ.get("CAPSTONE_POWERMCP_TESTS") != "1":
        pytest.skip("explicit isolated PowerMCP runtime check")
    root = Path(__file__).resolve().parents[3] / ".grid-agent/runtime/agent-resources"
    monkeypatch.setenv("CAPSTONE_POWERMCP_MANAGED_ROOT", str(root))
    created = grid.call("model.create", {"name": "isolated-audit-bus", "elements": [
        {"id": "isolated", "creator": "bus", "arguments": {"vn_kv": 110.0}}]})
    artifact = grid.workspace.model_artifact(created["revision_ref"])
    original = artifact.read_bytes()
    result = grid.call("analysis.run", {"context_ref": created["context_ref"], "operation": "diagnostic.structural", "options": {}})
    assert result["status"] == "succeeded"
    assert result["summary"]["audit_status"] == "error"
    assert result["summary"]["counts"] == {"errors": 1, "warnings": 0, "info": 0}
    assert result["revision_ref"] == created["revision_ref"]
    assert artifact.read_bytes() == original
    query = grid.call("result.dataset.query", {"result_ref": result["result_ref"], "dataset": "result.res_structural_audit", "select": ["code", "element_index", "subject_asset_ref"]})
    assert query["rows"][0]["code"] == "DISCONNECTED_BUS"
    assert query["rows"][0]["element_index"] == 0
    assert query["rows"][0]["subject_asset_ref"]

