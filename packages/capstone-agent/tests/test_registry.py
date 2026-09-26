from __future__ import annotations

from pathlib import Path

import pytest

from capstone_agent.registry import build_registry
from capstone_agent.session import WorkerSession


def test_registry_selects_only_fixed_application_workers(tmp_path: Path) -> None:
    registry = build_registry(tmp_path)
    pandapower = registry.resolve("pandapower-static-analysis")
    pypsa = registry.resolve("pypsa-business-cases")
    assert pandapower.command[-2:] == ("-m", "grid_agent.worker")
    assert pypsa.command[-2:] == ("-m", "pypsa_agent.worker")
    assert pandapower.cwd == pypsa.cwd == tmp_path
    with pytest.raises(ValueError, match="registered"):
        registry.resolve("arbitrary-command")
    with pytest.raises(ValueError, match="case"):
        WorkerSession(pypsa, mode="scripted-demo", case_id="unregistered")
