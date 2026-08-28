from __future__ import annotations

import os

import pytest


@pytest.fixture
def clean_child_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure the transport tests can assert secret filtering explicitly."""

    monkeypatch.setenv("PATH", os.environ.get("PATH", ""))
    monkeypatch.setenv("GRID_AGENT_SECRET", "should-not-reach-gridctl")
