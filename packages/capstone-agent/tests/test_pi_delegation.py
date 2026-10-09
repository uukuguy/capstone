import copy
import json
import threading
import time
from dataclasses import FrozenInstanceError
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from capstone_agent.pi_delegation import HttpGeneralPiExecutor, PiTaskRequest, PiTaskResult
from capstone_agent.request_intent import NodeControl


def request_document(entrypoint="delegated"):
    return {"schema": "capstone-pi-task/1", "task_id": "task-1", "parent_attempt_id": "attempt-1",
            "entrypoint": entrypoint, "instruction": "Explain this text.", "messages": [],
            "dependency_results": [], "executor_identity": {"engine": "pi", "config_revision": "v1"},
            "timeout_seconds": 2}


def result_document(request):
    return {"schema": "capstone-pi-task-result/1", "task_id": request.task_id,
            "parent_attempt_id": request.parent_attempt_id, "executor_identity": dict(request.executor_identity),
            "status": "completed", "answer": "Done.", "sources": [], "artifacts": [], "usage": {"tokens": 1}}


def test_documents_are_defensive_and_immutable():
    document = request_document()
    request = PiTaskRequest.from_document(document)
    document["executor_identity"]["engine"] = "other"
    request.to_document()["executor_identity"]["engine"] = "other"
    assert request.executor_identity["engine"] == "pi"
    with pytest.raises(TypeError):
        request.executor_identity["engine"] = "other"
    with pytest.raises(FrozenInstanceError):
        request.task_id = "other"
    result = PiTaskResult.from_document(result_document(request), request)
    result.to_document()["usage"]["tokens"] = 99
    assert result.usage["tokens"] == 1


def v2_document(kind='text'):
    from capstone_agent.business_context import BusinessContext
    document = request_document()
    document.update(schema='capstone-pi-task/2', business_context=BusinessContext.empty('thread1', 12).to_document(),
                    resource_profile={'profile_id': 'general', 'revision': 'sha256:' + 'b' * 64},
                    input={'kind': kind, 'text': document['instruction']})
    if kind == 'skill_invocation':
        document['input'].update(skill_id='explain', skill_version='v1')
    return document


def test_legacy_positional_constructor_preserves_exact_v1_document():
    document = request_document()
    request = PiTaskRequest(*(document[field] for field in
        ('task_id', 'parent_attempt_id', 'entrypoint', 'instruction', 'messages',
         'dependency_results', 'executor_identity', 'timeout_seconds')))
    assert request.to_document() == document


@pytest.mark.parametrize('kind', ['text', 'skill_invocation'])
def test_v2_round_trip_freezes_context_profile_and_typed_input(kind):
    document = v2_document(kind)
    original = copy.deepcopy(document)
    request = PiTaskRequest.from_document(document)
    document['resource_profile']['revision'] = 'changed'
    request.to_document()['input']['text'] = 'changed'
    assert request.to_document() == original
    assert request.business_context.to_document() == original['business_context']
    with pytest.raises(TypeError):
        request.resource_profile['revision'] = 'changed'
    constructed = PiTaskRequest(**{k: v for k, v in original.items() if k != 'schema'})
    assert constructed.to_document() == original
    assert PiTaskResult.from_document(result_document(request), request).status == 'completed'


@pytest.mark.parametrize('field', ['business_context', 'resource_profile', 'input'])
def test_v2_rejects_partial_fields_and_v1_downgrade(field):
    document = v2_document()
    document.pop(field)
    with pytest.raises(ValueError):
        PiTaskRequest.from_document(document)
    with pytest.raises(ValueError):
        PiTaskRequest(**{k: v for k, v in document.items() if k != 'schema'})
    document = v2_document()
    document['schema'] = 'capstone-pi-task/1'
    with pytest.raises(ValueError):
        PiTaskRequest.from_document(document)


@pytest.mark.parametrize('mutation', [
    lambda d: d['input'].update(text='different'),
    lambda d: d['input'].update(kind='shell'),
    lambda d: d['input'].update(skill_id='not-typed'),
    lambda d: d['input'].update(token='secret'),
    lambda d: d['input'].update(kind='skill_invocation'),
    lambda d: d['resource_profile'].update(revision=''),
    lambda d: d['resource_profile'].update(extra='private'),
    lambda d: d['resource_profile'].update(profile_id='x' * 257),
    lambda d: d['business_context'].update(snapshot_id='sha256:' + '0' * 64),
    lambda d: d['executor_identity'].update(model_revision='private'),
    lambda d: d.update(extra=True),
])
def test_v2_rejects_invalid_inputs_and_retains_generic_protected_fields(mutation):
    document = v2_document()
    mutation(document)
    with pytest.raises(ValueError):
        PiTaskRequest.from_document(document)


