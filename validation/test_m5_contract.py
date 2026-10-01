from __future__ import annotations

import json

import pytest

from validation.thread.m5_contract import M5CheckResult, M5RunSummary, M5ValidationError


def test_m5_summary_serializes_bounded_schema_and_redacts_secret_keys() -> None:
    summary = M5RunSummary(
        application_id="pandapower-static-analysis",
        api_origin="http://127.0.0.1:8767",
        checks=(M5CheckResult("catalog", "passed", {"models": 2, "token": "do-not-store"}),),
    )

    document = summary.to_document()

    assert document["schema"] == "capstone-m5-validation/1"
    assert document["checks"] == [{"name": "catalog", "status": "passed", "details": {"models": 2, "token": "[redacted]"}}]
    assert json.dumps(document, ensure_ascii=False).find("do-not-store") == -1


def test_m5_contract_rejects_unbounded_or_invalid_values() -> None:
    with pytest.raises(M5ValidationError, match="status"):
        M5CheckResult("catalog", "unknown", {})  # type: ignore[arg-type]
    with pytest.raises(M5ValidationError, match="details"):
        M5CheckResult("catalog", "passed", {"nested": object()})
    with pytest.raises(M5ValidationError, match="checks"):
        M5RunSummary("app", "http://127.0.0.1:8767", tuple(
            M5CheckResult(str(index), "passed", {}) for index in range(129)
        ))
