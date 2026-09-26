"""Source-defined application worker selection without dynamic discovery."""

from __future__ import annotations

from pathlib import Path

from capstone_agent.session import WorkerRegistry, WorkerSpec


PYPSA_DEMOS = (
    "regional-demand-stress",
    "scigrid-dispatch",
    "ac-dc-interconnection",
)
PANDAPOWER_DEMOS = ("pandapower-scripted-task", "pandapower-scripted-test")


def build_registry(repo_root: Path | None = None) -> WorkerRegistry:
    root = Path(repo_root or Path(__file__).resolve().parents[4]).resolve()
    return WorkerRegistry((
        WorkerSpec(
            "pandapower-static-analysis",
            ("uv", "run", "--project", str(root / "packages/grid-agent"),
             "python", "-m", "grid_agent.worker"),
            cwd=root, scripted_cases=PANDAPOWER_DEMOS,
            preview_command=("uv", "run", "--project", str(root / "packages/grid-agent"),
                             "python", "-m", "grid_agent.case_preview"),
        ),
        WorkerSpec(
            "pypsa-business-cases",
            ("uv", "run", "--project", str(root / "packages/pypsa-agent"),
             "python", "-m", "pypsa_agent.worker"),
            cwd=root, scripted_cases=PYPSA_DEMOS,
            preview_command=("uv", "run", "--project", str(root / "packages/pypsa-agent"),
                             "python", "-m", "pypsa_agent.case_preview"),
        ),
    ))
