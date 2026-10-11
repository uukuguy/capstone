from dataclasses import replace

from capstone_agent.task_understanding import SCHEMA, recognize_decision
from capstone_agent.thread_worker import run_pending_attempt
from test_thread_worker import _service, _submit, _Runtime
import pytest
from types import SimpleNamespace


@pytest.mark.parametrize("payload, valid", [
    ({"operation": "read"}, True),
    ({"operation": "read", "count": 3}, True),
    ({"operation": "read", "count": True}, False),
    ({"operation": "read", "private": 3}, False),
    ({"count": 3}, False),
])
def test_declared_optional_fields_do_not_relax_required_or_unknown_fields(payload, valid):
    from capstone_agent.task_recognition import _validate_published_payload_fields
    schema = {"binding_id": "test", "schema": "test/1",
              "payload_fields": {"operation": ["read"], "count": "Optional count"},
              "payload_schema": {"type": "object", "additionalProperties": False,
                  "required": ["operation"], "properties": {
                      "operation": {"enum": ["read"]}, "count": {"type": "integer", "minimum": 1}}}}
    domain = SimpleNamespace(binding_id="test", schema="test/1", payload=payload)
    task = SimpleNamespace(goals=(SimpleNamespace(domain_request=domain, missing_requirements=()),))
    if valid:
        _validate_published_payload_fields(task, (schema,))
    else:
        with pytest.raises(ValueError):
            _validate_published_payload_fields(task, (schema,))


@pytest.mark.parametrize("gap, invalid, allowed", [
    (True, None, True), (False, None, False),
    (True, "unknown-field", False), (True, "wrong-type", False),
])
def test_pending_input_proposal_can_omit_nested_required_values_only(gap, invalid, allowed):
    from capstone_agent.task_recognition import _validate_published_payload_fields
    schema = {"binding_id": "test", "schema": "test/1", "payload_fields": {"changes": [{}]},
        "payload_schema": {"type": "object", "additionalProperties": False, "required": ["changes"],
            "properties": {"changes": {"type": "array", "items": {"type": "object",
                "additionalProperties": False, "required": ["factor"],
                "properties": {"factor": {"type": "number", "exclusiveMinimum": 0}}}}}}}
    item = {}
    if invalid == "unknown-field": item["private"] = "value"
    if invalid == "wrong-type": item["factor"] = "unknown"
    payload = {"changes": [item]}
    domain = SimpleNamespace(binding_id="test", schema="test/1", payload=payload)
    task = SimpleNamespace(goals=(SimpleNamespace(domain_request=domain,
        missing_requirements=("Parameter is not yet chosen",) if gap else ()),))
    if allowed:
        _validate_published_payload_fields(task, (schema,))
        assert payload == {"changes": [{}]}  # No invented executable value.
    else:
        with pytest.raises(ValueError): _validate_published_payload_fields(task, (schema,))


@pytest.mark.parametrize("value", [["line"], "private invalid value"])
def test_published_json_schema_rejects_nested_enum_without_echoing_values(value):
    from capstone_agent.task_recognition import _validate_published_payload_fields
    schema = {"binding_id": "grid", "schema": "test/1", "payload_fields": {"objects": [{}]},
        "payload_schema": {"type": "object", "properties": {"objects": {"type": "array", "items": {
            "type": "object", "properties": {"kind": {"enum": ["line", "bus"]}}, "required": ["kind"],
            "additionalProperties": False}}}, "required": ["objects"], "additionalProperties": False}}
    proposal = SimpleNamespace(binding_id="grid", schema="test/1", payload={"objects": [{"kind": value}]})
    with pytest.raises(ValueError, match="objects.*kind") as error:
        _validate_published_payload_fields(SimpleNamespace(goals=(SimpleNamespace(domain_request=proposal),)), (schema,))
    assert "private invalid value" not in str(error.value)


