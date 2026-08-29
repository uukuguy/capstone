from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
STATE = ROOT / "docs/status/climb"
ARCHIVE = STATE / "_archive/2026-08-28-workstream-b-package-extraction"

EXPECTED_WEIGHTS = {
    "reference_authority": 25.0,
    "domain_pack_spi": 20.0,
    "generic_pi_transport": 15.0,
    "authority_lineage": 20.0,
    "distribution_integrity": 10.0,
    "product_compatibility": 10.0,
}
EXPECTED_HYPOTHESES = ["C-H001", "C-H002", "C-H003", "C-H004", "C-H005"]
PROTECTED_PATHS = [
    "packages/capability-agent-kernel",
    "packages/pi-capability-tools",
    "packages/trajectory-workbench",
]
ARCHIVED_FILES = {
    "adjudicator-log.md",
    "calibration.json",
    "config.yaml",
    "hypotheses.yaml",
    "pending-lb.json",
    "research-tree.json",
    "research-tree.md",
    "runs.csv",
    "session-state.json",
    "session-target.md",
}


def _json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_active_state_selects_workstream_c_inventory_score_contract() -> None:
    config = _json(STATE / "config.yaml")

    assert config["session"] == "2026-08-29-workstream-c-inventory-reference-domain"
    assert config["workstream_label"] == "Workstream C Inventory Reference Domain"
    assert config["target_description"] == (
        "100% inventory reference-domain score with protected framework paths unchanged."
    )
    assert config["release_hypothesis_id"] == "C-H005"
    assert config["release_policy_id"] == "workstream-c-inventory-v1"
    assert config["score_weights"] == EXPECTED_WEIGHTS
    assert config["subscores"] == list(EXPECTED_WEIGHTS)
    assert config["protected_paths"] == PROTECTED_PATHS
    assert set(config["protected_path_digests"]) == set(PROTECTED_PATHS)


def test_active_hypothesis_pool_and_session_start_at_c_h001() -> None:
    document = _json(STATE / "hypotheses.yaml")
    hypotheses = document["hypotheses"]
    session = _json(STATE / "session-state.json")

    assert isinstance(hypotheses, list)
    assert [item["id"] for item in hypotheses] == EXPECTED_HYPOTHESES
    assert all(item["status"] == "pending" for item in hypotheses)
    effective = {item["id"]: item["status"] for item in hypotheses}
    for event in document["events"]:
        effective[event["hypothesis_id"]] = event["status"]
    expected_next = next(
        (item for item in EXPECTED_HYPOTHESES if effective[item] == "pending"),
        "none",
    )
    assert session["session"] == "2026-08-29-workstream-c-inventory-reference-domain"
    assert session["next_hypothesis"] == expected_next
    assert session["in_flight"] is None
    assert session["falsified_routes"] == []


def test_completed_workstream_b_state_is_archived() -> None:
    assert ARCHIVE.is_dir()
    assert {path.name for path in ARCHIVE.iterdir()} == ARCHIVED_FILES
    archived_config = _json(ARCHIVE / "config.yaml")
    assert archived_config["session"] == "2026-08-28-workstream-b-package-extraction"


def test_adapter_runtime_has_no_workstream_b_release_hard_coding() -> None:
    for relative_path in (
        "tools/climb/train.sh",
        "tools/climb/eval-local.sh",
        "tools/climb/cycle.sh",
        "tools/climb/check-target.py",
        "tools/climb/sync-cycle.py",
        "tools/climb/regen-tree.py",
    ):
        source = (ROOT / relative_path).read_text(encoding="utf-8")
        assert "Workstream B" not in source, relative_path
        assert '"B-H005"' not in source, relative_path
        assert "workstream-b-package-extraction" not in source, relative_path


def test_runs_header_tracks_each_workstream_c_subscore() -> None:
    header = (STATE / "runs.csv").read_text(encoding="utf-8").splitlines()[0]
    columns = header.split(",")

    for score_name in EXPECTED_WEIGHTS:
        assert f"local_{score_name}" in columns
    assert "local_kernel_independence" not in columns
