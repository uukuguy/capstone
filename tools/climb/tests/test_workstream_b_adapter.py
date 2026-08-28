#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
TRAIN = ROOT / "tools/climb/train.sh"
EVAL = ROOT / "tools/climb/eval-local.sh"
DECISION = ROOT / "tools/climb/decision-gate.py"
SYNC = ROOT / "tools/climb/sync-cycle.py"
REGEN = ROOT / "tools/climb/regen-tree.py"
CHECK_TARGET = ROOT / "tools/climb/check-target.py"
GATE_RECEIPT = ROOT / "tools/climb/gate-receipt.py"

EXPECTED_WEIGHTS = {
    "kernel_independence": 25.0,
    "domain_ownership": 20.0,
    "pi_tool_generalization": 15.0,
    "application_thinness": 10.0,
    "distribution_integrity": 10.0,
    "product_compatibility": 20.0,
}


def _write_temp_state(tmp_path: Path, *, phase: str = "B-H001 implementation") -> tuple[Path, Path]:
    state_dir = tmp_path / "state"
    artifact_dir = tmp_path / "artifacts"
    gate_dir = tmp_path / "gates"
    kernel_root = tmp_path / "packages" / "capability-agent-kernel"
    state_dir.mkdir()
    artifact_dir.mkdir()
    gate_dir.mkdir()
    kernel_root.mkdir(parents=True)
    (gate_dir / "kernel-ok.py").write_text("print('kernel gate ok')\n", encoding="utf-8")
    (gate_dir / "should-not-run.py").write_text(
        "raise SystemExit('future hypothesis gate should not run')\n",
        encoding="utf-8",
    )
    (gate_dir / "append-marker.py").write_text(
        "from pathlib import Path\n"
        "import sys\n"
        "Path(sys.argv[1]).write_text('ran\\n', encoding='utf-8')\n",
        encoding="utf-8",
    )
    (state_dir / "config.yaml").write_text(
        json.dumps(
            {
                "session": "2026-08-28-workstream-b-package-extraction",
                "score_name": "workstream_b_package_extraction_score",
                "score_direction": "max",
                "subscores": list(EXPECTED_WEIGHTS),
                "score_weights": EXPECTED_WEIGHTS,
                "push_mode": "local-gate",
                "state_dir": str(state_dir),
                "artifact_dir": str(artifact_dir),
                "run_tag_marker": "-climb-b-",
                "paradigm_field": "package_extraction_boundary",
                "score_gates": {
                    "kernel_independence": {
                        "hypothesis_id": "B-H001",
                        "required_paths": [str(kernel_root)],
                        "command": [sys.executable, str(gate_dir / "kernel-ok.py")],
                    },
                    "domain_ownership": {
                        "hypothesis_id": "B-H004",
                        "required_paths": [str(tmp_path / "packages" / "pandapower-domain-pack")],
                        "command": [sys.executable, str(gate_dir / "should-not-run.py")],
                    },
                    "pi_tool_generalization": {
                        "hypothesis_id": "B-H003",
                        "required_paths": [str(tmp_path / "packages" / "pi-capability-tools")],
                        "command": [sys.executable, str(gate_dir / "should-not-run.py")],
                    },
                    "application_thinness": {
                        "hypothesis_id": "B-H005",
                        "required_paths": [str(tmp_path / "not-yet" / "application")],
                        "command": [sys.executable, str(gate_dir / "should-not-run.py")],
                    },
                    "distribution_integrity": {
                        "hypothesis_id": "B-H005",
                        "required_paths": [str(tmp_path / "not-yet" / "dist")],
                        "command": [sys.executable, str(gate_dir / "should-not-run.py")],
                    },
                    "product_compatibility": {
                        "hypothesis_id": "B-H005",
                        "required_paths": [str(tmp_path / "not-yet" / "product")],
                        "command": [sys.executable, str(gate_dir / "should-not-run.py")],
                    },
                },
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (state_dir / "hypotheses.yaml").write_text(
        json.dumps(
            {
                "hypotheses": [
                    {
                        "id": "B-H001",
                        "description": "artifact and import characterization can define a safe extraction baseline without changing behavior",
                        "parent_paradigm": "package-extraction-baseline",
                        "expected_lift": "kernel independence evidence",
                        "cost_h": 1,
                        "ranking": 1.0,
                        "status": "pending",
                        "owned_score_keys": ["kernel_independence"],
                        "focused_gate": "kernel_independence",
                        "results": [],
                    },
                    {
                        "id": "B-H002",
                        "description": "the approved neutral slice can move into capability-agent-kernel with compatibility imports preserving callers",
                        "parent_paradigm": "python-kernel-extraction",
                        "expected_lift": "neutral kernel package exists",
                        "cost_h": 4,
                        "ranking": 0.9,
                        "status": "pending",
                        "owned_score_keys": [],
                        "results": [],
                    },
                    {
                        "id": "B-H005",
                        "description": "grid-agent can assemble the extracted artifacts and remain behavior-compatible under clean installation and all deterministic gates",
                        "parent_paradigm": "application-composition",
                        "expected_lift": "application thinness, distribution integrity, and product compatibility",
                        "cost_h": 8,
                        "ranking": 0.8,
                        "status": "pending",
                        "owned_score_keys": [
                            "application_thinness",
                            "distribution_integrity",
                            "product_compatibility",
                        ],
                        "focused_gate": "product_compatibility",
                        "results": [],
                    },
                ],
                "events": [],
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (state_dir / "runs.csv").write_text(
        "run_id,cycle,session,hypothesis_id,paradigm,parent_run,pushed_at,lb_landed_at,local_score,local_kernel_independence,local_domain_ownership,local_pi_tool_generalization,local_application_thinness,local_distribution_integrity,local_product_compatibility,online_score,gap,push_decision,decision_reason,verdict,train_cost_h,manifest_path\n",
        encoding="utf-8",
    )
    (state_dir / "session-state.json").write_text(
        json.dumps(
            {
                "session": "2026-08-28-workstream-b-package-extraction",
                "phase": phase,
                "last_cycle": 0,
                "next_hypothesis": "B-H001",
                "in_flight": None,
                "next_action": "Execute B-H001 through the deterministic local gate.",
                "falsified_routes": [],
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (state_dir / "session-target.md").write_text(
        "# Climb session target\n\n"
        "Workstream B closes only when every package extraction gate passes.\n\n"
        "<!-- TARGET-BEGIN (machine-readable, check-target.py reads) -->\n"
        "target_metric: local\n"
        "target_value: 100\n"
        "<!-- TARGET-END -->\n",
        encoding="utf-8",
    )
    (state_dir / "calibration.json").write_text('{"schema_version": 1, "paradigms": {}}\n', encoding="utf-8")
    (state_dir / "pending-lb.json").write_text('{"pending": [], "landed_this_session": []}\n', encoding="utf-8")
    (state_dir / "adjudicator-log.md").write_text("# Climb adjudicator log\n", encoding="utf-8")
    (state_dir / "research-tree.json").write_text("{}\n", encoding="utf-8")
    (state_dir / "research-tree.md").write_text("", encoding="utf-8")
    return state_dir, artifact_dir


def _append_run(
    state_dir: Path,
    artifact_dir: Path,
    *,
    run_id: str,
    cycle: int,
    hypothesis_id: str,
    gate_key: str,
    weight: float,
    command: list[str],
) -> None:
    run_dir = artifact_dir / run_id
    run_dir.mkdir(parents=True)
    local_eval = {
        "focused_gate": gate_key,
        "gate_evidence": {
            gate_key: {
                "artifact_path": f"{run_id}/gate-output-{gate_key}.json",
                "command": command,
                "returncode": 0,
                "status": "passed",
            }
        },
        "hypothesis_gate_passed": True,
        "per_task": {key: 0.0 for key in EXPECTED_WEIGHTS},
        "release_ready": False,
        "total": weight,
    }
    local_eval["per_task"][gate_key] = weight
    (run_dir / "local-eval.json").write_text(json.dumps(local_eval, sort_keys=True) + "\n", encoding="utf-8")
    (run_dir / "manifest.json").write_text(
        json.dumps(
            {
                "hypothesis_id": hypothesis_id,
                "kind": "workstream-b-package-extraction-gate",
                "score_evidence": [
                    {
                        "artifact_path": f"{run_id}/local-eval.json",
                        "command": command,
                        "score_key": gate_key,
                        "source": "local-eval",
                    }
                ],
                "session": "2026-08-28-workstream-b-package-extraction",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    document = json.loads((state_dir / "hypotheses.yaml").read_text(encoding="utf-8"))
    document["events"].append(
        {
            "gate_evidence": local_eval["gate_evidence"],
            "hypothesis_id": hypothesis_id,
            "local_score": weight,
            "per_task": local_eval["per_task"],
            "recorded_at": f"2026-08-28T0{cycle}:00:00+00:00",
            "run_id": run_id,
            "status": "confirmed",
            "verdict": "confirmed: owned deterministic Workstream B gate passed",
        }
    )
    (state_dir / "hypotheses.yaml").write_text(json.dumps(document, sort_keys=True) + "\n", encoding="utf-8")
    with (state_dir / "runs.csv").open("a", encoding="utf-8") as handle:
        handle.write(
            f"{run_id},{cycle},2026-08-28-workstream-b-package-extraction,{hypothesis_id},test-paradigm,,,,"
            f"{weight},{local_eval['per_task']['kernel_independence']},{local_eval['per_task']['domain_ownership']},"
            f"{local_eval['per_task']['pi_tool_generalization']},{local_eval['per_task']['application_thinness']},"
            f"{local_eval['per_task']['distribution_integrity']},{local_eval['per_task']['product_compatibility']},"
            ",,CONTINUE,matrix incomplete; advance next implementation hypothesis,"
            "confirmed: owned deterministic Workstream B gate passed,0.0,"
            f"{run_id}/manifest.json\n"
        )


def _write_receipt(
    state_dir: Path,
    *,
    gate_key: str,
    command: list[str],
    source_commit: str = "test-source",
    returncode: int = 0,
) -> Path:
    receipt_dir = state_dir / "receipts"
    receipt_dir.mkdir(exist_ok=True)
    receipt_path = receipt_dir / f"{gate_key}.json"
    output_path = receipt_dir / f"{gate_key}.output.txt"
    output_path.write_text(f"{gate_key} output\n", encoding="utf-8")
    receipt_path.write_text(
        json.dumps(
            {
                "artifact_path": f"receipts/{gate_key}.json",
                "command": command,
                "gate_key": gate_key,
                "output_artifact_path": f"receipts/{gate_key}.output.txt",
                "returncode": returncode,
                "source_commit": source_commit,
                "status": "passed" if returncode == 0 else "failed",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    config_path = state_dir / "config.yaml"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["score_gates"][gate_key]["receipt_path"] = str(receipt_path)
    config["score_gates"][gate_key]["receipt_required"] = True
    config_path.write_text(json.dumps(config, sort_keys=True) + "\n", encoding="utf-8")
    return receipt_path


def _env(state_dir: Path, artifact_dir: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["CLIMB_STATE_DIR"] = str(state_dir)
    env["CLIMB_ARTIFACT_DIR"] = str(artifact_dir)
    return env


def _run(command: list[str | Path], *, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(part) for part in command],
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def test_train_writes_workstream_b_manifest_in_temp_artifact_dir(tmp_path: Path) -> None:
    state_dir, artifact_dir = _write_temp_state(tmp_path)

    result = _run([TRAIN, "B-H001"], cwd=tmp_path, env=_env(state_dir, artifact_dir))

    assert result.returncode == 0, result.stderr
    run_dir = Path(result.stdout.strip())
    try:
        assert run_dir.parent == artifact_dir
        manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["session"] == "2026-08-28-workstream-b-package-extraction"
        assert manifest["hypothesis_id"] == "B-H001"
        assert manifest["kind"] == "workstream-b-package-extraction-gate"
    finally:
        if run_dir.is_dir() and artifact_dir in run_dir.parents:
            shutil.rmtree(run_dir)


def test_eval_scores_workstream_b_weights_and_skips_future_package_roots(tmp_path: Path) -> None:
    state_dir, artifact_dir = _write_temp_state(tmp_path)
    run_dir = artifact_dir / "cycle-b-h001"
    run_dir.mkdir()
    (run_dir / "manifest.json").write_text(
        json.dumps({"hypothesis_id": "B-H001", "session": "2026-08-28-workstream-b-package-extraction"}) + "\n",
        encoding="utf-8",
    )

    result = _run([EVAL, run_dir], cwd=tmp_path, env=_env(state_dir, artifact_dir))

    assert result.returncode == 0, result.stderr
    score = json.loads(result.stdout)
    assert score["per_task"] == {
        "kernel_independence": 25.0,
        "domain_ownership": 0.0,
        "pi_tool_generalization": 0.0,
        "application_thinness": 0.0,
        "distribution_integrity": 0.0,
        "product_compatibility": 0.0,
    }
    assert set(score["per_task"]) == set(EXPECTED_WEIGHTS)
    assert score["total"] == sum(score["per_task"].values())
    assert score["hypothesis_gate_passed"] is True
    assert score["release_ready"] is False
    assert score["gate_evidence"]["kernel_independence"]["status"] == "passed"
    assert score["gate_evidence"]["domain_ownership"]["status"] == "missing"


def test_eval_runs_only_the_manifest_hypothesis_focused_gate(tmp_path: Path) -> None:
    state_dir, artifact_dir = _write_temp_state(tmp_path)
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    required_root = tmp_path / "available"
    required_root.mkdir()
    config_path = state_dir / "config.yaml"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    for score_key in ("application_thinness", "distribution_integrity", "product_compatibility"):
        config["score_gates"][score_key]["required_paths"] = [str(required_root)]
    config["score_gates"]["application_thinness"]["command"] = [
        sys.executable,
        str(tmp_path / "gates" / "append-marker.py"),
        str(marker_dir / "application"),
    ]
    config["score_gates"]["distribution_integrity"]["command"] = [
        sys.executable,
        str(tmp_path / "gates" / "append-marker.py"),
        str(marker_dir / "distribution"),
    ]
    config["score_gates"]["product_compatibility"]["command"] = [
        sys.executable,
        str(tmp_path / "gates" / "append-marker.py"),
        str(marker_dir / "product"),
    ]
    config_path.write_text(json.dumps(config, sort_keys=True) + "\n", encoding="utf-8")
    run_dir = artifact_dir / "cycle-b-h005"
    run_dir.mkdir()
    (run_dir / "manifest.json").write_text(
        json.dumps({"hypothesis_id": "B-H005", "session": "2026-08-28-workstream-b-package-extraction"}) + "\n",
        encoding="utf-8",
    )

    result = _run([EVAL, run_dir], cwd=tmp_path, env=_env(state_dir, artifact_dir))

    assert result.returncode == 0, result.stderr
    score = json.loads(result.stdout)
    assert score["per_task"]["product_compatibility"] == 20.0
    assert score["per_task"]["application_thinness"] == 0.0
    assert score["per_task"]["distribution_integrity"] == 0.0
    assert score["total"] == 20.0
    assert score["hypothesis_gate_passed"] is True
    assert score["gate_evidence"]["product_compatibility"]["status"] == "passed"
    assert score["gate_evidence"]["application_thinness"]["status"] == "not-focused"
    assert score["gate_evidence"]["distribution_integrity"]["status"] == "not-focused"
    assert (marker_dir / "product").is_file()
    assert not (marker_dir / "application").exists()
    assert not (marker_dir / "distribution").exists()


def test_eval_b_h005_scores_valid_cumulative_evidence_and_receipts(tmp_path: Path) -> None:
    state_dir, artifact_dir = _write_temp_state(tmp_path)
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    required_root = tmp_path / "available"
    required_root.mkdir()
    config_path = state_dir / "config.yaml"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    for score_key in ("application_thinness", "distribution_integrity", "product_compatibility"):
        config["score_gates"][score_key]["required_paths"] = [str(required_root)]
    config["score_gates"]["application_thinness"]["command"] = [
        sys.executable,
        str(tmp_path / "gates" / "append-marker.py"),
        str(marker_dir / "application"),
    ]
    config["score_gates"]["distribution_integrity"]["command"] = [
        sys.executable,
        str(tmp_path / "gates" / "append-marker.py"),
        str(marker_dir / "distribution"),
    ]
    config["score_gates"]["product_compatibility"]["command"] = [
        sys.executable,
        str(tmp_path / "gates" / "append-marker.py"),
        str(marker_dir / "product"),
    ]
    config_path.write_text(json.dumps(config, sort_keys=True) + "\n", encoding="utf-8")
    _append_run(
        state_dir,
        artifact_dir,
        run_id="cycle-b-h002",
        cycle=1,
        hypothesis_id="B-H002",
        gate_key="kernel_independence",
        weight=25.0,
        command=["kernel", "gate"],
    )
    _append_run(
        state_dir,
        artifact_dir,
        run_id="cycle-b-h003",
        cycle=2,
        hypothesis_id="B-H003",
        gate_key="pi_tool_generalization",
        weight=15.0,
        command=["pi", "gate"],
    )
    _append_run(
        state_dir,
        artifact_dir,
        run_id="cycle-b-h004",
        cycle=3,
        hypothesis_id="B-H004",
        gate_key="domain_ownership",
        weight=20.0,
        command=["domain", "gate"],
    )
    _write_receipt(
        state_dir,
        gate_key="application_thinness",
        command=config["score_gates"]["application_thinness"]["command"],
    )
    _write_receipt(
        state_dir,
        gate_key="distribution_integrity",
        command=config["score_gates"]["distribution_integrity"]["command"],
    )
    run_dir = artifact_dir / "cycle-b-h005"
    run_dir.mkdir()
    (run_dir / "manifest.json").write_text(
        json.dumps({"hypothesis_id": "B-H005", "session": "2026-08-28-workstream-b-package-extraction"}) + "\n",
        encoding="utf-8",
    )
    env = _env(state_dir, artifact_dir)
    env["CLIMB_SOURCE_COMMIT"] = "test-source"

    result = _run([EVAL, run_dir], cwd=tmp_path, env=env)

    assert result.returncode == 0, result.stderr
    score = json.loads(result.stdout)
    assert score["per_task"] == EXPECTED_WEIGHTS
    assert score["total"] == 100.0
    assert score["release_ready"] is True
    assert score["release_blockers"] == []
    assert score["gate_evidence"]["kernel_independence"]["status"] == "carried-forward"
    assert score["gate_evidence"]["kernel_independence"]["source_run_id"] == "cycle-b-h002"
    assert score["gate_evidence"]["domain_ownership"]["status"] == "carried-forward"
    assert score["gate_evidence"]["pi_tool_generalization"]["status"] == "carried-forward"
    assert score["gate_evidence"]["application_thinness"]["status"] == "receipt-passed"
    assert score["gate_evidence"]["distribution_integrity"]["status"] == "receipt-passed"
    assert score["gate_evidence"]["product_compatibility"]["status"] == "passed"
    assert (marker_dir / "product").is_file()
    assert not (marker_dir / "application").exists()
    assert not (marker_dir / "distribution").exists()


def test_eval_b_h005_zeroes_missing_failed_and_stale_receipts(tmp_path: Path) -> None:
    state_dir, artifact_dir = _write_temp_state(tmp_path)
    required_root = tmp_path / "available"
    required_root.mkdir()
    config_path = state_dir / "config.yaml"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    for score_key in ("application_thinness", "distribution_integrity", "product_compatibility"):
        config["score_gates"][score_key]["required_paths"] = [str(required_root)]
    config["score_gates"]["product_compatibility"]["command"] = [
        sys.executable,
        str(tmp_path / "gates" / "kernel-ok.py"),
    ]
    config_path.write_text(json.dumps(config, sort_keys=True) + "\n", encoding="utf-8")
    _append_run(
        state_dir,
        artifact_dir,
        run_id="cycle-b-h002",
        cycle=1,
        hypothesis_id="B-H002",
        gate_key="kernel_independence",
        weight=25.0,
        command=["kernel", "gate"],
    )
    _append_run(
        state_dir,
        artifact_dir,
        run_id="cycle-b-h003",
        cycle=2,
        hypothesis_id="B-H003",
        gate_key="pi_tool_generalization",
        weight=15.0,
        command=["pi", "gate"],
    )
    _append_run(
        state_dir,
        artifact_dir,
        run_id="cycle-b-h004",
        cycle=3,
        hypothesis_id="B-H004",
        gate_key="domain_ownership",
        weight=20.0,
        command=["domain", "gate"],
    )
    _write_receipt(
        state_dir,
        gate_key="distribution_integrity",
        command=config["score_gates"]["distribution_integrity"]["command"],
        returncode=1,
    )
    stale_receipt = _write_receipt(
        state_dir,
        gate_key="application_thinness",
        command=config["score_gates"]["application_thinness"]["command"],
        source_commit="old-source",
    )
    stale_payload = json.loads(stale_receipt.read_text(encoding="utf-8"))
    assert stale_payload["source_commit"] == "old-source"
    run_dir = artifact_dir / "cycle-b-h005"
    run_dir.mkdir()
    (run_dir / "manifest.json").write_text(
        json.dumps({"hypothesis_id": "B-H005", "session": "2026-08-28-workstream-b-package-extraction"}) + "\n",
        encoding="utf-8",
    )
    env = _env(state_dir, artifact_dir)
    env["CLIMB_SOURCE_COMMIT"] = "test-source"

    result = _run([EVAL, run_dir], cwd=tmp_path, env=env)

    assert result.returncode == 0, result.stderr
    score = json.loads(result.stdout)
    assert score["per_task"]["application_thinness"] == 0.0
    assert score["per_task"]["distribution_integrity"] == 0.0
    assert score["per_task"]["product_compatibility"] == 20.0
    assert score["total"] == 80.0
    assert score["release_ready"] is False
    assert score["gate_evidence"]["application_thinness"]["status"] == "stale-receipt"
    assert score["gate_evidence"]["distribution_integrity"]["status"] == "failed-receipt"
    assert "application_thinness: stale-receipt" in score["release_blockers"]
    assert "distribution_integrity: failed-receipt" in score["release_blockers"]


def test_eval_b_h005_zeroes_missing_receipt(tmp_path: Path) -> None:
    state_dir, artifact_dir = _write_temp_state(tmp_path)
    required_root = tmp_path / "available"
    required_root.mkdir()
    config_path = state_dir / "config.yaml"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    for score_key in ("application_thinness", "distribution_integrity", "product_compatibility"):
        config["score_gates"][score_key]["required_paths"] = [str(required_root)]
    config["score_gates"]["application_thinness"]["receipt_required"] = True
    config["score_gates"]["application_thinness"]["receipt_path"] = str(state_dir / "receipts/missing.json")
    config["score_gates"]["product_compatibility"]["command"] = [
        sys.executable,
        str(tmp_path / "gates" / "kernel-ok.py"),
    ]
    config_path.write_text(json.dumps(config, sort_keys=True) + "\n", encoding="utf-8")
    run_dir = artifact_dir / "cycle-b-h005"
    run_dir.mkdir()
    (run_dir / "manifest.json").write_text(
        json.dumps({"hypothesis_id": "B-H005", "session": "2026-08-28-workstream-b-package-extraction"}) + "\n",
        encoding="utf-8",
    )

    result = _run([EVAL, run_dir], cwd=tmp_path, env=_env(state_dir, artifact_dir))

    assert result.returncode == 0, result.stderr
    score = json.loads(result.stdout)
    assert score["per_task"]["application_thinness"] == 0.0
    assert score["gate_evidence"]["application_thinness"]["status"] == "missing-receipt"
    assert "application_thinness: missing-receipt" in score["release_blockers"]


def test_gate_receipt_records_exact_command_returncode_commit_and_output_path(tmp_path: Path) -> None:
    state_dir, artifact_dir = _write_temp_state(tmp_path)
    output_marker = tmp_path / "receipt-command-ran"
    config_path = state_dir / "config.yaml"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["score_gates"]["application_thinness"]["command"] = [
        sys.executable,
        str(tmp_path / "gates" / "append-marker.py"),
        str(output_marker),
    ]
    config["score_gates"]["application_thinness"]["required_paths"] = [str(tmp_path / "gates" / "append-marker.py")]
    config_path.write_text(json.dumps(config, sort_keys=True) + "\n", encoding="utf-8")
    env = _env(state_dir, artifact_dir)
    env["CLIMB_SOURCE_COMMIT"] = "test-source"

    result = _run([GATE_RECEIPT, "application_thinness"], cwd=tmp_path, env=env)

    assert result.returncode == 0, result.stderr
    receipt_path = Path(result.stdout.strip())
    assert receipt_path.is_file()
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["gate_key"] == "application_thinness"
    assert receipt["command"] == config["score_gates"]["application_thinness"]["command"]
    assert receipt["returncode"] == 0
    assert receipt["source_commit"] == "test-source"
    assert receipt["artifact_path"] == "gate-receipts/application_thinness.json"
    assert receipt["output_artifact_path"] == "gate-receipts/application_thinness.output.txt"
    assert (artifact_dir / "gate-receipts/application_thinness.output.txt").is_file()
    assert output_marker.is_file()


def test_decision_gate_pushes_only_release_ready_scores(tmp_path: Path) -> None:
    below_target = tmp_path / "below-target.json"
    below_target.write_text(
        json.dumps({"total": 25.0, "per_task": {"kernel_independence": 25.0}, "release_ready": False}) + "\n",
        encoding="utf-8",
    )
    ready = tmp_path / "ready.json"
    ready.write_text(
        json.dumps({"total": 100.0, "per_task": EXPECTED_WEIGHTS, "release_ready": True}) + "\n",
        encoding="utf-8",
    )

    continue_result = _run([DECISION, "--local-eval-json", below_target], cwd=tmp_path, env=os.environ.copy())
    push_result = _run([DECISION, "--local-eval-json", ready], cwd=tmp_path, env=os.environ.copy())

    assert continue_result.returncode == 0, continue_result.stderr
    assert push_result.returncode == 0, push_result.stderr
    assert json.loads(continue_result.stdout)["decision"] == "CONTINUE"
    assert json.loads(push_result.stdout)["decision"] == "PUSH"


def test_sync_confirms_owned_gate_below_release_target(tmp_path: Path) -> None:
    state_dir, artifact_dir = _write_temp_state(tmp_path)
    run_dir = artifact_dir / "cycle-b-h001"
    run_dir.mkdir()
    (run_dir / "manifest.json").write_text(
        json.dumps({"hypothesis_id": "B-H001", "session": "2026-08-28-workstream-b-package-extraction"}) + "\n",
        encoding="utf-8",
    )
    eval_json = run_dir / "local-eval.json"
    eval_json.write_text(
        json.dumps(
            {
                "total": 25.0,
                "per_task": {
                    "kernel_independence": 25.0,
                    "domain_ownership": 0.0,
                    "pi_tool_generalization": 0.0,
                    "application_thinness": 0.0,
                    "distribution_integrity": 0.0,
                    "product_compatibility": 0.0,
                },
                "release_ready": False,
                "hypothesis_gate_passed": True,
                "gate_evidence": {"kernel_independence": {"status": "passed"}},
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    decision_json = run_dir / "decision.json"
    decision_json.write_text(
        json.dumps({"decision": "CONTINUE", "reason": "release not ready"}, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    result = _run([SYNC, "B-H001", run_dir, eval_json, decision_json], cwd=tmp_path, env=_env(state_dir, artifact_dir))

    assert result.returncode == 0, result.stderr
    hypotheses = json.loads((state_dir / "hypotheses.yaml").read_text(encoding="utf-8"))
    assert hypotheses["events"][0]["status"] == "confirmed"
    rows = (state_dir / "runs.csv").read_text(encoding="utf-8")
    assert "2026-08-28-workstream-b-package-extraction" in rows
    assert "25.0" in rows


def test_sync_uses_focused_gate_and_records_stable_manifest_path(tmp_path: Path) -> None:
    state_dir, artifact_dir = _write_temp_state(tmp_path)
    run_dir = artifact_dir / "cycle-b-h005"
    run_dir.mkdir()
    (run_dir / "manifest.json").write_text(
        json.dumps({"hypothesis_id": "B-H005", "session": "2026-08-28-workstream-b-package-extraction"}) + "\n",
        encoding="utf-8",
    )
    eval_json = run_dir / "local-eval.json"
    eval_json.write_text(
        json.dumps(
            {
                "total": 20.0,
                "per_task": {
                    "kernel_independence": 0.0,
                    "domain_ownership": 0.0,
                    "pi_tool_generalization": 0.0,
                    "application_thinness": 0.0,
                    "distribution_integrity": 0.0,
                    "product_compatibility": 20.0,
                },
                "release_ready": False,
                "hypothesis_gate_passed": True,
                "focused_gate": "product_compatibility",
                "gate_evidence": {
                    "application_thinness": {"status": "not-focused"},
                    "distribution_integrity": {"status": "not-focused"},
                    "product_compatibility": {"status": "passed"},
                },
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    decision_json = run_dir / "decision.json"
    decision_json.write_text(
        json.dumps({"decision": "CONTINUE", "reason": "release not ready"}, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    result = _run([SYNC, "B-H005", run_dir, eval_json, decision_json], cwd=tmp_path, env=_env(state_dir, artifact_dir))

    assert result.returncode == 0, result.stderr
    hypotheses = json.loads((state_dir / "hypotheses.yaml").read_text(encoding="utf-8"))
    assert hypotheses["events"][0]["status"] == "confirmed"
    rows = (state_dir / "runs.csv").read_text(encoding="utf-8").splitlines()
    assert "cycle-b-h005/manifest.json" in rows[1]
    assert str(tmp_path) not in rows[1]


def test_sync_updates_manifest_with_six_stable_evidence_links(tmp_path: Path) -> None:
    state_dir, artifact_dir = _write_temp_state(tmp_path)
    _append_run(
        state_dir,
        artifact_dir,
        run_id="cycle-b-h001",
        cycle=1,
        hypothesis_id="B-H001",
        gate_key="kernel_independence",
        weight=25.0,
        command=["kernel", "gate"],
    )
    _append_run(
        state_dir,
        artifact_dir,
        run_id="cycle-b-h002",
        cycle=2,
        hypothesis_id="B-H002",
        gate_key="kernel_independence",
        weight=25.0,
        command=["kernel", "gate"],
    )
    _append_run(
        state_dir,
        artifact_dir,
        run_id="cycle-b-h003",
        cycle=3,
        hypothesis_id="B-H003",
        gate_key="pi_tool_generalization",
        weight=15.0,
        command=["pi", "gate"],
    )
    _append_run(
        state_dir,
        artifact_dir,
        run_id="cycle-b-h004",
        cycle=4,
        hypothesis_id="B-H004",
        gate_key="domain_ownership",
        weight=20.0,
        command=["domain", "gate"],
    )
    run_dir = artifact_dir / "cycle-b-h005"
    run_dir.mkdir()
    (run_dir / "manifest.json").write_text(
        json.dumps({"hypothesis_id": "B-H005", "session": "2026-08-28-workstream-b-package-extraction"}) + "\n",
        encoding="utf-8",
    )
    eval_json = run_dir / "local-eval.json"
    gate_evidence = {
        key: {
            "artifact_path": f"stable/{key}.json",
            "command": ["make", key],
            "returncode": 0,
            "status": "passed" if key == "product_compatibility" else "carried-forward",
        }
        for key in EXPECTED_WEIGHTS
    }
    gate_evidence["application_thinness"]["status"] = "receipt-passed"
    gate_evidence["distribution_integrity"]["status"] = "receipt-passed"
    eval_json.write_text(
        json.dumps(
            {
                "focused_gate": "product_compatibility",
                "gate_evidence": gate_evidence,
                "hypothesis_gate_passed": True,
                "per_task": EXPECTED_WEIGHTS,
                "release_blockers": [],
                "release_ready": True,
                "total": 100.0,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    decision_json = run_dir / "decision.json"
    decision_json.write_text(
        json.dumps({"decision": "PUSH", "reason": "100% release gate met"}, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    result = _run([SYNC, "B-H005", run_dir, eval_json, decision_json], cwd=tmp_path, env=_env(state_dir, artifact_dir))

    assert result.returncode == 0, result.stderr
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    links = manifest["score_evidence"]
    assert [link["score_key"] for link in links] == list(EXPECTED_WEIGHTS)
    assert {tuple(link["command"]) for link in links} == {
        ("make", key) for key in EXPECTED_WEIGHTS
    }
    assert all(link["artifact_path"].startswith("stable/") for link in links)
    assert str(tmp_path) not in json.dumps(manifest)
    session = json.loads((state_dir / "session-state.json").read_text(encoding="utf-8"))
    assert session["phase"] == "complete"
    assert session["next_action"] == "Target met; proceed with integration review and mainline closure."


def test_eval_no_argument_creates_missing_artifact_directory_before_mktemp(tmp_path: Path) -> None:
    state_dir, artifact_dir = _write_temp_state(tmp_path)
    missing_artifact_dir = tmp_path / "missing-artifacts"
    env = _env(state_dir, artifact_dir)
    env["CLIMB_ARTIFACT_DIR"] = str(missing_artifact_dir)

    result = _run([EVAL], cwd=tmp_path, env=env)

    assert result.returncode != 0
    assert missing_artifact_dir.is_dir()
    assert "mktemp" not in result.stderr


def test_target_checker_requires_complete_phase_at_100(tmp_path: Path) -> None:
    state_dir, artifact_dir = _write_temp_state(tmp_path)
    env = _env(state_dir, artifact_dir)

    below = _run([CHECK_TARGET], cwd=tmp_path, env=env)
    assert below.returncode == 0, below.stdout + below.stderr
    below_payload = json.loads(below.stdout)
    assert below_payload["current"] is None
    assert below_payload["target"] == 100.0
    assert below_payload["met"] is False

    with (state_dir / "runs.csv").open("a", encoding="utf-8") as handle:
        handle.write(
            "perfect,1,2026-08-28-workstream-b-package-extraction,B-H005,application-assembly,,,,100.0,25.0,20.0,15.0,10.0,10.0,20.0,,,,confirmed,0.0,\n"
        )
    pending = _run([CHECK_TARGET], cwd=tmp_path, env=env)
    assert pending.returncode == 0, pending.stdout + pending.stderr
    assert json.loads(pending.stdout)["met"] is False

    session = json.loads((state_dir / "session-state.json").read_text(encoding="utf-8"))
    session["phase"] = "complete"
    (state_dir / "session-state.json").write_text(json.dumps(session) + "\n", encoding="utf-8")
    complete = _run([CHECK_TARGET], cwd=tmp_path, env=env)
    assert complete.returncode == 10, complete.stdout + complete.stderr
    assert json.loads(complete.stdout)["met"] is True


def test_regen_tree_names_workstream_b_and_next_active_hypothesis(tmp_path: Path) -> None:
    state_dir, artifact_dir = _write_temp_state(tmp_path)

    result = _run([REGEN], cwd=tmp_path, env=_env(state_dir, artifact_dir))

    assert result.returncode == 0, result.stderr
    tree = (state_dir / "research-tree.md").read_text(encoding="utf-8")
    assert "Workstream B Package Extraction" in tree
    assert "Next hypothesis: B-H001" in tree
    assert "**B-H001**" in tree


if __name__ == "__main__":
    raise SystemExit(subprocess.call([sys.executable, "-m", "pytest", __file__, "-q"]))