def pending_snapshot(snapshot, state):
    from capstone_agent.thread_protocol import PendingSelectionSnapshot, PendingModelSwitchSnapshot
    if state == "selection":
        return replace(snapshot, pending_selection=PendingSelectionSnapshot("cmd_pending", (("static-analysis", "1.0.0"),)))
    return replace(snapshot, pending_model_switch=PendingModelSwitchSnapshot("cmd_pending", "other-model", "other-revision", "pandapower", ()))


@pytest.mark.parametrize("kind", ["send_auto", "send_ordinary", "send_professional"])
@pytest.mark.parametrize("state", ["selection", "model"])
def test_oversized_instruction_rejected_before_pending_activation(kind, state):
    from capstone_agent.thread_service import InMemoryThreadService
    snapshot = pending_snapshot(_service().snapshot("thr_worker"), state)
    service = InMemoryThreadService(snapshot)
    command = {"schema": "capstone-command/1", "command_id": "cmd_large", "idempotency_key": "idem_large", "thread_id": "thr_worker", "run_id": "run_worker", "kind": kind, "expected_event_seq": 0, "payload": {"text": "x" * 16385}}
    receipt = service.submit_command(command)
    assert receipt.status == "rejected"
    assert receipt.rejection == "message_text_too_large"
    assert service.snapshot("thr_worker") == snapshot
    assert service.read_events("thr_worker", 0).events == ()


def test_unbounded_pending_revision_rejected_before_context_activation():
    from capstone_agent.thread_service import InMemoryThreadService
    snapshot = pending_snapshot(_service().snapshot("thr_worker"), "model")
    snapshot = replace(snapshot, pending_model_switch=replace(snapshot.pending_model_switch, model_revision="r" * 513))
    service = InMemoryThreadService(snapshot)
    receipt = service.submit_command({"schema": "capstone-command/1", "command_id": "cmd_revision", "idempotency_key": "idem_revision", "thread_id": "thr_worker", "run_id": "run_worker", "kind": "send_auto", "expected_event_seq": 0, "payload": {"text": "inspect"}})
    assert receipt.rejection == "task_context_invalid"
    assert service.snapshot("thr_worker") == snapshot


def proposal():
    return {"schema": SCHEMA, "goals": [{"id": "overview", "purpose": "inspect", "subject": "selected model", "scope": "unspecified", "scenario": "none", "change": None, "conclusion": "description", "measure": None, "obligations": ["describe model"], "missing_requirements": []}], "answer_policy": {"language": "en", "scale": "concise"}}


@pytest.mark.parametrize("response", ['{"schema":"wrong","schema":"capstone-task-understanding/1"}', " " * 24577], ids=["duplicate-fields", "oversized"])
def test_recognition_output_rejects_duplicate_fields_and_unbounded_text(response):
    from capstone_agent.task_recognition import decode_recognition_output
    with pytest.raises(ValueError):
        decode_recognition_output(response)


class Factory:
    def __init__(self, service, *, fail=False):
        self.service, self.fail = service, fail
        self.requests, self.claims = [], []

    def recognize_task(self, claim, *, on_heartbeat):
        self.requests.append(claim.task_request)
        on_heartbeat()
        if self.fail:
            raise ValueError("invalid decision")
        return recognize_decision(claim.task_request, proposal(), recognizer="controlled")

    def __call__(self, claim):
        self.claims.append(claim)
        events = self.service.read_events(claim.thread_id, 0).events
        assert any(e.event_type == "task_understanding_created" for e in events)
        return _Runtime()


def retry(service):
    events = service.read_events("thr_worker", 0).events
    attempt = next(e.attempt_id for e in events if e.event_type == "attempt_started")
    return service.submit_command({"schema": "capstone-command/1", "command_id": "cmd_retry", "idempotency_key": "idem_retry", "thread_id": "thr_worker", "run_id": "run_worker", "kind": "retry_new_attempt", "expected_event_seq": service.snapshot("thr_worker").last_event_seq, "payload": {"attempt_id": attempt}})


