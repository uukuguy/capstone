from __future__ import annotations

from pathlib import Path

import pytest

from validation.run_m5_provider_free import _write_summary
from validation.thread.m5_contract import M5CheckResult
from validation.thread.m5_matrix import run_application_matrix
from validation.thread.provider_free_host import ProviderFreeThreadHost, _refs


def test_provider_free_host_forwards_only_authority_declared_references() -> None:
    assert _refs({"payload": "no authority references"}) == ((), ())
    assert _refs({"evidence_ref": "evidence:authority"}) == ((), ("evidence:authority",))
    assert _refs({
        "result_refs": ["result:authority"],
        "evidence_refs": ["evidence:authority"],
    }) == (("result:authority",), ("evidence:authority",))


def test_provider_free_runner_persists_bounded_summary(tmp_path: Path) -> None:
    path = _write_summary(
        tmp_path,
        "pandapower-static-analysis",
        (M5CheckResult("catalog", "passed", {"models": 1}),),
    )
    assert path == tmp_path / "m5-provider-free-summary.json"
    document = path.read_text(encoding="utf-8")
    assert '"schema": "capstone-m5-provider-free/1"' in document
    assert '"application_id": "pandapower-static-analysis"' in document


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
