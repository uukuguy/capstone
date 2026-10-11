from types import SimpleNamespace

import pytest

from capstone_agent.task_understanding import TaskRequest


def test_route_contract_keeps_the_original_question_and_has_no_business_parameters():
    from capstone_agent.task_routing import TaskRoute
    request = TaskRequest("thread", "turn", "attempt", "原始开放式业务问题", 0,
                          "context", "model", "revision")
    route = TaskRoute(request, "professional")
    assert route.to_document() == {"schema": "capstone-intent-route/1",
                                   "request": request.to_document(), "route": "professional"}
    assert TaskRoute.from_document(route.to_document(), request=request) == route
    with pytest.raises(ValueError):
        TaskRoute.from_document({**route.to_document(), "measure": "invented"}, request=request)
    with pytest.raises(ValueError):
        TaskRoute(request, "unknown")


def test_light_route_prompt_excludes_execution_contracts_and_rejects_tools(monkeypatch):
    from contextlib import contextmanager
    from capstone_agent.task_routing import route_with_pi
    request = TaskRequest("thread", "turn", "attempt", "分析所选业务模型", 0,
                          "context", "model", "revision")
    prompts = []
    class Client:
        def prompt_and_wait(self, prompt, **kwargs):
            import json
            prompts.append(json.loads(prompt))
            kwargs["on_event"]({"type": "tool_execution_start"})
            return '{"schema":"capstone-intent-route/1","route":"professional"}'
    class Process:
        @contextmanager
        def lease(self, *args, **kwargs):
            yield Client(), True
    claim = SimpleNamespace(task_request=request, task_history=None, kind="send_auto",
        model_context=SimpleNamespace(model_id="model", implementation_family="test"))
    llm = SimpleNamespace(config=SimpleNamespace(model="test", provider="test"))
    with pytest.raises(ValueError, match="tool"):
        route_with_pi(claim, runtime_host=None, resolved_llm=llm, base_environment={},
                      timeout_seconds=10, on_heartbeat=lambda: None, prepared_process=Process())
    assert set(prompts[0]) == {"instruction", "history", "selected_model"}
    assert prompts[0]["instruction"] == request.instruction


def test_routing_is_frozen_before_compilation_and_reused_after_compilation_failure():
    from test_task_recognition import Factory, retry
    from test_thread_worker import _service, _submit
    from capstone_agent.thread_worker import run_pending_attempt
    from capstone_agent.task_routing import TaskRoute
    service = _service()
    _submit(service)
    class RoutedFactory(Factory):
        route_calls = 0
        def route_task(self, claim, *, on_heartbeat):
            self.route_calls += 1
            return TaskRoute(claim.task_request, "general")
        def routing_metrics(self, claim):
            return {"phase": "routing", "calls": [{"duration_ms": 5}]}
        def recognize_task(self, claim, *, on_heartbeat):
            assert claim.task_route.route == "general"
            events = self.service.read_events(claim.thread_id, 0).events
            assert any(event.event_type == "task_route_created" for event in events)
            return super().recognize_task(claim, on_heartbeat=on_heartbeat)
    factory = RoutedFactory(service, fail=True)
    first = run_pending_attempt(service, factory, worker_id="worker")
    assert first.error_code == "task_requirements_compilation_failed"
    events = service.read_events("thr_worker", 0).events
    route_event = next(event for event in events if event.event_type == "task_route_created")
    assert next(event for event in events if event.event_type == "task_recognition_timing").payload["details"]["phase"] == "routing"
    assert next(event for event in events if event.event_type == "task_requirements_compilation_timing").payload["outcome"] == "failed"
    retry(service)
    factory.fail = False
    assert run_pending_attempt(service, factory, worker_id="worker").status == "completed"
    assert factory.route_calls == 1
    assert factory.claims[0].task_route.request.to_document() == route_event.payload["routing"]["request"]


def test_runtime_rejects_changed_route_and_wrong_request_binding():
    from dataclasses import replace
    from test_thread_worker import _service, _submit
    from capstone_agent.task_routing import TaskRoute
    from capstone_agent.thread_service import ThreadExecutionError
    service = _service()
    _submit(service)
    claim = service.claim_attempt("worker", 30)
    route = TaskRoute(claim.task_request, "general")
    service.append_runtime_event(claim, event_type="task_route_created", payload={"routing": route.to_document()})
    with pytest.raises(ThreadExecutionError):
        service.append_runtime_event(claim, event_type="task_route_created",
            payload={"routing": TaskRoute(claim.task_request, "professional").to_document()})
    with pytest.raises(ThreadExecutionError):
        service.append_runtime_event(claim, event_type="task_route_created", payload={"routing":
            TaskRoute(replace(claim.task_request, instruction="altered request"), "general").to_document()})


def test_routing_failure_does_not_report_stale_compilation_metrics():
    from test_task_recognition import Factory
    from test_thread_worker import _service, _submit
    from capstone_agent.thread_worker import run_pending_attempt
    service = _service()
    _submit(service)
    class FailingRoute(Factory):
        def route_task(self, claim, *, on_heartbeat):
            raise ValueError("bad route output")
        def routing_metrics(self, claim):
            return {"phase": "routing", "calls": [{"duration_ms": 7}]}
        def recognition_metrics(self, claim):
            return {"phase": "stale compilation"}
    factory = FailingRoute(service)
    assert run_pending_attempt(service, factory, worker_id="worker").error_code == "task_recognition_failed"
    timing = next(e for e in service.read_events("thr_worker", 0).events if e.event_type == "task_recognition_timing")
    assert timing.payload["details"]["phase"] == "routing"
    assert not factory.requests and not factory.claims