def test_family_hosted_recognition_timing_keeps_inner_details():
    from capstone_agent.thread_application import FamilyRuntimeFactory
    from capstone_agent.task_recognition import accept_task
    service = _service()
    _submit(service)
    claim = service.claim_attempt('worker', 30)
    class TimedFactory(Factory):
        def recognition_metrics(self, claim):
            return {'process_reused': True, 'calls': [{'duration_ms': 12}]}
    factory = FamilyRuntimeFactory({claim.model_context.implementation_family: TimedFactory(service)})
    accept_task(service, claim, factory.recognize_task, on_heartbeat=lambda: None)
    timing = next(e for e in service.read_events(claim.thread_id, 0).events if e.event_type == 'task_recognition_timing')
    assert timing.payload['details'] == {'process_reused': True, 'calls': [{'duration_ms': 12}]}


def test_worker_persists_host_bound_task_before_execution():
    service = _service()
    _submit(service)
    factory = Factory(service)
    result = run_pending_attempt(service, factory, worker_id="worker")
    assert result.status == "completed"
    assert factory.claims[0].task_understanding.request == factory.requests[0]
    assert factory.claims[0].task_certification == "recognized"


def test_control_attempt_does_not_run_semantic_recognition():
    service = _service()
    service.submit_command({"schema": "capstone-command/1", "command_id": "cmd_control", "idempotency_key": "idem_control", "thread_id": "thr_worker", "run_id": "run_worker", "kind": "send_control", "expected_event_seq": 0, "payload": {"text": "inspect"}})
    class ControlRuntime(_Runtime):
        def prompt(self, question, **kwargs):
            return "done"
    class ControlFactory(Factory):
        def __call__(self, claim):
            return ControlRuntime()
    factory = ControlFactory(service)
    result = run_pending_attempt(service, factory, worker_id="worker")
    assert result.error_code == "answer_admission_unavailable"
    assert not factory.requests


def test_recognition_failure_stops_before_execution_and_retry_keeps_request():
    service = _service()
    _submit(service)
    factory = Factory(service, fail=True)
    result = run_pending_attempt(service, factory, worker_id="worker")
    assert result.error_code == "task_recognition_failed"
    assert not factory.claims
    timing = next(event for event in service.read_events("thr_worker", 0).events
                  if event.event_type == "task_recognition_timing")
    assert timing.payload["outcome"] == "failed"
    assert timing.payload["duration_ms"] >= 0
    assert set(timing.payload) == {"duration_ms", "outcome", "failure_type", "details"}
    retry(service)
    factory.fail = False
    result = run_pending_attempt(service, factory, worker_id="worker")
    assert result.status == "completed"
    assert factory.requests[0] == factory.requests[1]


def test_recognition_retry_keeps_history_from_original_cutoff():
    service = _service()
    _submit(service)
    assert run_pending_attempt(service, lambda claim: _Runtime(), worker_id="worker").status == "completed"
    service.submit_command({"schema": "capstone-command/1", "command_id": "cmd_followup", "idempotency_key": "idem_followup", "thread_id": "thr_worker", "run_id": "run_worker", "kind": "send_ordinary", "expected_event_seq": service.snapshot("thr_worker").last_event_seq, "payload": {"text": "inspect"}})
    history = []
    class FailingFactory(Factory):
        def recognize_task(self, claim, *, on_heartbeat):
            history.append(claim.task_history)
            raise ValueError("invalid")
    failing = FailingFactory(service)
    run_pending_attempt(service, failing, worker_id="worker")
    events = service.read_events("thr_worker", 0).events
    failed = next(e for e in reversed(events) if e.event_type == "attempt_failed")
    service.submit_command({"schema": "capstone-command/1", "command_id": "cmd_retry_history", "idempotency_key": "idem_retry_history", "thread_id": "thr_worker", "run_id": "run_worker", "kind": "retry_new_attempt", "expected_event_seq": service.snapshot("thr_worker").last_event_seq, "payload": {"attempt_id": failed.attempt_id}})
    run_pending_attempt(service, failing, worker_id="worker")
    assert history == [("inspect", "done"), ("inspect", "done")]


