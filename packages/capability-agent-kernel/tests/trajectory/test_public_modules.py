from __future__ import annotations

import importlib


def test_trajectory_public_modules_import_without_application() -> None:
    modules = (
        "capability_agent.trajectory.canonical",
        "capability_agent.trajectory.events",
        "capability_agent.trajectory.artifacts",
        "capability_agent.trajectory.answers",
        "capability_agent.trajectory.reader",
        "capability_agent.trajectory.recorder",
        "capability_agent.trajectory.replay",
    )
    for module in modules:
        assert importlib.import_module(module).__name__ == module
