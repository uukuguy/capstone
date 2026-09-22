"""Provider-free experiment: existing inventory Pack over a fixed HTTP authority."""

from __future__ import annotations

import json
from dataclasses import replace
from types import SimpleNamespace

import pytest

from capability_agent.application.context_store import ApplicationContextStore
from capability_agent.application.profile import CredentialScope
from capability_agent.application.reporting import GenericReportShell
from inventory_reference.artifacts import persist_document
from inventory_domain.profile import build_inventory_profile

from http_authority_experiment import (
    HttpInventoryArtifactAuthority,
    HttpInventoryError,
    HttpInventoryExecutor,
    HttpInventoryProvisioner,
    LoopbackInventoryService,
)
from test_application_conformance import TWO_TURNS, admissions, run_application


class HttpCredentials:
    def __init__(self, token: str) -> None:
        self.token = token

    def issue(self, *, binding_id, scope):
        assert binding_id == "inventory"
        assert scope.credential_names == ("INVENTORY_API_TOKEN",)
        return SimpleNamespace(
            scope_id=scope.scope_id,
            credentials={"INVENTORY_API_TOKEN": self.token},
        )


def test_http_authority_two_turns_receipts_and_replay(tmp_path) -> None:
    with LoopbackInventoryService() as service:
        domain = replace(
            build_inventory_profile(),
            provisioner=HttpInventoryProvisioner(service.origin),
            authority_factory=HttpInventoryArtifactAuthority,
        )
        outcome, workspace, transports = run_application(
            tmp_path, TWO_TURNS, domain=domain,
            credentials=HttpCredentials(service.token),
            credential_scope=CredentialScope(credential_names=("INVENTORY_API_TOKEN",)),
        )

    assert outcome.status == "completed", outcome.error
    assert outcome.completed_questions == 2
    assert [item[0] for item in transports[0].calls] == ["catalog.open", "asset.list", "stock.summary"]
    assert service.requests[0]["capability"] == "environment.describe"
    assert service.page_requests >= 2
    snapshot = json.loads(workspace.context_snapshot_path.read_text(encoding="utf-8"))
    assert ApplicationContextStore.replay(workspace).model_dump(mode="json") == snapshot
    results = [json.loads(path.read_text(encoding="utf-8")) for path in workspace.domain_path("inventory").glob("evidence/results/*.json")]
    assert len(results) == 2
    assert all(result["receipt"]["complete"] for result in results)
    assert all(result["receipt"]["authority_id"] == "inventory-http-loopback" for result in results)
    assert service.token not in json.dumps(snapshot)
    assert isinstance(outcome.rendered, str)
    assert service.token not in outcome.rendered
    assert service.token not in "".join(path.read_text(encoding="utf-8") for path in workspace.root.rglob("*.json"))


@pytest.mark.parametrize(
    ("mode", "code"),
    [
        ("unauthorized", "http_unauthorized"),
        ("forbidden", "http_forbidden"),
        ("rate_limited", "http_rate_limited"),
        ("timeout", "http_timeout"),
        ("schema_drift", "http_schema_invalid"),
        ("partial_page", "http_pagination_incomplete"),
        ("version_change", "http_version_changed"),
    ],
)
def test_http_authority_failure_never_publishes_a_result(tmp_path, mode: str, code: str) -> None:
    with LoopbackInventoryService() as service:
        executor = HttpInventoryExecutor(service.origin, service.token, tmp_path, timeout_seconds=0.05)
        opened = executor.invoke("catalog.open", {"catalog_id": "warehouse-a"})
        service.mode = mode
        with pytest.raises(HttpInventoryError) as raised:
            executor.invoke("asset.list", {"context_ref": opened["context_ref"]})

    assert raised.value.code == code
    assert not list((tmp_path / "evidence/results").glob("*.json"))


def test_http_authority_repeated_read_retains_version_and_distinct_observation(tmp_path) -> None:
    with LoopbackInventoryService() as service:
        executor = HttpInventoryExecutor(service.origin, service.token, tmp_path)
        opened = executor.invoke("catalog.open", {"catalog_id": "warehouse-a"})
        first = executor.invoke("stock.summary", {"context_ref": opened["context_ref"]})
        second = executor.invoke("stock.summary", {"context_ref": opened["context_ref"]})

    assert first["result_ref"] != second["result_ref"]
    assert first["total_quantity_on_hand"] == second["total_quantity_on_hand"]


def test_http_receipt_rejects_content_addressed_tampering(tmp_path) -> None:
    with LoopbackInventoryService() as service:
        executor = HttpInventoryExecutor(service.origin, service.token, tmp_path)
        opened = executor.invoke("catalog.open", {"catalog_id": "warehouse-a"})
        result = executor.invoke("stock.summary", {"context_ref": opened["context_ref"]})

    original_path, = (tmp_path / "evidence/results").glob("*.json")
    altered = json.loads(original_path.read_text(encoding="utf-8"))
    altered["receipt"]["response_sha256"] = "0" * 64
    forged_ref, _ = persist_document(tmp_path, "result", altered)
    authority = HttpInventoryArtifactAuthority(tmp_path)

    assert isinstance(result["result_ref"], str)
    authority.verify_result(result["result_ref"])
    with pytest.raises(RuntimeError, match="HTTP receipt"):
        authority.verify_result(forged_ref)


def test_http_report_failure_does_not_undo_committed_answers(tmp_path) -> None:
    class FailingReport(GenericReportShell):
        def render(self, **kwargs):
            raise RuntimeError("injected report failure")

    with LoopbackInventoryService() as service:
        domain = replace(
            build_inventory_profile(),
            provisioner=HttpInventoryProvisioner(service.origin),
            authority_factory=HttpInventoryArtifactAuthority,
        )
        outcome, workspace, _transports = run_application(
            tmp_path, TWO_TURNS, domain=domain,
            credentials=HttpCredentials(service.token),
            credential_scope=CredentialScope(credential_names=("INVENTORY_API_TOKEN",)),
            report_shell=FailingReport(),
        )

    assert outcome.status == "completed", outcome.error
    assert outcome.completed_questions == 2
    assert outcome.result.core.diagnostic_refs
    assert ApplicationContextStore.replay(workspace).core.turns[-1]["status"] == "success"


def test_http_failure_in_second_turn_preserves_first_turn_without_new_evidence(tmp_path) -> None:
    with LoopbackInventoryService() as service:
        domain = replace(
            build_inventory_profile(),
            provisioner=HttpInventoryProvisioner(service.origin),
            authority_factory=HttpInventoryArtifactAuthority,
        )

        def fail_after_first_turn(capability, _result, _binding):
            if capability == "asset.list":
                service.mode = "rate_limited"

        outcome, workspace, transports = run_application(
            tmp_path, TWO_TURNS, domain=domain,
            credentials=HttpCredentials(service.token),
            credential_scope=CredentialScope(credential_names=("INVENTORY_API_TOKEN",)),
            after_invoke=fail_after_first_turn,
        )

    assert outcome.status == "completed", outcome.error
    assert outcome.completed_questions == 2
    assert transports[0].calls[-1][2] == {"code": "capability_transport_failed"}
    assert [item["mode"] for item in admissions(workspace)] == ["authority_backed", "limited"]
    answers = [json.loads(path.read_text()) for path in sorted(workspace.turns_path.glob("*/answer.json"))]
    assert answers[0]["result_refs"] and answers[0]["evidence_refs"]
    assert answers[1]["result_refs"] == [] and answers[1]["evidence_refs"] == []
    assert len(list((workspace.domain_path("inventory") / "evidence/results").glob("*.json"))) == 1