def test_accepted_decision_is_replayed_after_execution_failure():
    service = _service()
    _submit(service)
    factory = Factory(service)
    original = factory.__class__.__call__
    class FailingFactory(Factory):
        def __call__(self, claim):
            original(self, claim)
            raise RuntimeError("execution unavailable")
    failing = FailingFactory(service)
    assert run_pending_attempt(service, failing, worker_id="worker").status == "failed"
    retry(service)
    result = run_pending_attempt(service, factory, worker_id="worker")
    assert result.status == "completed"
    assert not factory.requests
    assert factory.claims[0].task_understanding == failing.claims[0].task_understanding


def test_required_decision_persistence_failure_stops_execution():
    service = _service()
    _submit(service)
    append = service.append_runtime_event
    def fail(claim, *, event_type, **kwargs):
        if event_type == "task_understanding_created":
            raise OSError("ledger unavailable")
        return append(claim, event_type=event_type, **kwargs)
    service.append_runtime_event = fail
    factory = Factory(service)
    result = run_pending_attempt(service, factory, worker_id="worker")
    assert result.error_code == "task_recognition_failed"
    assert not factory.claims


def test_request_persistence_failure_retry_still_requires_recognition():
    service = _service()
    _submit(service)
    append = service.append_runtime_event
    def fail(claim, *, event_type, **kwargs):
        if event_type == "task_request_created":
            raise OSError("ledger unavailable")
        return append(claim, event_type=event_type, **kwargs)
    service.append_runtime_event = fail
    factory = Factory(service)
    assert run_pending_attempt(service, factory, worker_id="worker").error_code == "task_recognition_failed"
    assert not factory.requests
    service.append_runtime_event = append
    service.submit_command({"schema": "capstone-command/1", "command_id": "cmd_later", "idempotency_key": "idem_later", "thread_id": "thr_worker", "run_id": "run_worker", "kind": "send_ordinary", "expected_event_seq": service.snapshot("thr_worker").last_event_seq, "payload": {"text": "inspect"}})
    assert run_pending_attempt(service, lambda claim: _Runtime(), worker_id="worker").status == "completed"
    retry(service)
    assert run_pending_attempt(service, factory, worker_id="worker").status == "completed"
    assert len(factory.requests) == 1
    assert factory.claims[0].task_certification == "recognized"
    assert factory.claims[0].task_history is None
    assert factory.claims[0].task_request.history_cutoff == 0


@pytest.mark.parametrize("boundary", ["write_input", "append_return", "read_output"])
def test_task_event_nested_mutation_cannot_change_replay(boundary):
    from capstone_agent.task_recognition import accept_task
    service = _service()
    _submit(service)
    claim = service.claim_attempt("worker", 30)
    captured = []
    append = service.append_runtime_event
    def capture(claim, *, event_type, payload, **kwargs):
        if event_type == "task_understanding_created":
            captured.append(payload)
        return append(claim, event_type=event_type, payload=payload, **kwargs)
    service.append_runtime_event = capture
    task = accept_task(service, claim, Factory(service).recognize_task, on_heartbeat=lambda: None)
    document = task.task_understanding.to_document()
    returned = service.append_runtime_event(task, event_type="task_understanding_created", payload={"understanding": document})
    if boundary == "write_input":
        captured[0]["understanding"]["answer_policy"]["scale"] = "detailed"
    elif boundary == "append_return":
        returned.payload["understanding"]["answer_policy"]["scale"] = "detailed"
    else:
        event = next(e for e in service.read_events("thr_worker", 0).events if e.event_type == "task_understanding_created")
        event.payload["understanding"]["answer_policy"]["scale"] = "detailed"
    service.finish_attempt(task, phase="failed", payload={"error_code": "controlled"})
    retry(service)
    replay = service.claim_attempt("worker", 30)
    assert replay.task_understanding == task.task_understanding