def test_v2_enforces_total_envelope_bounds_and_rejects_forged_result_evidence():
    document = v2_document()
    document['executor_identity'].update({f'field{i}': 'x' * 65536 for i in range(4)})
    with pytest.raises(ValueError, match='byte bounds'):
        PiTaskRequest.from_document(document)
    request = PiTaskRequest.from_document(v2_document())
    result = result_document(request)
    result['usage']['evidence_refs'] = ['forged']
    with pytest.raises(ValueError, match='protected'):
        PiTaskResult.from_document(result, request)


def test_v2_combined_envelope_budget_includes_input_and_context():
    document = v2_document()
    document['instruction'] = 'x' * 65536
    document['input']['text'] = document['instruction']
    document['executor_identity'].update({f'field{i}': 'x' * 45000 for i in range(3)})
    # Each part and the v1 request fit, but their v2 combination does not.
    legacy = {k: v for k, v in document.items() if k not in {'business_context', 'resource_profile', 'input'}}
    legacy['schema'] = 'capstone-pi-task/1'
    PiTaskRequest.from_document(legacy)
    with pytest.raises(ValueError, match='byte bounds'):
        PiTaskRequest.from_document(document)


@pytest.mark.parametrize("field,value", [("extra", 1), ("timeout_seconds", 0), ("timeout_seconds", float("nan")),
    ("timeout_seconds", True), ("timeout_seconds", 3601), ("instruction", "x" * 65537),
    ("entrypoint", "shell"), ("executor_identity", {}), ("dependency_results", [{"evidence_refs": []}])])
def test_request_rejects_invalid_fields(field, value):
    document = request_document()
    document[field] = value
    with pytest.raises(ValueError):
        PiTaskRequest.from_document(document)


def test_history_uses_conversation_contract_and_unique_ids():
    document = request_document()
    message = {"message_id": "m", "role": "user", "content": "hello", "turn_id": "t",
               "attempt_id": "a", "model_context_id": "c", "status": "completed"}
    document["messages"] = [message]
    assert PiTaskRequest.from_document(document).messages[0]["content"] == "hello"
    document["messages"].append(copy.deepcopy(message))
    with pytest.raises(ValueError):
        PiTaskRequest.from_document(document)
    document["messages"] = [{"role": "system", "content": "secret"}]
    with pytest.raises(ValueError):
        PiTaskRequest.from_document(document)


@pytest.mark.parametrize("field,value", [("task_id", "other"), ("parent_attempt_id", "other"),
    ("executor_identity", {"engine": "other"}), ("status", "running"), ("usage", {"tokens": float("inf")}),
    ("extra", 1), ("sources", [{"source_id": "s", "task_id": "other", "parent_attempt_id": "attempt-1", "kind": "web", "metadata": {}}])])
def test_result_is_bound_to_host_request(field, value):
    request = PiTaskRequest.from_document(request_document())
    document = result_document(request)
    document[field] = value
    with pytest.raises(ValueError):
        PiTaskResult.from_document(document, request)


def test_sources_and_artifacts_require_unique_host_identity():
    request = PiTaskRequest.from_document(request_document())
    document = result_document(request)
    source = {"source_id": "s", "task_id": request.task_id, "parent_attempt_id": request.parent_attempt_id,
              "kind": "web", "metadata": {"url": "https://example.org"}}
    document["sources"] = [source]
    assert PiTaskResult.from_document(document, request).sources[0]["source_id"] == "s"
    document["sources"].append(copy.deepcopy(source))
    with pytest.raises(ValueError):
        PiTaskResult.from_document(document, request)
    document["sources"] = []
    document["artifacts"] = [{"artifact_id": "f", "task_id": request.task_id,
        "parent_attempt_id": request.parent_attempt_id, "kind": "text", "metadata": {"result_refs": ["fake"]}}]
    with pytest.raises(ValueError):
        PiTaskResult.from_document(document, request)


