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
from typing import Protocol, cast, runtime_checkable
from urllib.parse import urlsplit

import httpx

from .conversation_context import ConversationContext
from .business_context import BusinessContext
from .request_intent import NodeControl

MAX_DOCUMENT_BYTES = 256 * 1024
from .native_document_types import MAX_NATIVE_TASK_BYTES
MAX_TASK_DOCUMENT_BYTES = MAX_NATIVE_TASK_BYTES
CANCELLATION_TIMEOUT_SECONDS = 0.5
TASK_EXCHANGE_TIMEOUT_SECONDS = 5.0


class PiTransportTimeout(TimeoutError):
    """A communication interruption; it says nothing about task completion."""
    transport_phase: str = ''
    operation: str = 'unknown'

    @property
    def diagnostic(self):
        return {'operation': self.operation, 'transport_phase': self.transport_phase}


class PiTransportUnavailable(RuntimeError):
    """A transient connection failure, distinct from invalid task contracts."""
    transport_phase: str = ''


class PiHTTPFailure(RuntimeError):
    """Non-retryable host rejection with allowlisted public diagnostics only."""
    def __init__(self, status, code):
        self.diagnostic = {'operation': 'unknown', 'http_status': status, 'protocol_code': code}
        super().__init__('Pi executor transport failed; task state may be unknown')

    def __str__(self):
        value = self.diagnostic
        return ('Pi executor HTTP request rejected: operation=' + value['operation']
                + ', status=' + str(value['http_status']) + ', code=' + value['protocol_code'])


class PiArtifactTransportUnavailable(OSError):
    """Retry the same receipt-selected file; never restart its completed task."""
STATUSES = frozenset({"completed", "needs_clarification", "capability_unavailable", "failed", "cancelled"})
_FORBIDDEN = {"authority", "authority_refs", "result_refs", "evidence_refs", "model_revision",
              "api_key", "credentials", "password", "token", "secret", "endpoint"}
_TASK_V1_FIELDS = ('task_id', 'parent_attempt_id', 'entrypoint', 'instruction',
                   'messages', 'dependency_results', 'executor_identity', 'timeout_seconds')
_TASK_V2_FIELDS = ('business_context', 'resource_profile', 'input')

from .application_capacity import limits, current_capacity