@pytest.mark.parametrize("phase", ["before", "during"])
def test_direct_harness_recognition_cancellation_stays_cancelled(phase):
    from capstone_agent.harness import HarnessAttemptRunner
    service = _service()
    _submit(service)
    claim = service.claim_attempt("worker", 30)
    if phase == "before":
        service._cancel_requests.add(claim.attempt.attempt_id)
    def recognize(bound, *, on_heartbeat):
        service._cancel_requests.add(bound.attempt.attempt_id)
        on_heartbeat()
        return recognize_decision(bound.task_request, proposal(), recognizer="controlled")
    result = HarnessAttemptRunner(service, _Runtime(), task_recognizer=recognize).run(claim)
    assert result.status == "cancelled"
    retry(service)
    replay = service.claim_attempt("worker", 30)
    assert replay.task_certification == "pending"
    assert replay.task_request == claim.task_request


@pytest.mark.parametrize("field,value", [("attempt_id", "attempt_foreign"), ("history_cutoff", 99)])
def test_acceptance_marker_rejects_foreign_attempt_or_cutoff(field, value):
    from capstone_agent.task_recognition import task_state_from_events
    service = _service()
    _submit(service)
    claim = service.claim_attempt("worker", 30)
    events = list(service.read_events("thr_worker", 0).events)
    accepted = events[0]
    accepted.payload["task_recognition"]["request"][field] = value
    with pytest.raises(ValueError, match="acceptance identity"):
        task_state_from_events(events, thread_id=claim.thread_id, attempt=claim.attempt,
                               instruction=claim.instruction, context=claim.model_context)


def test_legacy_retry_is_explicit_and_does_not_recognize():
    service = _service()
    _submit(service)
    # Restore the shape of a record accepted by the historical release.
    service._events[0] = replace(service._events[0], payload={key: value for key, value in service._events[0].payload.items() if key != "task_recognition"})
    claim = service.claim_attempt("worker", 30)
    service.finish_attempt(claim, phase="failed", payload={"error_code": "old_failure"})
    retry(service)
    factory = Factory(service)
    class LegacyFactory(Factory):
        def __call__(self, claim):
            self.claims.append(claim)
            return _Runtime()
    factory = LegacyFactory(service)
    result = run_pending_attempt(service, factory, worker_id="worker")
    assert result.status == "completed"
    assert not factory.requests
    assert factory.claims[0].task_certification == "legacy_uncertified"
    assert factory.claims[0].task_understanding is None


def test_cancel_during_recognition_does_not_execute():
    service = _service()
    _submit(service)
    class CancelFactory(Factory):
        def recognize_task(self, claim, *, on_heartbeat):
            service._cancel_requests.add(claim.attempt.attempt_id)
            return recognize_decision(claim.task_request, proposal(), recognizer="controlled")
    factory = CancelFactory(service)
    result = run_pending_attempt(service, factory, worker_id="worker")
    assert result.status == "cancelled"
    assert not factory.claims