@pytest.fixture
def service():
    state = {"requests": [], "cancelled": [], "running": False, "headers": [], "polls": 0}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def send(self, document):
            body = json.dumps(document).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            state["headers"].append(self.headers.get("Authorization"))
            document = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            state["requests"].append(document)
            self.send({"task_id": document["task_id"]})

        def do_GET(self):
            state["polls"] += 1
            if state.get("delay"):
                time.sleep(state["delay"])
            request = PiTaskRequest.from_document(state["requests"][-1] if state["requests"] else request_document())
            if state["cancelled"] and not state.get("cancel_running"):
                result = result_document(request)
                result["status"] = "cancelled"
                self.send(state.get("cancel_response", {"status": "cancelled", "events": [], "result": result}))
                return
            if "response" in state:
                self.send(state["response"])
                return
            self.send({"status": "running" if state["running"] else "completed",
                       "events": [{"event_id": "e1", "type": "progress", "text": "Working."}],
                       "result": None if state["running"] else result_document(request)})

        def do_DELETE(self):
            state["cancelled"].append(self.path)
            if state.get("slow_delete_headers"):
                body = json.dumps({"task_id": "task-1", "status": "cancellation_requested"}).encode()
                headers = b"X-Slow: " + b"x" * 40 + b"\r\nContent-Length: " + str(len(body)).encode() + b"\r\n\r\n"
                try:
                    self.wfile.write(b"HTTP/1.1 200 OK\r\n")
                    self.wfile.flush()
                    for byte in headers:
                        self.wfile.write(bytes([byte]))
                        self.wfile.flush()
                        time.sleep(0.03)
                    self.wfile.write(body)
                except (BrokenPipeError, ConnectionResetError):
                    pass
                return
            if state.get("slow_delete"):
                body = json.dumps({"task_id": "task-1", "status": "cancellation_requested"}).encode()
                body += b" " * 40
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                try:
                    self.wfile.write(body[:-40])
                    self.wfile.flush()
                    for _ in range(40):
                        time.sleep(0.025)
                        self.wfile.write(b" ")
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    pass
                return
            self.send(state.get("delete_response", {"task_id": "task-1", "status": "cancellation_requested"}))

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}", state
    server.shutdown()
    thread.join()
    server.server_close()


def executor(origin):
    return HttpGeneralPiExecutor(origin, identity=request_document()["executor_identity"],
                                 capability={"capability_id": "general_pi", "available": True},
                                 poll_interval_seconds=0.001)


def test_direct_and_delegated_share_executor_identity(service):
    origin, state = service
    client = executor(origin)
    events = []
    for entrypoint in ("direct", "delegated"):
        request = PiTaskRequest.from_document(request_document(entrypoint))
        result = client.execute(request, NodeControl(lambda: None, time.monotonic() + 2), events.append)
        assert result.executor_identity == client.identity
        assert result.status == "completed"
    assert [r["entrypoint"] for r in state["requests"]] == ["direct", "delegated"]
    assert state["requests"][0]["executor_identity"] == state["requests"][1]["executor_identity"]
    assert len(events) == 2
    assert not state["cancelled"]


@pytest.mark.parametrize("reason", ["cancel", "timeout"])
def test_parent_stop_cancels_remote_task(service, reason):
    origin, state = service
    state["running"] = True
    checks = 0

    def check():
        nonlocal checks
        checks += 1
        if reason == "cancel" and checks >= 3:
            raise RuntimeError("parent cancelled")

    request = PiTaskRequest.from_document(request_document())
    with pytest.raises(RuntimeError if reason == "cancel" else TimeoutError):
        executor(origin).execute(request, NodeControl(check, time.monotonic() + 0.08), lambda _: None)
    assert state["cancelled"] == ["/tasks/task-1"]


def test_request_budget_cancels_and_deduplicates_events(service):
    origin, state = service
    state["running"] = True
    document = request_document()
    document["timeout_seconds"] = 0.08
    events = []
    with pytest.raises(TimeoutError):
        executor(origin).execute(PiTaskRequest.from_document(document),
                                 NodeControl(lambda: None, time.monotonic() + 2), events.append)
    assert len(events) == 1
    assert state["polls"] > 1
    assert state["cancelled"] == ["/tasks/task-1"]


@pytest.mark.parametrize("field,value", [("status", []), ("entrypoint", []),
    ("executor_identity", {"credentials": "no"}), ("usage", {"depth": [[[[[[[[[[[[[[1]]]]]]]]]]]]]]})])
def test_malformed_shapes_fail_with_validation_error(field, value):
    request = PiTaskRequest.from_document(request_document())
    document = result_document(request) if field in {"status", "usage"} else request_document()
    document[field] = value
    with pytest.raises(ValueError):
        if field in {"status", "usage"}:
            PiTaskResult.from_document(document, request)
        else:
            PiTaskRequest.from_document(document)


