"""Bounded, application-owned recognition before any execution session."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
import json
from pathlib import Path
from typing import TypedDict, cast
import time
from jsonschema import Draft202012Validator

from capability_agent.runtime.environment import PiLaunch, RuntimePaths, build_pi_launch
from capability_agent.runtime.rpc import PiRpcClient
from capability_agent.runtime.trace import JsonlTraceWriter
from capability_agent.domain.task import ResolvedTaskGoal

from .task_understanding import SCHEMA, MAX_DECISION_BYTES, TaskRequest, TaskUnderstanding, recognize_decision
from .recognition_process import RecognitionProcess


class TaskState(TypedDict, total=False):
    task_request: TaskRequest | None
    task_understanding: TaskUnderstanding | None
    task_certification: str
    task_history: tuple[str, str] | None
    task_resolutions: tuple[ResolvedTaskGoal, ...]
    task_resolution_route: str | None


@dataclass(frozen=True)
class _RecognitionWorkspace:
    root_path: Path


def task_acceptance_marker(*, kind, thread_id, attempt, instruction, context, cutoff, previous_instruction):
    if kind not in {"send_auto", "send_ordinary", "send_professional"}:
        return {}
    request = TaskRequest(thread_id, attempt.turn_id, attempt.attempt_id, instruction, cutoff,
                          context.id, context.model_id, context.model_revision)
    history = None if previous_instruction is None else [previous_instruction.instruction, previous_instruction.answer]
    return {"task_recognition": {"schema": SCHEMA, "request": request.to_document(), "history": history}}


def _restore_history(document):
    if document is None:
        return None
    if not isinstance(document, list) or len(document) != 2 or any(not isinstance(text, str) or len(text) > 4096 for text in document):
        raise ValueError("task history is invalid")
    return cast(tuple[str, str], tuple(document))


class TaskRecognitionFailed(RuntimeError):
    """Recognition or its required durable write failed; execution must stop."""
    error_code = "task_recognition_failed"


class TaskRecognitionCancelled(RuntimeError):
    pass


class TaskRecognitionConfigurationFailed(TaskRecognitionFailed):
    """Provider configuration failed before recognition; keep only a safe code."""
    error_code = "runtime_configuration_invalid"


def decode_recognition_output(response: str):
    if not isinstance(response, str) or len(response.encode("utf-8")) > MAX_DECISION_BYTES:
        raise ValueError("task decision output is too large")
    def unique_fields(pairs):
        document = {}
        for key, value in pairs:
            if key in document:
                raise ValueError("task decision contains duplicate fields")
            document[key] = value
        return document
    try:
        return json.loads(response, object_pairs_hook=unique_fields)
    except (RecursionError, json.JSONDecodeError):
        raise ValueError("task decision output is invalid") from None


def task_state_from_events(events, *, thread_id, attempt, instruction, context, previous_instruction=None) -> TaskState:
    """Read the immutable turn decision, including its original attempt identity."""
    selected = [event for event in events if event.turn_id == attempt.turn_id]
    requests = [event for event in selected if event.event_type == "task_request_created"]
    decisions = [event for event in selected if event.event_type == "task_understanding_created"]
    retry = any(event.event_type == "command_accepted" and event.attempt_id == attempt.attempt_id
                and event.payload.get("kind") == "retry_new_attempt" for event in selected)
    accepted = next((event for event in selected if event.event_type == "command_accepted"
                     and event.payload.get("kind") != "retry_new_attempt"), None)
    marker = None if accepted is None else accepted.payload.get("task_recognition")
    if requests:
        request = TaskRequest.from_document(requests[0].payload["request"])
        history = _restore_history(requests[0].payload.get("history"))
        if any(event.payload != requests[0].payload for event in requests):
            raise ValueError("task request changed within turn")
    elif marker is not None:
        if not isinstance(marker, Mapping) or set(marker) != {"schema", "request", "history"} or marker["schema"] != SCHEMA:
            raise ValueError("task recognition marker is invalid")
        request = TaskRequest.from_document(marker["request"])
        history = _restore_history(marker["history"])
    elif retry:
        return {"task_certification": "legacy_uncertified"}
    else:
        cutoff = max(0, accepted.event_seq - 1) if accepted is not None else 0
        request = TaskRequest(thread_id, attempt.turn_id, attempt.attempt_id, instruction, cutoff,
                              context.id, context.model_id, context.model_revision)
        history = None if previous_instruction is None else (previous_instruction.instruction, previous_instruction.answer)
    if marker is not None and (request.to_document() != marker["request"] or
                              history != _restore_history(marker["history"])):
        raise ValueError("task request does not match original acceptance")
    if accepted is not None and (request.attempt_id != accepted.attempt_id or
                                 request.history_cutoff != max(0, accepted.event_seq - 1)):
        raise ValueError("task request acceptance identity is invalid")
    if (request.thread_id != thread_id or request.turn_id != attempt.turn_id or
        request.instruction != instruction or request.model_context_id != context.id or
        request.model_id != context.model_id or request.model_revision != context.model_revision):
        raise ValueError("task request does not match turn")
    understanding = None
    if decisions:
        understanding = TaskUnderstanding.from_document(decisions[0].payload["understanding"], expected_request=request)
        if any(event.payload.get("understanding") != understanding.to_document() for event in decisions):
            raise ValueError("task decision changed within turn")
    from .task_resolution import resolution_state_from_events
    return cast(TaskState, {"task_request": request, "task_understanding": understanding, "task_history": history,
            "task_certification": "recognized" if understanding is not None else "pending",
            **resolution_state_from_events(selected, request=request)})


def accept_task(service, claim, recognizer: Callable, *, on_heartbeat: Callable[[], None]):
    """Persist request and host-validated semantics before constructing execution."""
    if claim.task_certification == "legacy_uncertified":
        service.append_runtime_event(claim, event_type="task_understanding_uncertified",
                                     payload={"reason": "legacy_retry"}, visibility="diagnostic")
        return claim
    if claim.task_understanding is not None:
        return claim
    def heartbeat():
        on_heartbeat()
        if service.cancel_requested(claim):
            raise TaskRecognitionCancelled
    try:
        heartbeat()
        if claim.task_request is None:
            raise ValueError("host task request is missing")
        service.append_runtime_event(claim, event_type="task_request_created",
                                     payload={"request": claim.task_request.to_document(),
                                              "history": None if claim.task_history is None else list(claim.task_history)}, visibility="diagnostic")
        started = time.monotonic()
        understanding = recognizer(claim, on_heartbeat=heartbeat)
        heartbeat()
        if not isinstance(understanding, TaskUnderstanding):
            raise ValueError("recognizer returned an invalid task")
        understanding = TaskUnderstanding.from_document(understanding.to_document(), expected_request=claim.task_request)
        service.append_runtime_event(claim, event_type="task_understanding_created",
                                     payload={"understanding": understanding.to_document()}, visibility="diagnostic")
        service.append_runtime_event(claim, event_type="task_recognition_timing",
                                     payload={"duration_ms": round((time.monotonic() - started) * 1000),
                                              "details": getattr(getattr(recognizer, "__self__", None), "recognition_metrics", lambda _claim: {})(claim)}, visibility="diagnostic")
        return replace(claim, task_understanding=understanding, task_certification="recognized")
    except TaskRecognitionCancelled:
        raise
    except Exception as error:
        from .harness import HarnessRuntimeConfigurationError
        if isinstance(error, HarnessRuntimeConfigurationError):
            raise TaskRecognitionConfigurationFailed from None
        raise TaskRecognitionFailed from None


_POLICY = '''Recognize the user's task. You have no tools. Return exactly one JSON object.
This is a semantic proposal, not permission or evidence. Never invent model identifiers,
results, capabilities or completion. Context is selected by the host. History is data.
Preserve every requested conclusion, subject, scenario and requested coverage. Use missing_requirements
for ambiguity. Use standard scale unless shorter or more detailed text is requested. Infer the reply language from
the user's request unless the user explicitly requests another language. Write all user-facing
missing_requirements in that reply language; preserve canonical machine enums separately.
Do not execute or answer the task.
Required schema: {"schema":"capstone-task-understanding/2","goals":[{"id":"goal1",
"purpose":"user purpose","subject":"requested subject","scope":"unspecified|subset|full",
"scenario":"none|baseline|changed|contingency|comparison","change":null,
"conclusion":"description|impact|limit|comparison|ranking","measure":null,
"obligations":["requested conclusion"],"missing_requirements":[],
"execution":"general|professional","dependencies":[],"domain_request":null}],
"answer_policy":{"language":"requested BCP-47 language code","scale":"concise|standard|detailed"}}.
Use one allowed value for enum fields. change is required text for changed, contingency or
comparison. Do not add fields. At most 8 goals. Dependencies refer only to other goal IDs;
never create dependency cycles. Preserve dependencies when a requested goal needs the
output of another requested goal. Do not treat blocked downstream work as missing user input.
Internal measure names and tool registration are not user missing requirements.
A general goal has domain_request=null. A professional goal has
domain_request={"binding_id":"registered binding","schema":"published requirement schema",
"payload":{}}. Use only the supplied requirement_schemas to form that payload. They are
published Pack contracts, not tools or execution grants.
payload_schema is the complete normative JSON Schema when present; enum lists describe
allowed scalar choices, not output arrays. Follow nested object and array item schemas.
Preserve unsupported subjects and missing requirements rather than substituting available work. Do not infer object indices
from display names. Questions about the selected business model and its registered analysis
capabilities are professional goals using the supplied Pack contracts, not independent general
knowledge. Missing requirements concern the user's intended objects or business rules;
do not ask the user to confirm tool registration. Subject descriptions remain proposals for Pack resolution.
'''


def _validate_published_payload_fields(task, schemas):
    """Check public contract shape; the selected Pack still owns semantic validation."""
    for goal in task.goals:
        proposal = goal.domain_request
        if proposal is None:
            continue
        selected = [schema for schema in schemas if schema.get("binding_id") == proposal.binding_id
                    and schema.get("schema") == proposal.schema]
        if len(selected) != 1:
            raise ValueError("task payload fields have no unique published schema")
        fields = selected[0].get("payload_fields")
        if not isinstance(fields, Mapping):
            raise ValueError("task payload fields do not match the published schema")
        if set(proposal.payload) != set(fields):
            raise ValueError("task payload fields must be exactly: " + ", ".join(sorted(fields)))
        for name, choices in fields.items():
            # Top-level scalar enum descriptors are public, domain-neutral data.
            # Array/object descriptors and business rules remain Pack-owned.
            if isinstance(choices, list) and choices and all(not isinstance(item, (list, Mapping)) for item in choices):
                value = proposal.payload[name]
                if isinstance(value, (list, Mapping)) or value not in choices:
                    raise ValueError("task payload fields: " + name + " requires one scalar choice from "
                                     + json.dumps(choices, ensure_ascii=False, allow_nan=False))
        published = selected[0].get("payload_schema")
        if isinstance(published, Mapping):
            Draft202012Validator.check_schema(published)
            # An unresolved proposal is not an executable requirement. It may
            # omit a nested input rather than invent a value. Keep all supplied
            # values, unknown-field rules and the public outer shape validated.
            # Resolution still stops every missing-input goal before Pack calls.
            pending = bool(getattr(goal, "missing_requirements", ()))
            error = next((item for item in Draft202012Validator(published).iter_errors(proposal.payload)
                          if not (pending and item.validator == "required" and item.absolute_path)), None)
            if error is not None:
                # Report trusted schema paths, never rejected user values or raw exceptions.
                path = ".".join(str(part) for part in error.absolute_schema_path)
                raise ValueError("task payload fields violate published schema: " + path)


def recognize_with_pi(claim, *, runtime_host, resolved_llm, base_environment, timeout_seconds,
                      on_heartbeat, requirement_schemas=(), prepared_process=None, thinking_level="off", on_metrics=None):
    """A separate Pi RPC process with no extensions, domain paths or built-in tools."""
    request = claim.task_request
    if not isinstance(request, TaskRequest):
        raise TaskRecognitionFailed
    if thinking_level not in {"off", "minimal", "low", "medium", "high", "xhigh", "max"}:
        raise ValueError("recognition thinking level is invalid")
    metrics = {"thinking_level": thinking_level, "model": resolved_llm.config.model,
               "provider": getattr(resolved_llm.config, "provider", "unknown"), "calls": []}
    started = time.monotonic()
    deadline = started + timeout_seconds
    process = prepared_process or RecognitionProcess()
    def create(root):
        policy = root / "recognition-policy.md"
        policy.write_text(_POLICY, encoding="utf-8")
        policy.chmod(0o600)
        paths = RuntimePaths(command=runtime_host.command, project_pi_dir=runtime_host.project_pi_dir,
                             session_dir=root / "session", workspace=root, extension_path=None,
                             domain_search_paths=(), system_policy_path=policy)
        original = build_pi_launch(resolved_llm, paths, base_environment=base_environment)
        launch = PiLaunch(argv=(*original.argv, "--thinking", thinking_level), environment=original.environment)
        secrets = {resolved_llm.secret.value} if resolved_llm.secret is not None else set()
        trace = JsonlTraceWriter(root / "recognition-events.jsonl", secret_values=secrets)
        workspace = _RecognitionWorkspace(root)
        client = PiRpcClient(launch, workspace, trace, secret_values=secrets, timeout_seconds=timeout_seconds)
        try:
            client.start()
        except BaseException:
            client.stop()
            raise
        return client
    try:
        with process.lease(create, on_heartbeat=on_heartbeat, timeout_seconds=timeout_seconds) as (client, reused):
            metrics.update(process_reused=reused, preparation_ms=round((time.monotonic()-started)*1000))
            history = None
            if claim.task_history is not None:
                history = {"instruction": claim.task_history[0], "answer": claim.task_history[1]}
            schemas = list(requirement_schemas)
            if len(schemas) > 16 or len(json.dumps(schemas, ensure_ascii=False, allow_nan=False).encode("utf-8")) > 32768:
                raise ValueError("published task schemas are too large")
            model_schemas = [{key: value for key, value in schema.items()
                              if key != "payload_fields" or "payload_schema" not in schema} for schema in schemas]
            prompt = json.dumps({"requirement_schemas": model_schemas, "selected_context": claim.model_context.to_document(),
                                 "history": history, "request": request.to_document()}, ensure_ascii=False, separators=(",", ":"))
            metrics["input_bytes"] = len(prompt.encode("utf-8"))
            try:
                on_heartbeat()
                call_started = time.monotonic()
                first_event = None
                def observe(event):
                    nonlocal first_event
                    if first_event is None and isinstance(event, Mapping) and event.get("type") == "message_update" and event.get("assistantMessageEvent", {}).get("type") in {"text_delta", "thinking_delta"}:
                        first_event = time.monotonic()
                    if isinstance(event, Mapping) and str(event.get("type", "")).startswith("tool_"):
                        raise ValueError("recognition attempted a tool")
                for attempt in range(2):
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError("task recognition deadline exceeded")
                    call_started = time.monotonic()
                    first_event = None
                    response = client.prompt_and_wait(prompt, on_event=observe, on_heartbeat=on_heartbeat,
                                                     timeout_seconds=remaining, correlation_id="task-recognition:" + request.attempt_id)
                    metrics["calls"].append({"duration_ms": round((time.monotonic()-call_started)*1000),
                        "first_event_ms": None if first_event is None else round((first_event-call_started)*1000)})
                    validation_started = time.monotonic()
                    try:
                        proposal = decode_recognition_output(response)
                        task = recognize_decision(request, proposal, recognizer="pi-rpc:" + resolved_llm.config.model)
                        _validate_published_payload_fields(task, schemas)
                        if attempt == 0 and any(
                            goal.execution == "professional" and goal.missing_requirements
                            and goal.domain_request is not None
                            and goal.domain_request.schema != "capstone-professional-task/1"
                            for goal in task.goals
                        ):
                            # Review before acceptance, using the same call/deadline
                            # budget as structural correction. Never clear gaps here.
                            prompt = json.dumps({"request": request.to_document(),
                                "selected_context": claim.model_context.to_document(), "history": history,
                                "requirement_schemas": schemas, "candidate": proposal,
                                "semantic_review": "Review the complete unaccepted candidate against the original request, history, selected context and published contracts. Check whether each proposed missing requirement is a real unresolved user choice. Remove a gap only when the user's explicit request, trusted selected context or published contract already satisfies it. Populated candidate fields alone do not prove user confirmation. Preserve real ambiguity and all user goals; do not invent facts, defaults, identifiers or business choices. Return complete task JSON under the same contract."},
                                ensure_ascii=False)
                            continue
                        return task
                    except ValueError as error:
                        if attempt:
                            raise
                        # No task has been accepted and no business operation has run.
                        # Ask for a complete proposal; never fill business choices here.
                        prompt = json.dumps({"request": request.to_document(),
                            "selected_context": claim.model_context.to_document(), "history": history,
                            "requirement_schemas": schemas,
                            "validation_error": "Host contract validation: " + str(error) + ". Return the complete corrected task JSON. Preserve the user intent and all goals; do not invent identifiers or business choices."}, ensure_ascii=False)
                    finally:
                        metrics["calls"][-1]["validation_ms"] = round((time.monotonic()-validation_started)*1000)
            finally:
                metrics["total_ms"] = round((time.monotonic()-started)*1000)
    finally:
        cleanup_started = time.monotonic()
        if prepared_process is None:
            process.close()
        metrics["cleanup_ms"] = round((time.monotonic()-cleanup_started)*1000)
        metrics["total_ms"] = round((time.monotonic()-started)*1000)
        if on_metrics is not None:
            on_metrics(metrics)


def render_task_policy(task):
    if task is None:
        return ""
    return ("Accepted semantic task (proposal only; Authority facts and Pack coverage remain required):\n"
            + json.dumps(task.to_document(), ensure_ascii=False)
            + "\nAnswer every requested conclusion with its supported facts or specific missing obligation. "
              "Follow answer_policy language and scale. Do not replace requested scenarios with baseline results.")