def test_rpc_recognition_has_no_extension_or_domain_paths(monkeypatch, tmp_path):
    from capstone_agent import task_recognition
    service = _service()
    _submit(service)
    claim = service.claim_attempt("worker", 30)
    captured = []
    clients = []
    def launch(llm, paths, **kwargs):
        captured.append(paths)
        return SimpleNamespace(argv=("pi",), environment={})
    class Client:
        def __init__(self, *args, **kwargs):
            clients.append(args[0])
        def start(self):
            pass
        def stop(self):
            pass
        def prompt_and_wait(self, prompt, **kwargs):
            import json
            assert json.loads(prompt)["request"]["instruction"] == "inspect"
            return json.dumps(proposal())
    monkeypatch.setattr(task_recognition, "build_pi_launch", launch)
    monkeypatch.setattr(task_recognition, "PiRpcClient", Client)
    host = SimpleNamespace(command=SimpleNamespace(argv=("pi",)), project_pi_dir=tmp_path, extension_path=tmp_path / "domain-extension.ts")
    llm = SimpleNamespace(secret=None, config=SimpleNamespace(model="controlled"))
    task = task_recognition.recognize_with_pi(claim, runtime_host=host, resolved_llm=llm,
                                             base_environment={}, timeout_seconds=60, on_heartbeat=lambda: None)
    assert task.request == claim.task_request
    assert captured[0].extension_path is None
    assert captured[0].domain_search_paths == ()
    assert captured[0].runtime_descriptor_path is None
    assert clients[0].argv[-2:] == ("--thinking", "off")


@pytest.mark.parametrize("accepted", ["general", "professional"])
def test_compiler_repairs_a_route_mismatch_before_acceptance(monkeypatch, tmp_path, accepted):
    import json
    from capstone_agent import task_recognition
    from capstone_agent.task_routing import TaskRoute
    from capstone_agent.task_understanding import SCHEMA_V2
    service = _service()
    _submit(service)
    claim = service.claim_attempt("worker", 30)
    claim = replace(claim, task_route=TaskRoute(claim.task_request, accepted))
    prompts = []

    class Client:
        def __init__(self, *args, **kwargs): pass
        def start(self): pass
        def stop(self): pass
        def prompt_and_wait(self, prompt, **kwargs):
            prompts.append(json.loads(prompt))
            execution = accepted if len(prompts) == 2 else ("general" if accepted == "professional" else "professional")
            decision = proposal()
            decision["schema"] = SCHEMA_V2
            decision["goals"][0].update(execution=execution, dependencies=[], domain_request=(
                {"binding_id": "grid", "schema": "test/1", "payload": {"operation": "overview"}}
                if execution == "professional" else None))
            return json.dumps(decision)

    monkeypatch.setattr(task_recognition, "build_pi_launch", lambda *args, **kwargs: SimpleNamespace(argv=("pi",), environment={}))
    monkeypatch.setattr(task_recognition, "PiRpcClient", Client)
    task = task_recognition.recognize_with_pi(claim,
        runtime_host=SimpleNamespace(command=SimpleNamespace(argv=("pi",)), project_pi_dir=tmp_path),
        resolved_llm=SimpleNamespace(secret=None, config=SimpleNamespace(model="controlled")),
        base_environment={}, timeout_seconds=60, on_heartbeat=lambda: None,
        requirement_schemas=({"binding_id": "grid", "schema": "test/1", "payload_fields": {"operation": ["overview"]}},))
    assert task.goals[0].execution == accepted
    assert len(prompts) == 2
    assert "accepted task route" in prompts[1]["validation_error"]