def test_response_bounds_cancel_remote_task(service):
    origin, state = service
    state["response"] = {"status": "running", "events": [], "result": None, "extra": "x" * 300000}
    with pytest.raises(ValueError, match="byte bounds"):
        executor(origin).execute(PiTaskRequest.from_document(request_document()),
                                 NodeControl(lambda: None, time.monotonic() + 2), lambda _: None)
    assert state["cancelled"] == ["/tasks/task-1"]


def test_control_token_stays_in_transport_header(service):
    origin, state = service
    client = HttpGeneralPiExecutor(origin, identity=request_document()["executor_identity"],
                                  capability={"capability_id": "general_pi"}, control_token="private-test-token")
    result = client.execute(PiTaskRequest.from_document(request_document()),
                            NodeControl(lambda: None, time.monotonic() + 2), lambda _: None)
    assert state["headers"] == ["Bearer private-test-token"]
    assert "private-test-token" not in repr(client)
    assert "private-test-token" not in json.dumps(result.to_document())


def test_cancellation_failure_keeps_original_parent_stop(service):
    origin, state = service
    state["running"] = True
    client = executor(origin)
    checks = 0

    def check():
        nonlocal checks
        checks += 1
        if checks >= 3:
            raise TimeoutError("parent deadline")

    def cancel(_):
        raise RuntimeError("service unreachable")

    client.cancel = cancel
    with pytest.raises(TimeoutError, match="parent deadline") as caught:
        client.execute(PiTaskRequest.from_document(request_document()),
                       NodeControl(check, time.monotonic() + 2), lambda _: None)
    assert any("unknown" in note for note in caught.value.__notes__)


def test_slow_response_obeys_parent_deadline(service):
    origin, state = service
    state["delay"] = 0.12
    with pytest.raises(TimeoutError):
        executor(origin).execute(PiTaskRequest.from_document(request_document()),
                                 NodeControl(lambda: None, time.monotonic() + 0.06), lambda _: None)
    assert state["cancelled"] == ["/tasks/task-1"]


@pytest.mark.parametrize("receipt", [{}, {"task_id": "other", "status": "cancellation_requested"},
    {"task_id": "task-1", "status": "completed"},
    {"task_id": "task-1", "status": "cancellation_requested", "extra": True}])
def test_cancel_requires_bound_exact_receipt(service, receipt):
    origin, state = service
    state["delete_response"] = receipt
    with pytest.raises(ValueError, match="cancellation receipt"):
        executor(origin).cancel("task-1")


def test_cancel_has_total_budget_for_continuous_slow_body(service):
    origin, state = service
    state["slow_delete"] = True
    start = time.monotonic()
    with pytest.raises(TimeoutError):
        executor(origin).cancel("task-1")
    assert time.monotonic() - start < 0.85


@pytest.mark.parametrize("reason", ["cancel", "deadline"])
def test_event_callback_parent_stop_prevents_completed_return(service, reason):
    origin, state = service
    stopped = False

    def check():
        if stopped:
            raise RuntimeError("parent stopped during event")

    def on_event(_):
        nonlocal stopped
        if reason == "cancel":
            stopped = True
        else:
            time.sleep(0.09)

    with pytest.raises(RuntimeError if reason == "cancel" else TimeoutError):
        executor(origin).execute(PiTaskRequest.from_document(request_document()),
                                 NodeControl(check, time.monotonic() + 0.07), on_event)
    assert state["cancelled"] == ["/tasks/task-1"]


def test_cancel_waits_for_stopped_state_and_reports_unknown(service):
    origin, state = service
    state["running"] = True
    state["cancel_running"] = True
    start = time.monotonic()
    with pytest.raises(TimeoutError):
        executor(origin).cancel("task-1")
    assert state["polls"] > 1
    assert time.monotonic() - start < 0.85


def test_cancel_rejects_terminal_result_for_other_task(service):
    origin, state = service
    request = PiTaskRequest.from_document(request_document())
    result = result_document(request)
    result["task_id"] = "other"
    state["cancel_response"] = {"status": "completed", "events": [], "result": result}
    with pytest.raises(ValueError):
        executor(origin).cancel("task-1")


def test_cancel_accepts_already_completed_bound_task(service):
    origin, state = service
    request = PiTaskRequest.from_document(request_document())
    state["cancel_response"] = {"status": "completed", "events": [], "result": result_document(request)}
    executor(origin).cancel("task-1")
    assert state["polls"] == 1


def test_cancel_total_budget_includes_dripped_response_headers(service):
    origin, state = service
    state["slow_delete_headers"] = True
    start = time.monotonic()
    with pytest.raises((TimeoutError, RuntimeError)):
        executor(origin).cancel("task-1")
    assert time.monotonic() - start < 0.75
