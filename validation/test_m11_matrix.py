from __future__ import annotations

import json
from types import SimpleNamespace as NS

import httpx
import pytest

from capstone_agent.thread_http import HttpThreadSession


@pytest.fixture
def configured_m11_runner(monkeypatch, tmp_path):
    import validation.run_m11 as runner

    receipt_dir = tmp_path / "receipts"
    token = "must-not-appear"
    monkeypatch.setenv("CAPSTONE_M11_API_ORIGIN", "http://testserver")
    monkeypatch.setenv("CAPSTONE_M11_OPERATOR_TOKEN", token)
    monkeypatch.setenv("CAPSTONE_M11_RECEIPT_DIR", str(receipt_dir))
    return runner, receipt_dir, token


@pytest.mark.parametrize("missing", ["CAPSTONE_M11_API_ORIGIN", "CAPSTONE_M11_OPERATOR_TOKEN"])
def test_missing_remote_configuration_is_not_success(monkeypatch, configured_m11_runner, capsys, missing):
    runner, receipt_dir, token = configured_m11_runner
    monkeypatch.delenv(missing, raising=False)

    def forbidden(session):
        raise AssertionError("The matrix must not run without configuration")

    monkeypatch.setattr(runner, "run_matrix", forbidden)
    assert runner.main() == 2
    assert not receipt_dir.exists()
    output = capsys.readouterr()
    assert token not in output.out + output.err


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


def test_receipt_is_private_and_excludes_credentials(monkeypatch, configured_m11_runner, capsys):
    runner, receipt_dir, token = configured_m11_runner
    monkeypatch.setattr(runner, "run_matrix", lambda session: [{"id": "test", "status": "passed", "details": {}}])
    assert runner.main() == 0
    path = next(receipt_dir.glob("*.json"))
    assert path.stat().st_mode & 0o777 == 0o600
    assert path.parent.stat().st_mode & 0o777 == 0o700
    assert token not in path.read_text()
    assert json.loads(path.read_text())["provider_validation"] == "not_run"
    output = capsys.readouterr()
    assert token not in output.out + output.err


@pytest.mark.parametrize("check_count", [64, 65])
def test_receipt_check_count_bound(monkeypatch, configured_m11_runner, capsys, check_count):
    runner, receipt_dir, token = configured_m11_runner
    checks = [{"id": f"check-{index}", "status": "passed", "details": {}}
              for index in range(check_count)]
    monkeypatch.setattr(runner, "run_matrix", lambda session: checks)

    if check_count == 64:
        assert runner.main() == 0
        paths = list(receipt_dir.glob("*.json"))
        assert len(paths) == 1
        assert json.loads(paths[0].read_text())["checks"] == checks
        assert token not in paths[0].read_text()
    else:
        with pytest.raises(ValueError, match="^M11 receipt check limit exceeded$"):
            runner.main()
        assert not receipt_dir.exists()
    output = capsys.readouterr()
    assert token not in output.out + output.err


@pytest.mark.parametrize("overflow_bytes", [0, 1])
def test_receipt_byte_bound(monkeypatch, configured_m11_runner, capsys, overflow_bytes):
    runner, receipt_dir, token = configured_m11_runner
    details = {"padding": ""}
    checks = [{"id": "byte-bound", "status": "passed", "details": details}]
    monkeypatch.setattr(runner, "run_matrix", lambda session: checks)
    assert runner.main() == 0
    baseline_path = next(receipt_dir.glob("*.json"))
    baseline_size = baseline_path.stat().st_size
    assert token not in baseline_path.read_text()

    # Derive framing overhead from an actual receipt. Use multibyte text so
    # counting characters instead of encoded bytes cannot satisfy this test.
    padding_bytes = 256 * 1024 - baseline_size + overflow_bytes
    details["padding"] = "验" * (padding_bytes // 3) + "x" * (padding_bytes % 3)
    boundary_dir = receipt_dir.parent / "boundary-receipts"
    monkeypatch.setenv("CAPSTONE_M11_RECEIPT_DIR", str(boundary_dir))
    if overflow_bytes == 0:
        assert runner.main() == 0
        paths = list(boundary_dir.glob("*.json"))
        assert len(paths) == 1
        assert paths[0].stat().st_size == 256 * 1024
        assert json.loads(paths[0].read_text())["checks"] == checks
        assert token not in paths[0].read_text()
    else:
        with pytest.raises(ValueError, match="^M11 receipt size limit exceeded$"):
            runner.main()
        assert not boundary_dir.exists()
    output = capsys.readouterr()
    assert token not in output.out + output.err


def test_terminal_matrix_failure_excludes_exception_body(monkeypatch, configured_m11_runner, capsys):
    runner, receipt_dir, token = configured_m11_runner
    response_body = "private-server-response"

    def failed_matrix(session):
        raise RuntimeError(f"{token}: {response_body}")

    monkeypatch.setattr(runner, "run_matrix", failed_matrix)
    assert runner.main() == 1
    paths = list(receipt_dir.glob("*.json"))
    assert len(paths) == 1
    content = paths[0].read_text()
    receipt = json.loads(content)
    assert receipt["checks"] == [{"id": "remote-matrix", "status": "failed",
                                  "details": {"error_type": "RuntimeError"}}]
    assert receipt["provider_validation"] == "not_run"
    output = capsys.readouterr()
    for private_value in (token, response_body):
        assert private_value not in content + output.out + output.err


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