@pytest.mark.parametrize("repair", [True, False])
@pytest.mark.parametrize("malformed", ["missing-field", "enum-array"])
@pytest.mark.parametrize("gap", [False, True])
def test_rpc_repairs_missing_published_payload_field_before_acceptance(monkeypatch, tmp_path, repair, malformed, gap):
    import json
    from capstone_agent import task_recognition
    from capstone_agent.task_understanding import SCHEMA_V2
    service = _service()
    _submit(service)
    claim = service.claim_attempt("worker", 30)
    decision = proposal()
    decision["schema"] = SCHEMA_V2
    decision["goals"][0].update(execution="professional", dependencies=[], domain_request={
        "binding_id": "grid", "schema": "test-requirement/1", "payload": {"operation": "overview"}})
    if gap:
        decision["goals"][0]["missing_requirements"] = ["Unresolved user choice"]
    if malformed == "enum-array":
        decision["goals"][0]["domain_request"]["payload"]["direction"] = ["descending"]
    prompts = []
    timeouts = []
    class Client:
        def __init__(self, *args, **kwargs): pass
        def start(self): pass
        def stop(self): pass
        def prompt_and_wait(self, prompt, **kwargs):
            prompts.append(json.loads(prompt))
            timeouts.append(kwargs["timeout_seconds"])
            if repair and len(prompts) == 2:
                decision["goals"][0]["domain_request"]["payload"]["direction"] = "descending"
            return json.dumps(decision)
    monkeypatch.setattr(task_recognition, "build_pi_launch", lambda *args, **kwargs: SimpleNamespace(argv=("pi",), environment={}))
    monkeypatch.setattr(task_recognition, "PiRpcClient", Client)
    arguments = dict(runtime_host=SimpleNamespace(command=SimpleNamespace(argv=("pi",)), project_pi_dir=tmp_path),
                     resolved_llm=SimpleNamespace(secret=None, config=SimpleNamespace(model="controlled")),
                     base_environment={}, timeout_seconds=60, on_heartbeat=lambda: None,
                     requirement_schemas=({"binding_id": "grid", "schema": "test-requirement/1",
                                           "payload_fields": {"operation": ["overview"], "direction": ["ascending", "descending"]}},))
    if repair:
        task = task_recognition.recognize_with_pi(claim, **arguments)
        assert task.goals[0].domain_request.payload["direction"] == "descending"
        assert bool(task.goals[0].missing_requirements) == gap
    else:
        with pytest.raises(ValueError, match="payload fields"):
            task_recognition.recognize_with_pi(claim, **arguments)
    assert len(prompts) == 2
    assert prompts[1]["request"] == prompts[0]["request"]
    assert "direction" in prompts[1]["validation_error"]
    assert 0 < timeouts[1] <= timeouts[0] <= 60


def test_harness_recognizes_before_start_and_exposes_task_to_admission():
    from capstone_agent.harness import HarnessAttemptRunner
    service = _service()
    _submit(service)
    claim = service.claim_attempt("worker", 30)
    captured = []
    class Runtime(_Runtime):
        def start(self):
            assert any(e.event_type == "task_understanding_created" for e in service.read_events(claim.thread_id, 0).events)
        def admit_attempt(self, bound, *args):
            captured.append(bound.task_understanding)
    def recognize(bound, *, on_heartbeat):
        return recognize_decision(bound.task_request, proposal(), recognizer="controlled")
    result = HarnessAttemptRunner(service, Runtime(), task_recognizer=recognize).run(claim)
    assert result.status == "completed"
    assert captured[0].request == claim.task_request


def test_task_decision_cannot_be_replaced_in_running_turn():
    from capstone_agent.task_recognition import accept_task
    service = _service()
    _submit(service)
    claim = service.claim_attempt("worker", 30)
    bound = accept_task(service, claim, Factory(service).recognize_task, on_heartbeat=lambda: None)
    document = bound.task_understanding.to_document()
    document["answer_policy"]["scale"] = "detailed"
    with pytest.raises(Exception, match="immutable"):
        service.append_runtime_event(bound, event_type="task_understanding_created",
                                     payload={"understanding": document}, visibility="diagnostic")


@pytest.mark.parametrize("family", ["pandapower", "pypsa"])
def test_m11_scripted_recognition_is_finite_and_provider_free(family, monkeypatch):
    from pathlib import Path
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[3]))
    from validation.thread.m11_session import build_m11_session_builder, INSTRUCTIONS, MODELS
    from capstone_agent.task_understanding import TaskRequest
    request = TaskRequest("thread", "turn", "attempt", INSTRUCTIONS[family][0], 0,
                          "context", MODELS[family], "revision")
    claim = SimpleNamespace(task_request=request, instruction=request.instruction,
                            model_context=SimpleNamespace(implementation_family=family, model_id=MODELS[family]))
    builder = build_m11_session_builder(family)
    task = builder.recognize_task(claim, on_heartbeat=lambda: None)
    assert task.request == request
    assert task.goals[0].scenario == "baseline"
    claim.instruction = "unregistered instruction"
    with pytest.raises(ValueError):
        builder.recognize_task(claim, on_heartbeat=lambda: None)


