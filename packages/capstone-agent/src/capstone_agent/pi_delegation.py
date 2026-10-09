"""Bounded host-to-host contracts for the isolated general Pi executor.

These references describe external observations, never Authority evidence.
The executor host issues source and artifact identities; the application binds
them to the accepted task before it saves or presents the result.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
import asyncio
import json
import math
import re
import sys
import time
from types import MappingProxyType
from typing import Protocol, runtime_checkable
from urllib.parse import urlsplit

import httpx

from .conversation_context import ConversationContext
from .business_context import BusinessContext
from .request_intent import NodeControl

MAX_DOCUMENT_BYTES = 256 * 1024
CANCELLATION_TIMEOUT_SECONDS = 0.5
STATUSES = frozenset({"completed", "needs_clarification", "capability_unavailable", "failed", "cancelled"})
_FORBIDDEN = {"authority", "authority_refs", "result_refs", "evidence_refs", "model_revision",
              "api_key", "credentials", "password", "token", "secret", "endpoint"}
_TASK_V1_FIELDS = ('task_id', 'parent_attempt_id', 'entrypoint', 'instruction',
                   'messages', 'dependency_results', 'executor_identity', 'timeout_seconds')
_TASK_V2_FIELDS = ('business_context', 'resource_profile', 'input')


def _json_document(value: object) -> dict:
    nodes = 0

    def visit(item, depth=0):
        nonlocal nodes
        nodes += 1
        if depth > 12 or nodes > 8192:
            raise ValueError("Pi JSON exceeds structural bounds")
        if isinstance(item, Mapping):
            if any(not isinstance(k, str) or len(k) > 256 for k in item):
                raise ValueError("Pi JSON keys are invalid")
            if set(item) & _FORBIDDEN:
                raise ValueError("Pi JSON contains protected fields")
            return {k: visit(v, depth + 1) for k, v in item.items()}
        if isinstance(item, (list, tuple)):
            return [visit(v, depth + 1) for v in item]
        if item is None or type(item) in {bool, int}:
            return item
        if type(item) is float and math.isfinite(item):
            return item
        if isinstance(item, str) and len(item.encode("utf-8")) <= 65536:
            return item
        raise ValueError("Pi values must be bounded finite JSON")

    document = visit(value)
    if not isinstance(document, dict):
        raise ValueError("Pi document must be an object")
    if len(json.dumps(document, ensure_ascii=False, allow_nan=False).encode()) > MAX_DOCUMENT_BYTES:
        raise ValueError("Pi JSON exceeds byte bounds")
    return document


def _freeze(value):
    if isinstance(value, dict):
        return MappingProxyType({k: _freeze(v) for k, v in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(v) for v in value)
    return value


def _identity(value):
    if not isinstance(value, dict) or not value:
        raise ValueError("executor identity must be a nonempty JSON object")


def _id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", value):
        raise ValueError("Pi host identity is invalid")


def _fields(document, fields, schema):
    if set(document) != set(fields) | {"schema"} or document["schema"] != schema:
        raise ValueError("Pi document fields or schema are invalid")


def _task_v2_values(business_context, resource_profile, task_input, instruction):
    """Validate the public context separately from generic untrusted JSON."""
    context = (business_context if isinstance(business_context, BusinessContext)
               else BusinessContext.from_document(business_context))
    profile = _json_document(resource_profile)
    if set(profile) != {'profile_id', 'revision'}:
        raise ValueError('Pi resource profile fields are invalid')
    for value in profile.values():
        if not isinstance(value, str) or not value.strip() or len(value.encode('utf-8')) > 256:
            raise ValueError('Pi resource profile identity is invalid')
    task_input = _json_document(task_input)
    kind = task_input.get('kind')
    if kind == 'text':
        expected = {'kind', 'text'}
    elif kind == 'skill_invocation':
        expected = {'kind', 'text', 'skill_id', 'skill_version'}
        _id(task_input.get('skill_id'))
        version = task_input.get('skill_version')
        if not isinstance(version, str) or not version.strip() or len(version.encode('utf-8')) > 256:
            raise ValueError('Pi skill version is invalid')
    else:
        raise ValueError('Pi typed input kind is invalid')
    if set(task_input) != expected or task_input['text'] != instruction:
        raise ValueError('Pi typed input fields or instruction are invalid')
    return context, _freeze(profile), _freeze(task_input)


@dataclass(frozen=True, slots=True)
class PiTaskRequest:
    task_id: str
    parent_attempt_id: str
    entrypoint: str
    instruction: str
    messages: tuple
    dependency_results: tuple
    executor_identity: Mapping
    timeout_seconds: float
    business_context: BusinessContext | Mapping | None = field(default=None, kw_only=True)
    resource_profile: Mapping | None = field(default=None, kw_only=True)
    input: Mapping | None = field(default=None, kw_only=True)

    def __post_init__(self):
        document = _json_document({name: getattr(self, name) for name in _TASK_V1_FIELDS})
        _id(self.task_id)
        _id(self.parent_attempt_id)
        if not isinstance(self.entrypoint, str) or self.entrypoint not in {"delegated", "direct"}:
            raise ValueError("Pi entrypoint is invalid")
        if not isinstance(self.instruction, str) or not self.instruction.strip():
            raise ValueError("Pi instruction is required")
        _identity(document["executor_identity"])
        if (type(self.timeout_seconds) not in {int, float} or not math.isfinite(self.timeout_seconds)
                or not 0 < self.timeout_seconds <= 3600):
            raise ValueError("Pi timeout is invalid")
        if not isinstance(document["messages"], list) or not isinstance(document["dependency_results"], list):
            raise ValueError("Pi context must contain lists")
        ConversationContext(messages=tuple(document["messages"]))
        seen = set()
        for message in document["messages"]:
            _id(message["message_id"])
            if message["message_id"] in seen:
                raise ValueError("duplicate Pi message identity")
            seen.add(message["message_id"])
        if len(document["dependency_results"]) > 16:
            raise ValueError("too many Pi dependency results")
        seen = {self.task_id}
        for dependency in document["dependency_results"]:
            if not isinstance(dependency, dict):
                raise ValueError("invalid Pi dependency")
            _id(dependency.get("task_id"))
            if dependency["task_id"] in seen:
                raise ValueError("invalid or duplicate Pi dependency")
            _validate_result(dependency, dependency.get("task_id"), self.parent_attempt_id,
                             dependency.get("executor_identity"))
            seen.add(dependency["task_id"])
        for field in ("messages", "dependency_results", "executor_identity"):
            object.__setattr__(self, field, _freeze(document[field]))
        extras = [getattr(self, name) is not None for name in _TASK_V2_FIELDS]
        if any(extras):
            if not all(extras):
                raise ValueError('Pi v2 requires context, resource profile and typed input')
            context, profile, task_input = _task_v2_values(
                self.business_context, self.resource_profile, self.input, self.instruction)
            object.__setattr__(self, 'business_context', context)
            object.__setattr__(self, 'resource_profile', profile)
            object.__setattr__(self, 'input', task_input)
        # Include the schema and every v2 field in the total transport budget.
        self.to_document()

    @classmethod
    def from_document(cls, document):
        if not isinstance(document, Mapping):
            raise ValueError('Pi document must be an object')
        schema = document.get('schema')
        if schema == 'capstone-pi-task/1':
            document = _json_document(document)
            _fields(document, _TASK_V1_FIELDS, schema)
        elif schema == 'capstone-pi-task/2':
            _fields(document, _TASK_V1_FIELDS + _TASK_V2_FIELDS, schema)
            base = _json_document({key: document[key] for key in _TASK_V1_FIELDS})
            document = {'schema': schema, **base, **{key: document[key] for key in _TASK_V2_FIELDS}}
            if any(document[key] is None for key in _TASK_V2_FIELDS):
                raise ValueError('Pi v2 fields cannot be null')
        else:
            raise ValueError('Pi task schema is invalid')
        return cls(**{k: v for k, v in document.items() if k != "schema"})

    def to_document(self):
        document = {'schema': 'capstone-pi-task/1', **_json_document(
            {name: getattr(self, name) for name in _TASK_V1_FIELDS})}
        if self.business_context is not None:
            document.update(schema='capstone-pi-task/2', business_context=self.business_context.to_document(),
                            resource_profile=_json_document(self.resource_profile), input=_json_document(self.input))
        if len(json.dumps(document, ensure_ascii=False, allow_nan=False).encode('utf-8')) > MAX_DOCUMENT_BYTES:
            raise ValueError('Pi JSON exceeds byte bounds')
        return document


def _validate_result(document, task_id, parent_attempt_id, executor_identity):
    _fields(document, PiTaskResult.__dataclass_fields__, "capstone-pi-task-result/1")
    _id(document["task_id"])
    _id(document["parent_attempt_id"])
    _identity(document["executor_identity"])
    if (document["task_id"] != task_id or document["parent_attempt_id"] != parent_attempt_id
            or document["executor_identity"] != executor_identity):
        raise ValueError("Pi result does not match host task identity")
    if (not isinstance(document["status"], str) or document["status"] not in STATUSES
            or not isinstance(document["answer"], str)):
        raise ValueError("Pi result status or answer is invalid")
    if not isinstance(document["usage"], dict):
        raise ValueError("Pi usage must be an object")
    for collection, identity_key in (("sources", "source_id"), ("artifacts", "artifact_id")):
        items = document[collection]
        if not isinstance(items, list) or len(items) > 64:
            raise ValueError("Pi references exceed bounds")
        seen = set()
        for item in items:
            if not isinstance(item, dict) or set(item) != {identity_key, "task_id", "parent_attempt_id", "kind", "metadata"}:
                raise ValueError("Pi reference fields are invalid")
            _id(item[identity_key])
            if item[identity_key] in seen:
                raise ValueError("duplicate Pi reference identity")
            seen.add(item[identity_key])
            if item["task_id"] != task_id or item["parent_attempt_id"] != parent_attempt_id:
                raise ValueError("Pi reference does not match host task identity")
            if not isinstance(item["kind"], str) or not item["kind"] or len(item["kind"]) > 64 or not isinstance(item["metadata"], dict):
                raise ValueError("Pi reference metadata is invalid")


@dataclass(frozen=True, slots=True)
class PiTaskResult:
    task_id: str
    parent_attempt_id: str
    executor_identity: Mapping
    status: str
    answer: str
    sources: tuple
    artifacts: tuple
    usage: Mapping

    def __post_init__(self):
        document = {"schema": "capstone-pi-task-result/1", **_json_document(
            {field: getattr(self, field) for field in self.__dataclass_fields__})}
        _validate_result(document, self.task_id, self.parent_attempt_id, document["executor_identity"])
        for field in ("sources", "artifacts", "usage", "executor_identity"):
            object.__setattr__(self, field, _freeze(document[field]))

    @classmethod
    def from_document(cls, document, request: PiTaskRequest):
        document = _json_document(document)
        _validate_result(document, request.task_id, request.parent_attempt_id,
                         request.to_document()["executor_identity"])
        return cls(**{k: v for k, v in document.items() if k != "schema"})

    def to_document(self):
        return {"schema": "capstone-pi-task-result/1", **_json_document(
            {field: getattr(self, field) for field in self.__dataclass_fields__})}


@runtime_checkable
class GeneralPiExecutor(Protocol):
    @property
    def capability(self) -> Mapping: ...

    @property
    def identity(self) -> Mapping: ...

    def execute(self, request: PiTaskRequest, control: NodeControl,
                on_event: Callable[[dict], None]) -> PiTaskResult: ...

    def cancel(self, task_id: str) -> None: ...


class HttpGeneralPiExecutor:
    """Host-selected private transport. Requests cannot select an origin."""

    def __init__(self, origin: str, *, identity: Mapping, capability: Mapping,
                 poll_interval_seconds: float = 0.05, control_token: str | None = None):
        parsed = urlsplit(origin)
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username
                or parsed.password or parsed.path not in {"", "/"} or parsed.query or parsed.fragment):
            raise ValueError("Pi host origin is invalid")
        identity = _json_document(identity)
        _identity(identity)
        if type(poll_interval_seconds) not in {int, float} or not 0 < poll_interval_seconds <= 1:
            raise ValueError("Pi polling interval is invalid")
        self._origin = origin.rstrip("/")
        self._identity = _freeze(identity)
        self._capability = _freeze(_json_document(capability))
        self._poll_interval = poll_interval_seconds
        self._headers = {"Authorization": "Bearer " + control_token} if control_token else {}

    @property
    def identity(self):
        return self._identity

    @property
    def capability(self):
        return self._capability

    def _call(self, method, path, *, document=None, timeout=0.25,
              total_timeout=0.25, checkpoint=lambda: None):
        """Bound the entire exchange, including response headers and slow reads.

        Application workers call this synchronous API from their worker threads.
        The private async loop lets the total timer interrupt network awaits.
        """
        checkpoint()

        async def fetch():
            async with httpx.AsyncClient(trust_env=False, follow_redirects=False, headers=self._headers) as client:
                async with client.stream(method, self._origin + path, json=document, timeout=timeout) as response:
                    response.raise_for_status()
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        checkpoint()
                        body.extend(chunk)
                        if len(body) > MAX_DOCUMENT_BYTES:
                            raise ValueError("Pi response exceeds byte bounds")
            checkpoint()
            result = _json_document(json.loads(body))
            checkpoint()
            return result

        async def checked_fetch():
            pending = asyncio.create_task(fetch())
            try:
                while not pending.done():
                    await asyncio.wait({pending}, timeout=0.025)
                    checkpoint()
                return pending.result()
            finally:
                if not pending.done():
                    pending.cancel()
                await asyncio.gather(pending, return_exceptions=True)

        async def bounded_fetch():
            return await asyncio.wait_for(checked_fetch(), timeout=total_timeout)

        try:
            from .bounded_http_loop import run_http
            return run_http(bounded_fetch())
        except TimeoutError:
            checkpoint()
            raise TimeoutError("Pi transport deadline expired; task state is unknown") from None
        except (httpx.HTTPError, json.JSONDecodeError, UnicodeDecodeError):
            checkpoint()
            raise RuntimeError("Pi executor transport failed; task state may be unknown") from None

    def cancel(self, task_id):
        """Request cancellation and confirm a bound terminal state within cleanup budget."""
        _id(task_id)
        control = NodeControl(lambda: None, time.monotonic() + CANCELLATION_TIMEOUT_SECONDS)

        def call(method):
            control.checkpoint()
            return self._call(method, "/tasks/" + task_id,
                              timeout=max(0.001, min(0.1, control.deadline - time.monotonic())),
                              total_timeout=max(0.001, control.deadline - time.monotonic()),
                              checkpoint=control.checkpoint)

        receipt = call("DELETE")
        if receipt != {"task_id": task_id, "status": "cancellation_requested"}:
            raise ValueError("Pi cancellation receipt is invalid; task state is unknown")
        while True:
            response = call("GET")
            if (set(response) != {"status", "events", "result"}
                    or not isinstance(response["status"], str)
                    or not isinstance(response["events"], list) or len(response["events"]) > 128):
                raise ValueError("Pi cancellation status is invalid; task state is unknown")
            status = response["status"]
            if status in STATUSES:
                document = _json_document(response["result"])
                _validate_result(document, task_id, document.get("parent_attempt_id"),
                                 _json_document(self.identity))
                if document["status"] != status:
                    raise ValueError("Pi cancellation terminal status is invalid")
                control.checkpoint()
                return
            if status not in {"queued", "running"} or response["result"] is not None:
                raise ValueError("Pi cancellation status is invalid; task state is unknown")
            time.sleep(min(self._poll_interval, max(0, control.deadline - time.monotonic())))

    def execute(self, request, control, on_event):
        if request.executor_identity != self.identity:
            raise ValueError("Pi request executor identity is not selected")
        deadline = min(control.deadline, time.monotonic() + request.timeout_seconds)

        def checkpoint():
            control.checkpoint()
            if time.monotonic() >= deadline:
                raise TimeoutError("Pi task deadline expired")

        checkpoint()
        complete = False
        seen_events = {}
        try:
            accepted = self._call("POST", "/tasks", document=request.to_document(),
                                  timeout=max(0.001, min(0.25, deadline - time.monotonic())),
                                  total_timeout=max(0.001, deadline - time.monotonic()), checkpoint=checkpoint)
            if accepted != {"task_id": request.task_id}:
                raise ValueError("Pi accepted task identity is invalid")
            while True:
                checkpoint()
                response = self._call("GET", "/tasks/" + request.task_id,
                                      timeout=max(0.001, min(0.25, deadline - time.monotonic())),
                                      total_timeout=max(0.001, deadline - time.monotonic()), checkpoint=checkpoint)
                checkpoint()
                if set(response) != {"status", "events", "result"} or not isinstance(response["events"], list):
                    raise ValueError("Pi task status fields are invalid")
                if len(response["events"]) > 128:
                    raise ValueError("Pi events exceed bounds")
                for event in response["events"]:
                    if not isinstance(event, dict) or "event_id" not in event:
                        raise ValueError("Pi event identity is required")
                    _id(event["event_id"])
                    event_id = event["event_id"]
                    if event_id in seen_events and seen_events[event_id] != event:
                        raise ValueError("Pi event identity changed")
                    if event_id not in seen_events:
                        if len(seen_events) >= 128:
                            raise ValueError("Pi event history exceeds bounds")
                        seen_events[event_id] = event
                        on_event(_json_document(event))
                        checkpoint()
                status = response["status"]
                if not isinstance(status, str):
                    raise ValueError("Pi task status is invalid")
                if status in STATUSES:
                    result = PiTaskResult.from_document(response["result"], request)
                    if result.status != status:
                        raise ValueError("Pi terminal status does not match result")
                    checkpoint()
                    complete = True
                    return result
                if status not in {"queued", "running"} or response["result"] is not None:
                    raise ValueError("Pi task status is invalid")
                time.sleep(min(self._poll_interval, max(0, deadline - time.monotonic())))
        finally:
            if not complete:
                original = sys.exception()
                try:
                    self.cancel(request.task_id)
                except Exception:
                    if original is None:
                        raise
                    original.add_note("Pi cancellation was not confirmed; remote task state is unknown")