def _json_document(value: object, *, native_events: bool = False) -> dict:
    nodes = 0

    def visit(item, depth=0, path=(), presentation=False):
        nonlocal nodes
        nodes += 1
        if depth > limits.json_depth or nodes > limits.json_nodes:
            raise ValueError("Pi JSON exceeds structural bounds")
        if isinstance(item, Mapping):
            if any(not isinstance(k, str) or len(k) > 256 for k in item):
                raise ValueError("Pi JSON keys are invalid")
            protected = set(item) & _FORBIDDEN
            if protected and not (presentation and protected == {'model_revision'}):
                raise ValueError("Pi JSON contains protected fields")
            # Only the fixed presentation descriptor on a native gateway end
            # event may carry a source model revision. This is not an Authority
            # binding, result or evidence grant. Keep generic task JSON closed.
            event_position = native_events and (not path or len(path) == 2 and path[0] == 'events' and type(path[1]) is int)
            gateway_end = (item.get('type') == 'tool_execution_end' or
                item.get('type') == 'enterprise_graph_child_tool' and item.get('activity') == 'end')
            electrical_view = (event_position and gateway_end
                and item.get('tool_name') == 'data_gateway_open_network_model_view'
                and isinstance(item.get('tool_call_id'), str) and bool(item['tool_call_id'])
                and item.get('is_error') is not True)
            result = {}
            for key, child in item.items():
                if electrical_view and key == 'source_view':
                    from .grid_electrical_view import checked_electrical_descriptor
                    child = checked_electrical_descriptor(child)
                    result[key] = visit(child, depth + 1, path + (key,), presentation=True)
                else:
                    result[key] = visit(child, depth + 1, path + (key,))
            return result
        if isinstance(item, (list, tuple)):
            return [visit(v, depth + 1, path + (index,)) for index, v in enumerate(item)]
        if item is None or type(item) in {bool, int}:
            return item
        if type(item) is float and math.isfinite(item):
            return item
        if isinstance(item, str) and len(item.encode("utf-8")) <= limits.native_task_bytes:
            return item
        raise ValueError("Pi values must be bounded finite JSON")

    document = visit(value)
    if not isinstance(document, dict):
        raise ValueError("Pi document must be an object")
    if len(json.dumps(document, ensure_ascii=False, allow_nan=False).encode()) > limits.control_document_bytes:
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
    native_context: Mapping | None = field(default=None, kw_only=True)
    research_binding: Mapping | None = field(default=None, kw_only=True)

    def __post_init__(self):
        document = _json_document({name: getattr(self, name) for name in _TASK_V1_FIELDS})
        _id(self.task_id)
        _id(self.parent_attempt_id)
        if not isinstance(self.entrypoint, str) or self.entrypoint not in {"delegated", "direct"}:
            raise ValueError("Pi entrypoint is invalid")
        if not isinstance(self.instruction, str) or not self.instruction.strip():
            raise ValueError("Pi instruction is required")
        from .application_capacity import require_capacity
        require_capacity('input_text_chars', len(self.instruction), 'native_admission')
        _identity(document["executor_identity"])
        if (type(self.timeout_seconds) not in {int, float} or not math.isfinite(self.timeout_seconds)
                or self.timeout_seconds <= 0):
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
        if len(document["dependency_results"]) > limits.context_references:
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
        if self.native_context is not None:
            from .native_task_context import checked_native_context
            if self.business_context is None:
                raise ValueError('native context requires typed Pi input')
            object.__setattr__(self, 'native_context', _freeze(checked_native_context(self.native_context)))
        if self.research_binding is not None:
            from .native_research_bridge import checked_binding
            if self.business_context is None:
                raise ValueError('research channel requires typed Pi input')
            binding = checked_binding(json.loads(json.dumps(_json_document(self.research_binding))))
            if binding['attempt_id'] != self.parent_attempt_id:
                raise ValueError('research producer identity changed')
            object.__setattr__(self, 'research_binding', _freeze(binding))
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
            optional = tuple(key for key in ('native_context', 'research_binding') if key in document)
            _fields(document, _TASK_V1_FIELDS + _TASK_V2_FIELDS + optional, schema)
            base = _json_document({key: document[key] for key in _TASK_V1_FIELDS})
            document = {'schema': schema, **base, **{key: document[key] for key in _TASK_V2_FIELDS + optional}}
            if any(document[key] is None for key in _TASK_V2_FIELDS):
                raise ValueError('Pi v2 fields cannot be null')
        else:
            raise ValueError('Pi task schema is invalid')
        return cls(**{k: v for k, v in document.items() if k != "schema"})

    def to_document(self):
        document = {'schema': 'capstone-pi-task/1', **_json_document(
            {name: getattr(self, name) for name in _TASK_V1_FIELDS})}
        if self.business_context is not None:
            document.update(schema='capstone-pi-task/2', business_context=cast(BusinessContext, self.business_context).to_document(),
                            resource_profile=_json_document(self.resource_profile), input=_json_document(self.input))
        if self.native_context is not None:
            from .native_task_context import checked_native_context
            document['native_context'] = checked_native_context(self.native_context)
        if self.research_binding is not None:
            document['research_binding'] = _json_document(self.research_binding)
        byte_limit = limits.native_task_bytes if self.native_context is not None else limits.control_document_bytes
        if len(json.dumps(document, ensure_ascii=False, allow_nan=False).encode('utf-8')) > byte_limit:
            raise ValueError('Pi JSON exceeds byte bounds')
        return document


