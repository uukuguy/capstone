"""Source-defined application worker selection without dynamic discovery."""

from __future__ import annotations

from pathlib import Path

from capstone_agent.session import WorkerRegistry, WorkerSpec


PYPSA_DEMOS = (
    "ac-dc-interconnection",
    "scigrid-dispatch",
    "regional-demand-stress",
)
PANDAPOWER_DEMOS = ("pandapower-scripted-task", "pandapower-scripted-test")


def build_registry(repo_root: Path | None = None) -> WorkerRegistry:
    root = Path(repo_root or Path(__file__).resolve().parents[4]).resolve()
    return WorkerRegistry((
        WorkerSpec(
            "pandapower-static-analysis",
            ("uv", "run", "--no-sync", "--project", str(root / "packages/grid-agent"),
             "python", "-m", "grid_agent.worker"),
            cwd=root, scripted_cases=PANDAPOWER_DEMOS, provider_cases=PANDAPOWER_DEMOS,
            preview_command=("uv", "run", "--no-sync", "--project", str(root / "packages/grid-agent"),
                             "python", "-m", "grid_agent.case_preview"),
        ),
        WorkerSpec(
            "pypsa-business-cases",
            ("uv", "run", "--no-sync", "--project", str(root / "packages/pypsa-agent"),
             "python", "-m", "pypsa_agent.worker"),
            cwd=root, scripted_cases=PYPSA_DEMOS, provider_cases=PYPSA_DEMOS,
            preview_command=("uv", "run", "--no-sync", "--project", str(root / "packages/pypsa-agent"),
                             "python", "-m", "pypsa_agent.case_preview"),
        ),
    ))
