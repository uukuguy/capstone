from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from capability_agent.application import prepare_domain_runtime

from inventory_domain.profile import build_inventory_profile


ROOT = Path(__file__).resolve().parents[3]


def test_unchanged_generic_pi_executes_inventory_tools(tmp_path) -> None:
    executable = shutil.which("inventoryctl")
    assert executable is not None
    workspace = tmp_path / "run"
    workspace.mkdir()
    profile = build_inventory_profile()
    prepared = prepare_domain_runtime(
        profile,
        executable=Path(executable),
        workspace=workspace,
        tool_catalog_path=workspace / "tool-catalog.json",
        guide_index_path=workspace / "guide-index.json",
    )
    descriptor = {
        "protocol": profile.manifest.protocol,
        "protocolVersion": profile.manifest.protocol_version,
        "executable": profile.manifest.executable_name,
        "executableArgs": ["request", "--workspace", str(workspace)],
        "toolNamePrefix": profile.manifest.tool_name_prefix,
        "guideToolName": "inventory_guide_open",
        "contextToolName": "inventory_analysis_context_get",
        "decisionToolName": "inventory_record_decision",
        "workspacePath": str(workspace),
        "toolCatalogPath": str(prepared.tool_catalog_path),
        "guideIndexPath": str(prepared.guide_index_path),
        "guideRootPath": str(profile.manifest.guide_root.resolve()),
        "guideIndexSha256": hashlib.sha256(
            prepared.guide_index_path.read_bytes()
        ).hexdigest(),
    }
    descriptor_path = workspace / "domain-runtime-node.json"
    descriptor_path.write_text(
        json.dumps(descriptor, sort_keys=True) + "\n", encoding="utf-8"
    )

    completed = subprocess.run(
        [
            "node",
            str(ROOT / "tools/test_inventory_pi_transport.mjs"),
            str(descriptor_path),
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    summary = json.loads(completed.stdout)
    assert summary["registered_names"] == [
        "inventory_asset_get",
        "inventory_asset_list",
        "inventory_catalog_open",
        "inventory_guide_open",
        "inventory_stock_summary",
    ]
    assert summary["asset_count"] == 1
    assert summary["stock_asset_count"] == 5
    assert summary["evidence_count"] == 2
    assert summary["used_grid_wrapper"] is False