def _validate_result(document, task_id, parent_attempt_id, executor_identity):
    fields = set(PiTaskResult.__dataclass_fields__) - {'failure'}
    if 'failure' in document:
        fields.add('failure')
        failure = document['failure']
        if (document.get('status') != 'failed' or not isinstance(failure, dict)
                or set(failure) - {'capacity'} != {'code', 'phase'}
                or failure['phase'] not in {'execution', 'persistence'}):
            raise ValueError('Pi failure fields are invalid')
        _id(failure['code'])
        if 'capacity' in failure:
            capacity = failure['capacity']
            debug_fields={'mode','fatal','effective','source','location'} if isinstance(capacity,dict) and capacity.get('mode')=='debug' else set()
            if (not isinstance(capacity, dict) or set(capacity)-debug_fields != {
                    'code', 'dimension', 'actual', 'limit', 'unit', 'phase', 'retryable'}
                    or capacity['code'] != 'capacity_exceeded' or capacity['retryable'] is not False
                    or not isinstance(capacity['dimension'], str)
                    or capacity['dimension'] not in current_capacity().values
                    or type(capacity['actual']) is not int or type(capacity['limit']) is not int
                    or not 0 <= capacity['limit'] < capacity['actual']
                    or capacity['unit'] not in {'bytes', 'seconds', 'items', 'chars', 'tokens'}
                    or capacity['phase'] is not None and (not isinstance(capacity['phase'], str)
                        or len(capacity['phase']) > 128)):
                raise ValueError('Pi capacity failure fields are invalid')
            if debug_fields and (capacity.get('fatal') is not True or capacity.get('effective')!=capacity['limit']
                    or capacity.get('source')!='application_capacity' or capacity.get('location')!=capacity['phase']):
                raise ValueError('Pi debug capacity failure fields are invalid')
    _fields(document, fields, "capstone-pi-task-result/2" if 'failure' in document else "capstone-pi-task-result/1")
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
        if not isinstance(items, list) or len(items) > (limits.artifact_count if collection == 'artifacts' else limits.context_references):
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
    failure: Mapping | None = None

    def __post_init__(self):
        document = self.to_document()
        _validate_result(document, self.task_id, self.parent_attempt_id, document["executor_identity"])
        for field in ("sources", "artifacts", "usage", "executor_identity"):
            object.__setattr__(self, field, _freeze(document[field]))
        if self.failure is not None:
            object.__setattr__(self, 'failure', _freeze(document['failure']))

    @classmethod
    def from_document(cls, document, request: PiTaskRequest):
        document = _json_document(document)
        _validate_result(document, request.task_id, request.parent_attempt_id,
                         request.to_document()["executor_identity"])
        return cls(**{k: v for k, v in document.items() if k != "schema"})

    def to_document(self):
        return {"schema": "capstone-pi-task-result/2" if self.failure is not None else "capstone-pi-task-result/1", **_json_document(
            {field: getattr(self, field) for field in self.__dataclass_fields__
             if field != 'failure' or self.failure is not None})}


@runtime_checkable
class GeneralPiExecutor(Protocol):
    @property
    def capability(self) -> Mapping: ...

    @property
    def identity(self) -> Mapping: ...

    def execute(self, request: PiTaskRequest, control: NodeControl,
                on_event: Callable[[dict], None]) -> PiTaskResult: ...

    def cancel(self, task_id: str) -> PiTaskResult | None: ...


