from __future__ import annotations

from types import SimpleNamespace as NS

import httpx
import pytest

from capstone_agent.thread_http import HttpThreadSession


def test_missing_remote_configuration_is_not_success(monkeypatch, tmp_path):
    from validation.run_m11 import main
    monkeypatch.delenv("CAPSTONE_M11_API_ORIGIN", raising=False)
    monkeypatch.delenv("CAPSTONE_M11_OPERATOR_TOKEN", raising=False)
    monkeypatch.setenv("CAPSTONE_M11_RECEIPT_DIR", str(tmp_path))
    assert main() == 2


@pytest.mark.parametrize("status,document", [(404, {}), (200, {"runtime_mode": "normal"})])
def test_preflight_failure_makes_no_mutating_requests(status, document):
    from validation.thread.m11_matrix import run_matrix
    calls = []

    def handler(request):
        calls.append(request.method)
        return httpx.Response(status, json=document)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        session = HttpThreadSession("http://testserver", "private-test-token", client=client)
        with pytest.raises((ValueError, RuntimeError)):
            run_matrix(session)
    assert calls == ["GET"]


def test_rejected_command_is_not_success():
    from validation.thread.m11_matrix import run_matrix, READINESS
    session = NS(_request=lambda *args: READINESS, create=lambda *args: None,
                 catalog=lambda: NS(models=(NS(model_id="ieee39", available=True),
                                            NS(model_id="regional-six-bus", available=True))),
                 snapshot=lambda: NS(last_event_seq=0),
                 command=lambda *args: NS(status="rejected"))
    with pytest.raises(ValueError, match="command_rejected"):
        run_matrix(session)


def test_resync_cannot_prove_attempt_history():
    from capstone_agent.thread_http import ThreadResyncRequired
    from validation.thread.m11_matrix import wait_attempt

    def events(**kwargs):
        raise ThreadResyncRequired(NS())

    with pytest.raises(ValueError, match="resync"):
        wait_attempt(NS(events=events), "attempt_one", "ctx_one", "sel_0",
                     after=0, require_topology=True)


def test_receipt_is_private_and_excludes_credentials(monkeypatch, tmp_path):
    import json
    import validation.run_m11 as runner
    monkeypatch.setenv("CAPSTONE_M11_API_ORIGIN", "http://testserver")
    monkeypatch.setenv("CAPSTONE_M11_OPERATOR_TOKEN", "must-not-appear")
    monkeypatch.setenv("CAPSTONE_M11_RECEIPT_DIR", str(tmp_path / "receipts"))
    monkeypatch.setattr(runner, "run_matrix", lambda session: [{"id": "test", "status": "passed", "details": {}}])
    assert runner.main() == 0
    path = next((tmp_path / "receipts").glob("*.json"))
    assert path.stat().st_mode & 0o777 == 0o600
    assert path.parent.stat().st_mode & 0o777 == 0o700
    assert "must-not-appear" not in path.read_text()
    assert json.loads(path.read_text())["provider_validation"] == "not_run"


def test_wait_rejects_failed_attempt_and_timeout(monkeypatch):
    import validation.thread.m11_matrix as matrix
    event = NS(event_seq=1, attempt_id="attempt_one", model_context_id="ctx_one",
               selection_revision="sel_0", event_type="attempt_failed", payload={})
    session = NS(events=lambda **kwargs: NS(events=(event,), next_event_seq=1))
    with pytest.raises(ValueError, match="attempt_failed"):
        matrix.wait_attempt(session, "attempt_one", "ctx_one", "sel_0", after=0,
                            require_topology=True, timeout_seconds=1)
    session.events = lambda **kwargs: NS(events=(), next_event_seq=0)
    ticks = iter((0, 0, 2))
    monkeypatch.setattr(matrix.time, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(matrix.time, "sleep", lambda _: None)
    with pytest.raises(TimeoutError):
        matrix.wait_attempt(session, "attempt_one", "ctx_one", "sel_0", after=0,
                            require_topology=True, timeout_seconds=1)


def test_wait_collects_late_topology_and_rejects_foreign_context(monkeypatch):
    import validation.thread.m11_matrix as matrix
    def event(seq, kind, context="ctx_one"):
        return NS(event_seq=seq, attempt_id="attempt_one", model_context_id=context,
                  selection_revision="sel_0", event_type=kind, payload={})
    pages = iter(((event(1, "attempt_completed"),),
                  (event(2, "network_diagram"), event(3, "network_layer"))))
    session = NS(events=lambda **kwargs: NS(events=next(pages), next_event_seq=0))
    monkeypatch.setattr(matrix.time, "sleep", lambda _: None)
    events = matrix.wait_attempt(session, "attempt_one", "ctx_one", "sel_0", after=0,
                                 require_topology=True, timeout_seconds=1)
    assert len(events) == 3
    session.events = lambda **kwargs: NS(events=(event(1, "network_diagram", "ctx_foreign"),), next_event_seq=1)
    with pytest.raises(ValueError, match="identity"):
        matrix.wait_attempt(session, "attempt_one", "ctx_one", "sel_0", after=0,
                            require_topology=True, timeout_seconds=1)
