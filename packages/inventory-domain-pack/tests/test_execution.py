from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from inventory_domain.execution import (
    InventoryCapabilityError,
    InventoryctlExecutor,
    sanitize_environment,
)


def test_executor_calls_real_inventoryctl_with_correlated_protocol(tmp_path) -> None:
    executable = shutil.which("inventoryctl")
    assert executable is not None
    executor = InventoryctlExecutor(
        executable=Path(executable),
        workspace=tmp_path,
        timeout_seconds=10,
    )

    environment = executor.invoke("environment.describe", {})
    opened = executor.invoke("catalog.open", {"catalog_id": "warehouse-a"})
    listed = executor.invoke(
        "asset.list",
        {"context_ref": opened["context_ref"], "limit": 1},
    )

    assert environment["protocol"] == "inventory-capability"
    assert listed["count"] == 1
    assert listed["result_ref"].startswith("inventory-result:sha256:")


def test_executor_preserves_typed_capability_error(tmp_path) -> None:
    executable = shutil.which("inventoryctl")
    assert executable is not None
    executor = InventoryctlExecutor(executable=Path(executable), workspace=tmp_path)

    with pytest.raises(InventoryCapabilityError) as caught:
        executor.invoke("asset.create", {})

    assert caught.value.error["code"] == "capability_not_published"


def test_executor_environment_removes_credentials() -> None:
    assert sanitize_environment(
        {
            "PATH": "/bin",
            "OPENAI_API_KEY": "secret",
            "INVENTORY_TOKEN": "secret",
            "VISIBLE_SETTING": "yes",
        }
    ) == {"PATH": "/bin", "VISIBLE_SETTING": "yes"}