class HttpGeneralPiExecutor:
    """Host-selected private transport. Requests cannot select an origin."""

    def __init__(self, origin: str, *, identity: Mapping, capability: Mapping,
                 poll_interval_seconds: float = 0.05, control_token: str | None = None,
                 exchange_timeout_seconds: float | None = None,
                 cancellation_timeout_seconds: float | None = None):
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
        self._exchange_timeout = limits.native_exchange_seconds if exchange_timeout_seconds is None else exchange_timeout_seconds
        self._cancel_timeout = limits.native_cancel_seconds if cancellation_timeout_seconds is None else cancellation_timeout_seconds
        if any(type(value) not in {int, float} or not math.isfinite(value) or value <= 0
               for value in (self._exchange_timeout, self._cancel_timeout)):
            raise ValueError('Pi transport timeouts are invalid')
        self._headers = {"Authorization": "Bearer " + control_token} if control_token else {}

    @property
    def identity(self):
        return self._identity

    @property
    def capability(self):
        return self._capability

    def network_policy(self):
        return self._call('GET', '/network-policy', timeout=2, total_timeout=3)

    def grid_source_catalog(self):
        return self._call('GET', '/grid-sources', timeout=2, total_timeout=3)

    def grid_source_scopes(self):
        from .grid_source_topology import EXCHANGE_SECONDS
        return self._call('GET', '/grid-sources/data-gateway/scopes',
                          timeout=EXCHANGE_SECONDS + 2, total_timeout=EXCHANGE_SECONDS + 3)

    def grid_source_resolve_scope(self, document):
        from .grid_source_topology import EXCHANGE_SECONDS
        return self._call('POST', '/grid-sources/data-gateway/resolve-scope', document=document,
                          timeout=EXCHANGE_SECONDS + 2, total_timeout=EXCHANGE_SECONDS + 3)

    def grid_source_topology(self, document):
        from .grid_source_topology import EXCHANGE_SECONDS, checked_topology_request
        return self._call('POST', '/grid-sources/data-gateway/topology',
                          document=checked_topology_request(document),
                          timeout=EXCHANGE_SECONDS + 2, total_timeout=EXCHANGE_SECONDS + 3)

    def grid_electrical_models(self):
        from .grid_source_topology import EXCHANGE_SECONDS
        return self._call('GET', '/grid-sources/data-gateway/electrical/models',
                          timeout=EXCHANGE_SECONDS + 2, total_timeout=EXCHANGE_SECONDS + 3, electrical_transport=True)

    def _grid_electrical(self, operation, document):
        from .grid_electrical_view import checked_electrical_request
        from .grid_source_topology import EXCHANGE_SECONDS
        return self._call('POST', '/grid-sources/data-gateway/electrical/' + operation,
                          document=checked_electrical_request(operation, document),
                          timeout=EXCHANGE_SECONDS + 2, total_timeout=EXCHANGE_SECONDS + 3, electrical_transport=True)

    def grid_electrical_open(self, document):
        return self._grid_electrical('open', document)

    def grid_electrical_read(self, document):
        return self._grid_electrical('read', document)

    def grid_electrical_job(self, document):
        return self._grid_electrical('job', document)

    def set_network_policy(self, enabled: bool):
        if type(enabled) is not bool:
            raise ValueError('external_access must be a boolean')
        return self._call('POST', '/network-policy', document={'external_access': enabled},
                          timeout=12, total_timeout=13)

    def _call(self, method, path, *, document=None, timeout=None,
              total_timeout=None, checkpoint=lambda: None, research_transport=False,
              capacity_dimension=None, capacity_phase='native_http', electrical_transport=False):
        """Bound the entire exchange, including response headers and slow reads.

        Application workers call this synchronous API from their worker threads.
        The private async loop lets the total timer interrupt network awaits.
        """
        from .application_capacity import limits, observe_capacity
        if timeout is None:
            timeout=limits.native_http_wait_ms/1000
            capacity_dimension=capacity_dimension or 'native_http_wait_ms'
        if total_timeout is None:
            total_timeout=limits.native_http_wait_ms/1000
        started=time.monotonic()
        checkpoint()

        async def fetch():
            async with httpx.AsyncClient(trust_env=False, follow_redirects=False, headers=self._headers) as client:
                async with client.stream(method, self._origin + path, json=document, timeout=timeout) as response:
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        checkpoint()
                        body.extend(chunk)
                        from .grid_source_topology import PAGE_BYTES
                        if len(body) > (PAGE_BYTES if electrical_transport else limits.research_response_bytes if research_transport else limits.control_document_bytes):
                            raise ValueError("Pi response exceeds byte bounds")
                    if response.is_error:
                        try:
                            error = json.loads(body).get('error')
                        except (ValueError, AttributeError):
                            error = None
                        if error=='capacity_exceeded':
                            detail=json.loads(body).get('capacity')
                            from .application_capacity import current_capacity,CapacityExceeded
                            if (isinstance(detail,dict) and detail.get('mode')=='debug'
                                    and isinstance(detail.get('dimension'),str)
                                    and detail.get('dimension') in current_capacity().values
                                    and type(detail.get('actual')) is int and type(detail.get('limit')) is int
                                    and 0<=detail['limit']<detail['actual']
                                    and isinstance(detail.get('phase'),str)
                                    and re.fullmatch(r'[A-Za-z0-9_.:-]{1,128}',detail['phase'])):
                                raise CapacityExceeded(detail['dimension'],detail['actual'],detail['limit'],detail['phase'],mode='debug')
                        known = {'invalid_task', 'task_not_found', 'research_owner_conflict',
                                 'unauthorized', 'executor_capacity', 'resource_not_found',
                                 'research_transport_file_changed', 'grid_source_unavailable',
                                 'grid_source_request_invalid', 'grid_source_view_changed',
                                 'grid_source_response_invalid', 'grid_source_observation_unavailable'}
                        from .grid_electrical_view import ERRORS as electrical_errors
                        known.update(electrical_errors)
                        raise PiHTTPFailure(response.status_code, error if isinstance(error, str) and error in known else 'unrecognized_response')
                    response.raise_for_status()
            checkpoint()
            result = json.loads(body)
            if research_transport or electrical_transport:
                if not isinstance(result, dict):
                    raise ValueError('research transport response must be an object')
            else:
                task_status = method == 'GET' and re.fullmatch(r'/tasks/[^/?]+(?:\?after=[0-9]+)?', path) is not None
                result = _json_document(result, native_events=task_status)
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
        except (TimeoutError, httpx.TimeoutException) as error:
            if capacity_dimension is not None:
                elapsed=time.monotonic()-started
                observe_capacity(capacity_dimension,math.ceil(elapsed*(1000 if capacity_dimension.endswith('_ms') else 1)),
                                 phase=capacity_phase)
            checkpoint()
            failure = PiTransportTimeout("Pi transport deadline expired; task state is unknown")
            failure.transport_phase = type(error).__name__
            raise failure from None
        except httpx.TransportError as error:
            checkpoint()
            failure = PiTransportUnavailable("Pi executor transport failed; task state may be unknown")
            failure.transport_phase = type(error).__name__
            raise failure from None
        except (httpx.HTTPError, json.JSONDecodeError, UnicodeDecodeError):
            checkpoint()
            raise RuntimeError("Pi executor transport failed; task state may be unknown") from None

    def cancel(self, task_id):
        """Request cancellation and confirm a bound terminal state within cleanup budget."""
        _id(task_id)
        control = NodeControl(lambda: None, time.monotonic() + self._cancel_timeout)

        def call(method):
            control.checkpoint()
            return self._call(method, "/tasks/" + task_id,
                              timeout=max(0.001, min(limits.native_cancel_wait_ms/1000, control.deadline - time.monotonic())),
                              total_timeout=max(0.001, control.deadline - time.monotonic()),
                              capacity_dimension='native_cancel_wait_ms',capacity_phase='native_cancel',
                              checkpoint=control.checkpoint)

        receipt = call("DELETE")
        if receipt != {"task_id": task_id, "status": "cancellation_requested"}:
            raise ValueError("Pi cancellation receipt is invalid; task state is unknown")
        while True:
            response = call("GET")
            if (set(response) != {"status", "events", "result"}
                    or not isinstance(response["status"], str)
                    or not isinstance(response["events"], list) or len(response["events"]) > limits.event_buffer_count):
                raise ValueError("Pi cancellation status is invalid; task state is unknown")
            status = response["status"]
            if status in STATUSES:
                document = _json_document(response["result"])
                _validate_result(document, task_id, document.get("parent_attempt_id"),
                                 _json_document(self.identity))
                if document["status"] != status:
                    raise ValueError("Pi cancellation terminal status is invalid")
                control.checkpoint()
                return PiTaskResult(**{key: value for key, value in document.items() if key != 'schema'})
            if status not in {"queued", "running"} or response["result"] is not None:
                raise ValueError("Pi cancellation status is invalid; task state is unknown")
            time.sleep(min(self._poll_interval, max(0, control.deadline - time.monotonic())))

    def read_artifact(self, task_id: str, artifact_id: str, *, expected_sha256: str, expected_size: int) -> bytes:
        """Fetch a receipt-selected file from the fixed protected executor."""
        from hashlib import sha256
        _id(task_id)
        _id(artifact_id)
        if (not isinstance(expected_sha256, str) or not re.fullmatch(r'[a-f0-9]{64}', expected_sha256)
                or type(expected_size) is not int or not 0 <= expected_size <= limits.artifact_file_bytes):
            raise ValueError('Pi artifact content identity is invalid')
        async def fetch():
            async with httpx.AsyncClient(trust_env=False, follow_redirects=False, headers=self._headers) as client:
                async with client.stream('GET', self._origin + '/tasks/' + task_id + '/artifacts/' + artifact_id,
                                         timeout=limits.artifact_transfer_seconds) as response:
                    response.raise_for_status()
                    data = bytearray()
                    async for chunk in response.aiter_bytes():
                        data.extend(chunk)
                        if len(data) > expected_size:
                            raise OSError('Pi artifact exceeds accepted byte count')
            return bytes(data)
        async def bounded():
            return await asyncio.wait_for(fetch(), timeout=limits.artifact_transfer_seconds)
        from .bounded_http_loop import run_http
        try:
            data = run_http(bounded())
        except (httpx.TransportError, TimeoutError):
            raise PiArtifactTransportUnavailable('Pi artifact transfer interrupted') from None
        except (httpx.HTTPError, TimeoutError):
            raise OSError('Pi artifact content is unavailable') from None
        if len(data) != expected_size or sha256(data).hexdigest() != expected_sha256:
            raise OSError('Pi artifact content identity changed')
        return data

    def execute(self, request, control, on_event):
        return self._execute(request, control, on_event, None)

    def stage_resources_with_events(self, task_id, manifests, reader, control, on_event):
        return self.stage_resources(task_id, manifests, reader, control, on_event=on_event)

    def stage_resources(self, task_id, manifests, reader, control, *, on_event=lambda _: None):
        from .native_resource_staging import CHUNK_BYTES
        from .resource_manifest import checked_resource
        from hashlib import sha256
        import base64
        sequence = 0
        for item in manifests:
            resource = checked_resource(_json_document(item))
            request = {'task_id': task_id, 'resource': resource}
            def call(operation, **extra):
                nonlocal sequence
                disconnected = False
                delay = .1
                while True:
                    started = time.monotonic()
                    try:
                        control.checkpoint()
                        remaining = max(0.001, control.deadline-time.monotonic())
                        from .application_capacity import limits
                        started = time.monotonic()
                        value = self._call('POST', '/inputs', document={**request, 'operation': operation, **extra},
                            timeout=min(limits.native_staging_wait_seconds,remaining), total_timeout=remaining, checkpoint=control.checkpoint,
                            capacity_dimension='native_staging_wait_seconds',capacity_phase='resource_'+operation,
                            research_transport=True)
                    except PiHTTPFailure as error:
                        error.diagnostic['operation'] = 'resource_' + operation
                        raise
                    except (PiTransportTimeout, PiTransportUnavailable) as error:
                        if isinstance(error, PiTransportTimeout):
                            from .application_capacity import observe_capacity
                            observe_capacity('native_staging_wait_seconds', math.ceil(time.monotonic()-started),
                                             phase='resource_' + operation)
                        if not disconnected:
                            sequence += 1
                            on_event({'event_id': 'staging-transport-' + str(sequence),
                                'type': 'transport_interrupted', 'operation': 'resource_' + operation,
                                'transport_phase': getattr(error, 'transport_phase', 'unknown')})
                            disconnected = True
                        until = min(control.deadline, time.monotonic() + delay)
                        while time.monotonic() < until:
                            try:
                                control.checkpoint()
                            except TimeoutError:
                                terminal = PiTransportTimeout('Pi transport deadline expired; task state is unknown')
                                terminal.operation, terminal.transport_phase = 'resource_' + operation, 'task_deadline'
                                raise terminal from None
                            time.sleep(min(.025, max(0, until-time.monotonic())))
                        delay = min(2., delay*2)
                        continue
                    except TimeoutError:
                        error = PiTransportTimeout('Pi transport deadline expired; task state is unknown')
                        error.operation, error.transport_phase = 'resource_' + operation, 'task_deadline'
                        raise error from None
                    if disconnected:
                        sequence += 1
                        on_event({'event_id': 'staging-transport-' + str(sequence),
                            'type': 'transport_restored', 'operation': 'resource_' + operation})
                    return value
            status = call('status')
            if status.get('resource_id') != resource['resource_id'] or status.get('chunk_bytes') != CHUNK_BYTES:
                raise ValueError('resource staging receipt mismatch')
            received = status.get('received_parts', [])
            if not isinstance(received, list):
                raise ValueError('resource staging parts are invalid')
            pending, index, total, digest = bytearray(), 0, 0, sha256()
            def send(data, index):
                if index in received:
                    return
                receipt = call('part', index=index, content_base64=base64.b64encode(data).decode())
                if receipt != {'index':index,'sha256':sha256(data).hexdigest(),'size_bytes':len(data)}:
                    raise ValueError('resource part receipt mismatch')
            for data in reader(resource):
                control.checkpoint()
                total += len(data)
                if total > resource['size_bytes'] or len(data) > CHUNK_BYTES:
                    raise ValueError('resource reader exceeds admitted size')
                digest.update(data); pending.extend(data)
                while len(pending) >= CHUNK_BYTES:
                    send(bytes(pending[:CHUNK_BYTES]), index)
                    del pending[:CHUNK_BYTES]; index += 1
            if pending:
                send(bytes(pending), index)
            if total != resource['size_bytes'] or digest.hexdigest() != resource['sha256']:
                raise ValueError('resource reader identity mismatch')
            receipt = call('complete')
            if receipt != {'resource_id':resource['resource_id'],'sha256':resource['sha256'],'size_bytes':total}:
                raise ValueError('resource completion receipt mismatch')

    def execute_with_research(self, request, control, on_event, bridge):
        return self._execute(request, control, on_event, bridge)

    def _execute(self, request, control, on_event, bridge):
        if (request.research_binding is None) != (bridge is None):
            raise ValueError('research task requires its bound controller')
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
        research_ready = False
        transport_sequence = 0

        def exchange(method, path, *, operation, **kwargs):
            # Every call here is replay-safe: task admission uses the same task
            # ID and request hash; research writes bind owner, revision and exact
            # receipt bytes. Never restart the model or repeat a business tool.
            nonlocal transport_sequence
            disconnected = False
            delay = .1
            while True:
                checkpoint()
                try:
                    value = self._call(method, path, total_timeout=max(.001, deadline-time.monotonic()),
                        checkpoint=checkpoint, capacity_dimension='native_exchange_seconds',capacity_phase=operation, **kwargs)
                except (PiTransportTimeout, PiTransportUnavailable) as error:
                    checkpoint()
                    if not disconnected:
                        transport_sequence += 1
                        on_event({'event_id': 'transport-' + str(transport_sequence),
                            'type': 'transport_interrupted', 'operation': operation,
                            'transport_phase': getattr(error, 'transport_phase', 'unknown')})
                        disconnected = True
                    until = min(deadline, time.monotonic()+delay)
                    while time.monotonic() < until:
                        checkpoint()
                        time.sleep(min(.025, max(0, until-time.monotonic())))
                    delay = min(2.0, delay*2)
                    continue
                except PiHTTPFailure as error:
                    error.diagnostic['operation'] = operation
                    raise
                if disconnected:
                    transport_sequence += 1
                    on_event({'event_id': 'transport-' + str(transport_sequence),
                        'type': 'transport_restored', 'operation': operation})
                return value

        try:
            accepted = exchange("POST", "/tasks", operation='task_admission', document=request.to_document(),
                                  # Admission validates and durably saves selected file bytes.
                                  # Its read timeout is distinct from lightweight status polling.
                                  timeout=self._exchange_timeout)
            if accepted != {"task_id": request.task_id}:
                raise ValueError("Pi accepted task identity is invalid")
            event_cursor = 0
            while True:
                checkpoint()
                response = exchange("GET", "/tasks/" + request.task_id + '?after=' + str(event_cursor), operation='task_status',
                                      # Scheduling and receipt I/O can exceed one poll interval.
                                      # User cancellation remains checked every 25 ms in _call.
                                      timeout=self._exchange_timeout)
                checkpoint()
                paged = 'event_cursor' in response
                if set(response) != ({"status", "events", "result", "event_cursor"} if paged else {"status", "events", "result"}) or not isinstance(response["events"], list):
                    raise ValueError("Pi task status fields are invalid")
                if len(response["events"]) > limits.event_buffer_count:
                    raise ValueError("Pi events exceed bounds")
                cursor = event_cursor
                if paged:
                    cursor = response['event_cursor']
                    if type(cursor) is not int or not event_cursor <= cursor <= event_cursor + limits.event_buffer_count:
                        raise ValueError('Pi event cursor is invalid')
                    expected = ['event-' + str(index) for index in range(event_cursor + 1, cursor + 1)]
                    if any(not isinstance(event, dict) for event in response['events']) or [
                            event.get('event_id') for event in response['events']] != expected:
                        raise ValueError('Pi event page is incomplete')
                for event in response["events"]:
                    if not isinstance(event, dict) or "event_id" not in event:
                        raise ValueError("Pi event identity is required")
                    _id(event["event_id"])
                    event_id = event["event_id"]
                    if event_id in seen_events and seen_events[event_id] != event:
                        raise ValueError("Pi event identity changed")
                    if event_id not in seen_events:
                        if len(seen_events) >= limits.event_buffer_count and not paged:
                            raise ValueError("Pi event history exceeds bounds")
                        seen_events[event_id] = event
                        on_event(_json_document(event, native_events=True))
                        checkpoint()
                if paged:
                    event_cursor = cursor
                    seen_events.clear()
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
                if bridge is not None:
                    checkpoint()
                    path = '/tasks/' + request.task_id + '/research'
                    if not research_ready:
                        exchange('POST', path, operation='research_bootstrap', document={'owner': bridge.owner_id,
                            'operation': 'bootstrap', 'document': bridge.bootstrap()},
                            timeout=self._exchange_timeout,
                            research_transport=True)
                        research_ready = True
                    pending = exchange('POST', path, operation='research_pending', document={'owner': bridge.owner_id,
                        'operation': 'pending'}, timeout=self._exchange_timeout,
                        research_transport=True)
                    if set(pending) != {'requests', 'source_refs'} or not isinstance(pending['source_refs'], list) or len(pending['source_refs']) > limits.context_references:
                        raise ValueError('research response is invalid')
                    for source in pending['source_refs']:
                        if (not isinstance(source, dict) or set(source) != {'task_id', 'parent_attempt_id', 'source_ref', 'observation_sha256'}
                                or source['task_id'] != request.task_id or source['parent_attempt_id'] != request.parent_attempt_id
                                or not isinstance(source['observation_sha256'], str)
                                or not re.fullmatch(r'[a-f0-9]{64}', source['observation_sha256'])
                                or not re.fullmatch(re.escape('native-observation:' + request.task_id + ':') + r'[a-f0-9]{64}', source['source_ref'])):
                            raise ValueError('research observation source is not task-bound')
                    bridge.admit_sources(pending['source_refs'])
                    if pending['requests']:
                        response_document = bridge.process(pending['requests'])
                        checkpoint()
                        exchange('POST', path, operation='research_acknowledge', document={'owner': bridge.owner_id,
                            'operation': 'acknowledge', 'document': response_document},
                            timeout=self._exchange_timeout,
                            research_transport=True)
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