@pytest.mark.parametrize("review", ["satisfied", "unresolved", "invalid"])
@pytest.mark.parametrize("schema", ["test/1", "capstone-professional-task/1"])
@pytest.mark.parametrize("has_gap", [True, False])
@pytest.mark.parametrize("composition", ["single", "mixed", "contracts", "duplicate"])
def test_professional_choices_receive_one_bounded_preacceptance_review(monkeypatch, tmp_path, review, schema, has_gap, composition):
    import copy
    import json
    from capstone_agent import task_recognition
    from capstone_agent.task_understanding import SCHEMA_V2
    service = _service()
    _submit(service)
    claim = service.claim_attempt("worker", 30)
    decision = proposal()
    decision["schema"] = SCHEMA_V2
    decision["goals"][0].update(execution="professional", dependencies=[], scope="subset",
        missing_requirements=["Possible missing user choice"] if has_gap else [], domain_request={
            "binding_id": "test", "schema": schema, "payload": {"operation": "inspect"}})
    if composition != "single":
        decision["goals"][0].update(scope="full", scenario="baseline", change=None,
                                    measure=None, missing_requirements=[])
        extra = copy.deepcopy(decision["goals"][0])
        extra.update(id="independent", purpose="Separate user objective")
        if composition == "duplicate":
            extra["purpose"] = decision["goals"][0]["purpose"]
        if composition == "mixed":
            extra.update(execution="general", scenario="none", domain_request=None)
        else:
            extra["domain_request"]["schema"] = "other/1"
        decision["goals"].append(extra)
    prompts, timeouts = [], []
    class Client:
        def __init__(self, *args, **kwargs): pass
        def start(self): pass
        def stop(self): pass
        def prompt_and_wait(self, prompt, **kwargs):
            prompts.append(json.loads(prompt))
            timeouts.append(kwargs["timeout_seconds"])
            result = copy.deepcopy(decision)
            if len(prompts) == 2:
                if composition == "duplicate": result["goals"].pop()
                if review == "satisfied": result["goals"][0]["missing_requirements"] = []
                if review == "invalid": result["goals"][0]["domain_request"]["payload"] = {}
            return json.dumps(result)
    monkeypatch.setattr(task_recognition, "build_pi_launch", lambda *args, **kwargs: SimpleNamespace(argv=("pi",), environment={}))
    monkeypatch.setattr(task_recognition, "PiRpcClient", Client)
    arguments = dict(runtime_host=SimpleNamespace(command=SimpleNamespace(argv=("pi",)), project_pi_dir=tmp_path),
        resolved_llm=SimpleNamespace(secret=None, config=SimpleNamespace(model="controlled")),
        base_environment={}, timeout_seconds=60, on_heartbeat=lambda: None,
        requirement_schemas=({"binding_id": "test", "schema": schema, "payload_fields": {"operation": ["inspect"]}},
                            {"binding_id": "test", "schema": "other/1", "payload_fields": {"operation": ["inspect"]}}))
    if review == "invalid":
        with pytest.raises(ValueError): task_recognition.recognize_with_pi(claim, **arguments)
    else:
        task = task_recognition.recognize_with_pi(claim, **arguments)
        assert bool(task.goals[0].missing_requirements) == (review == "unresolved" and has_gap and composition == "single")
        assert len(task.goals) == (1 if composition in {"single", "duplicate"} else 2)
    assert len(prompts) == 2
    assert prompts[1]["candidate"] == decision
    assert prompts[1]["request"] == prompts[0]["request"]
    assert "semantic_review" in prompts[1]
    assert 0 < timeouts[1] <= timeouts[0] <= 60
