from __future__ import annotations

import copy
import json
import stat
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import release_closure  # noqa: E402
from climb_evidence import (  # noqa: E402
    CLOSURE_GATE_ORDER,
    as_list,
    as_object,
    load_json_object,
    policy_sha256,
    sign_receipt,
    validate_release_policy,
)


ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize(
    "mutate",
    (
        lambda config: config["score_gates"]["product_compatibility"].update(
            command=["true"]
        ),
        lambda config: config["release_source"].update(
            include_pathspecs=["Makefile"]
        ),
        lambda config: config["score_weights"].update(kernel_independence=0),
        lambda config: config["score_gates"]["product_compatibility"].update(
            prerequisite_receipts=[]
        ),
        lambda config: config["closure"].update(gate_order=["product_compatibility"]),
    ),
)
def test_release_policy_rejects_command_weight_graph_and_pathspec_weakening(
    mutate,
) -> None:
    config = load_json_object(ROOT / "docs/status/climb/config.yaml")
    weakened = copy.deepcopy(config)
    mutate(weakened)

    with pytest.raises(ValueError, match="release policy"):
        validate_release_policy(weakened)


def test_release_closure_executes_every_fixed_gate_and_writes_readonly_chain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, run_dir = _release_repo(tmp_path)
    calls: list[list[str]] = []

    def fake_run(command: list[str], root: Path) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, f"passed {' '.join(command)}\n", "")

    monkeypatch.setattr(release_closure, "run_gate_command", fake_run)

    score = release_closure.execute_release_closure(repo, run_dir)
    config = load_json_object(repo / "docs/status/climb/config.yaml")
    score_gates = as_object(config.get("score_gates"), "score_gates")
    receipt_gates = as_object(config.get("receipt_gates"), "receipt_gates")
    expected_commands = []
    for key in CLOSURE_GATE_ORDER:
        raw_gate = score_gates.get(key) or receipt_gates.get(key)
        gate = as_object(raw_gate, f"gate {key}")
        expected_commands.append(
            [str(part) for part in as_list(gate.get("command"), f"command {key}")]
        )

    assert calls == expected_commands
    assert score["total"] == 100.0
    assert score["release_ready"] is True
    assert score["policy_sha256"] == policy_sha256(config)
    closure_path = run_dir / "release-closure.json"
    assert stat.S_IMODE(closure_path.stat().st_mode) == 0o400
    closure = json.loads(closure_path.read_text(encoding="utf-8"))
    assert closure["gate_order"] == list(CLOSURE_GATE_ORDER)
    assert closure["closure_digest"]
    assert all(result["stdout_sha256"] for result in closure["gate_results"])
    for result in closure["gate_results"]:
        output_path = repo / result["output_artifact_path"]
        assert stat.S_IMODE(output_path.stat().st_mode) == 0o400


def test_release_closure_rejects_dirty_policy_before_any_gate_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, run_dir = _release_repo(tmp_path)
    config_path = repo / "docs/status/climb/config.yaml"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["score_gates"]["product_compatibility"]["command"] = ["true"]
    config_path.write_text(json.dumps(config, sort_keys=True) + "\n", encoding="utf-8")
    calls: list[list[str]] = []
    monkeypatch.setattr(
        release_closure,
        "run_gate_command",
        lambda command, root: calls.append(command),
    )

    with pytest.raises(ValueError, match="release policy|dirty"):
        release_closure.execute_release_closure(repo, run_dir)

    assert calls == []


def test_same_user_forged_receipt_cannot_mask_a_live_closure_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, run_dir = _release_repo(tmp_path)
    forged = repo / "runs/climb/gate-receipts/forged/kernel_independence.json"
    forged.parent.mkdir(parents=True)
    same_user_key = b"same-user-visible-integrity-key"
    forged.write_text(
        json.dumps(
            sign_receipt(
                {"gate_key": "kernel_independence", "returncode": 0, "status": "passed"},
                same_user_key,
            ),
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    def fail_kernel(command: list[str], root: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            command,
            19 if command == [
                "uv",
                "run",
                "--project",
                "packages/grid-agent",
                "pytest",
                "packages/capability-agent-kernel/tests",
                "-q",
            ] else 0,
            "live gate\n",
            "",
        )

    monkeypatch.setattr(release_closure, "run_gate_command", fail_kernel)

    score = release_closure.execute_release_closure(repo, run_dir)

    per_task = as_object(score.get("per_task"), "per_task")
    evidence = as_object(score.get("gate_evidence"), "gate_evidence")
    kernel = as_object(evidence.get("kernel_independence"), "kernel evidence")
    assert per_task["kernel_independence"] == 0.0
    assert score["release_ready"] is False
    assert kernel["status"] == "closure-failed"


def test_release_closure_rejects_dirty_included_source_before_gates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, run_dir = _release_repo(tmp_path)
    source = repo / "tools/check_package_boundaries.py"
    source.write_text("dirty source\n", encoding="utf-8")
    calls: list[list[str]] = []
    monkeypatch.setattr(
        release_closure,
        "run_gate_command",
        lambda command, root: calls.append(command),
    )

    with pytest.raises(ValueError, match="dirty"):
        release_closure.execute_release_closure(repo, run_dir)

    assert calls == []


def test_release_closure_rejects_a_handwritten_final_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, run_dir = _release_repo(tmp_path)
    (run_dir / "release-closure.json").write_text(
        '{"all_passed":true,"total":100}\n', encoding="utf-8"
    )
    calls: list[list[str]] = []
    monkeypatch.setattr(
        release_closure,
        "run_gate_command",
        lambda command, root: calls.append(command),
    )

    with pytest.raises(ValueError, match="already exists"):
        release_closure.execute_release_closure(repo, run_dir)

    assert calls == []


def _release_repo(tmp_path: Path) -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    repo.mkdir()
    config = load_json_object(ROOT / "docs/status/climb/config.yaml")
    config_path = repo / "docs/status/climb/config.yaml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(json.dumps(config, sort_keys=True) + "\n", encoding="utf-8")
    for section in ("score_gates", "receipt_gates"):
        gates = as_object(config.get(section), section)
        for raw_gate in gates.values():
            gate = as_object(raw_gate, "gate")
            for raw_path in as_list(gate.get("required_paths", []), "required_paths"):
                required = repo / str(raw_path)
                if required.suffix or required.name == "Makefile":
                    required.parent.mkdir(parents=True, exist_ok=True)
                    required.write_text("fixture\n", encoding="utf-8")
                else:
                    required.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.DEVNULL)
    subprocess.run(
        ["git", "config", "user.email", "agent@example.invalid"], cwd=repo, check=True
    )
    subprocess.run(["git", "config", "user.name", "Agent"], cwd=repo, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "-m", "release source"],
        cwd=repo,
        check=True,
        stdout=subprocess.DEVNULL,
    )
    run_dir = repo / "runs/climb/test-closure"
    run_dir.mkdir(parents=True)
    return repo, run_dir
