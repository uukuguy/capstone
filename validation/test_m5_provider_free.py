from __future__ import annotations

from pathlib import Path

import pytest

from validation.thread.m5_matrix import run_application_matrix
from validation.thread.provider_free_host import ProviderFreeThreadHost


@pytest.mark.parametrize(
    ("application_id", "project"),
    (
        ("pandapower-static-analysis", "pandapower"),
        ("pypsa-business-cases", "pypsa"),
    ),
)
def test_provider_free_matrix_uses_real_thread_http_and_authority(
    tmp_path: Path, application_id: str, project: str,
) -> None:
    pytest.importorskip("grid_simulator" if project == "pandapower" else "pypsa_model_authority")
    with ProviderFreeThreadHost(application_id, tmp_path) as session:
        checks = run_application_matrix(application_id, session, timeout_seconds=45)
    assert checks
    assert all(check.status == "passed" for check in checks), checks
