"""Backend-only access to a gateway's declared investigation HTTP contract."""
import asyncio
import json
import re
from hashlib import sha256
from contextlib import closing
import sqlite3
from urllib.parse import urlsplit

from httpx import TransportError

from .application_capacity import require_capacity
from .data_gateway_mcp import GatewayError, validate


VERSION = 'gateway-investigation/1'
LOG_VERSION = 'gateway-investigation-logs/1'
EVIDENCE_VERSION = 'gateway-investigation-evidence/1'
BASE = '/investigations/v1/'
SCHEMAS = {'bind': ('BindRequest', 'BindingResponse'), 'read': ('ReadRequest', 'Receipt'),
           'list': ('ListRequest', 'ReceiptPage'), 'close': ('ScopeRequest', 'CloseResponse')}


DEBUG_OBSERVATION_OPERATIONS = ['list', 'read', 'logs', 'probe_data', 'source_files', 'source_lines', 'session_records', 'capstone_records', 'capstone_excerpt', 'publish_finding']


OBSERVATION_TOOL = {
    'description': 'Read on-site receipts, logs, source, or Capstone execution records. Use session_records to find attempts in this session. Pass a returned attempt_id to capstone_records or capstone_excerpt to read its details. List gateway calls before reading by ID.',
    'inputSchema': {'type': 'object', 'additionalProperties': False, 'required': ['operation'],
        'properties': {'operation': {'enum': DEBUG_OBSERVATION_OPERATIONS}, 'query': {'type': 'object',
            'additionalProperties': False, 'properties': {
                'repository': {'enum': ['capstone', 'data-gateway']},
                'after': {'type': 'integer', 'minimum': 0},
                'before': {'type': 'integer', 'minimum': 1},
                'attempt_id': {'type': 'string'},
                'tool': {'type': 'string', 'minLength': 1, 'maxLength': 128},
                'arguments_json': {'type': 'string', 'maxLength': 8192},
                'event_seq': {'type': 'integer', 'minimum': 1},
                'field': {'enum': ['input_excerpt', 'output_excerpt']},
                'finding_state': {'enum': ['located', 'narrowed', 'insufficient_evidence']},
                'event_refs': {'type': 'array', 'items': {'type': 'integer', 'minimum': 1}, 'maxItems': 16, 'uniqueItems': True},
                'gateway_refs': {'type': 'array', 'items': {'type': 'string', 'maxLength': 256}, 'maxItems': 16, 'uniqueItems': True},
                'source_refs': {'type': 'array', 'maxItems': 16, 'items': {'type': 'object',
                    'required': ['repository', 'revision', 'path', 'line'], 'additionalProperties': False,
                    'properties': {'repository': {'enum': ['capstone', 'data-gateway']},
                                   'revision': {'type': 'string', 'maxLength': 64},
                                   'path': {'type': 'string', 'maxLength': 300},
                                   'line': {'type': 'integer', 'minimum': 1}}}},
                'summary': {'type': 'string', 'minLength': 1, 'maxLength': 1200},
                'next_step': {'type': 'string', 'minLength': 1, 'maxLength': 600},
                'prefix': {'type':'string'}, 'offset': {'type':'integer'}, 'path': {'type':'string'}, 'line': {'type':'integer'},
                'request_id': {'type': 'string'}, 'client_call_id': {'type': 'string'},
                'cursor': {'type': 'string'}, 'limit': {'type': 'integer', 'minimum': 1, 'maximum': 50}}}}}}


def investigation_workspace_id(workspace):
    return 'ws_' + sha256(workspace.encode('utf-8')).hexdigest()


class SessionCallJournal:
    """Private, durable dispatch reservations for ordinary session calls."""

    def __init__(self, path):
        self.path = path
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("""CREATE TABLE IF NOT EXISTS session_calls (
                workspace TEXT NOT NULL, thread_id TEXT NOT NULL, attempt_id TEXT NOT NULL,
                operation TEXT NOT NULL, binding TEXT NOT NULL, digest TEXT NOT NULL, client_call_id TEXT NOT NULL,
                PRIMARY KEY (workspace, thread_id, attempt_id, operation))""")

    def reserve(self, *, workspace, thread_id, attempt_id, operation, binding, tool, arguments, client_call_id):
        identity = (workspace, thread_id, attempt_id, operation)
        binding_json = json.dumps(binding, sort_keys=True, allow_nan=False)
        digest = sha256(json.dumps([tool, arguments], sort_keys=True, allow_nan=False).encode()).hexdigest()
        with closing(sqlite3.connect(self.path)) as db, db:
            inserted = db.execute(
                'INSERT OR IGNORE INTO session_calls VALUES (?, ?, ?, ?, ?, ?, ?)',
                (*identity, binding_json, digest, client_call_id),
            ).rowcount
            saved = db.execute(
                'SELECT binding, digest, client_call_id FROM session_calls '
                'WHERE workspace=? AND thread_id=? AND attempt_id=? AND operation=?', identity,
            ).fetchone()
            if saved[:2] != (binding_json, digest):
                raise GatewayError('investigation_request_invalid')
            return saved[2], inserted == 1

    def calls(self, workspace, thread_id, attempt_ids, *, limit):
        placeholders = ','.join('?' for _ in attempt_ids)
        with closing(sqlite3.connect(self.path)) as db:
            rows = db.execute(
                'SELECT attempt_id, binding, client_call_id FROM session_calls WHERE workspace=? AND thread_id=? '
                f'AND attempt_id IN ({placeholders}) ORDER BY rowid DESC LIMIT ?',
                (workspace, thread_id, *attempt_ids, limit),
            ).fetchall()
        return [(attempt_id, json.loads(binding), call_id) for attempt_id, binding, call_id in rows]


async def export_session_calls(journal, registry, workspace, thread_id, attempt_ids):
    rows = await asyncio.to_thread(journal.calls, workspace, thread_id, attempt_ids, limit=17)

    async def project(entry, row):
        attempt_id, binding, call_id = row
        result = {'entry': entry, 'attempt_id': attempt_id}
        try:
            _, gateway = registry.access_for(binding['connection_id'], binding['instance_id'])
            async with asyncio.timeout(6), gateway.client.connect() as connection:
                if (connection.instance_identity or {}).get('instance_id') != binding['instance_id']:
                    return {**result, 'status': 'gateway_instance_changed'}
                access = await GatewayInvestigation.discover(
                    connection.http_client, gateway.client._connection['url'],
                    connection.investigation, connection.investigation_logs,
                )
                if access is None:
                    return {**result, 'status': 'capability_unavailable'}
                scope = {key: binding[key] for key in ('workspace_id', 'investigation_id', 'binding_handle')}
                evidence = await access.read_offline_evidence(
                    getattr(connection, 'investigation_evidence', None), scope, {'client_call_id': call_id},
                )
                return {**result, **evidence}
        except (KeyError, RuntimeError, ValueError, TransportError, OSError, TimeoutError):
            return {**result, 'status': 'read_unavailable'}

    events = []
    for start in range(0, min(len(rows), 16), 4):
        events.extend(await asyncio.gather(*(
            project(index + 1, rows[index]) for index in range(start, min(start + 4, len(rows), 16))
        )))
    statuses = {event['status'] for event in events}
    if not statuses:
        status = 'not_registered'
    elif len(statuses) == 1:
        status = next(iter(statuses))
    elif 'available' in statuses:
        status = 'partial'
    else:
        status = 'unavailable'
    return {'status': status, 'events': events, 'truncated': len(rows) > 16}


async def registered_session_call(client, catalog, tool, arguments, diagnostics, *, journal,
                                  workspace, thread_id, attempt_id, operation, connection_id):
    """Register calls only when the original business connection supports binding."""
    instance = (catalog.get('instance') or {}).get('instance_id')
    if not instance or not diagnostics:
        return None
    async with client.connect() as connection:
        try:
            if (connection.instance_identity or {}).get('instance_id') != instance:
                raise GatewayError('gateway_instance_changed')
            endpoint = client._connection['url']
            access = await GatewayInvestigation.discover(
                connection.http_client, endpoint, connection.investigation, connection.investigation_logs,
            )
            if access is None:
                return None
            owner_id = 'session_' + sha256(json.dumps([workspace, thread_id, attempt_id, connection_id, instance]).encode()).hexdigest()
            owner = {'workspace_id': investigation_workspace_id(workspace), 'investigation_id': owner_id}
            binding = await access.invoke('bind', {**owner, 'instance_id': instance, 'idempotency_key': owner_id})
            scope = {**owner, 'binding_handle': binding['binding_handle']}
            stored_binding = {**scope, 'instance_id': instance, 'connection_id': connection_id,
                              'catalog_revision': catalog['revision']}
            call_id, dispatch = await asyncio.to_thread(
                journal.reserve, workspace=workspace, thread_id=thread_id, attempt_id=attempt_id, operation=operation,
                binding=stored_binding, tool=tool, arguments=arguments, client_call_id=diagnostics['client_call_id'],
            )
            if dispatch:
                observed = await access.call_registered(client, tool, arguments, catalog, scope=scope,
                                                        diagnostics={**diagnostics, 'client_call_id': call_id})
                if 'business_response' in observed:
                    return observed['business_response']
            else:
                try:
                    await access.invoke('read', {**scope, 'client_call_id': call_id})
                except (GatewayError, TransportError, OSError, TimeoutError):
                    pass
        except GatewayError as error:
            failure = error
        else:
            # A receipt proves transport state. It cannot replace a business body.
            failure = GatewayError('gateway_result_body_unavailable', result_unknown=True)
    raise failure


async def _request(client, method, url, document=None):
    options = {'json': document} if document is not None else {}
    async with client.stream(method, url, follow_redirects=False, **options) as response:
        if response.status_code not in (200, 410):
            codes = {401: 'gateway_authentication_failed', 403: 'investigation_access_denied',
                     404: 'receipt_not_visible', 410: 'binding_expired', 503: 'investigation_store_unavailable'}
            raise GatewayError(codes.get(response.status_code, 'investigation_request_rejected'))
        body = bytearray()
        async for chunk in response.aiter_bytes():
            require_capacity('mcp_frame_bytes', len(body) + len(chunk), 'investigation_response')
            body.extend(chunk)
    try:
        packet = json.loads(body)
    except ValueError:
        raise GatewayError('investigation_response_invalid') from None
    if response.status_code == 410:
        detail = packet.get('error') if isinstance(packet, dict) else None
        if isinstance(detail, dict) and detail.get('code') == 'log_cursor_unavailable':
            raise GatewayError('log_cursor_unavailable')
        raise GatewayError('binding_expired')
    return packet


EXPORT_RECEIPT_FIELDS = ('contract_version', 'state', 'observed_status', 'elapsed_ms',
                         'phase_read_status', 'truncated', 'automatic_retry')


def capture_gateway_receipts(page):
    return {'truncated': bool(page.get('next_cursor') or page.get('truncated')),
            'receipts': [{key: row[key] for key in ('client_call_id', *EXPORT_RECEIPT_FIELDS) if key in row}
                         for row in page['receipts'][:32]
                         if isinstance(row, dict) and isinstance(row.get('client_call_id'), str)]}


class GatewayInvestigation:
    @classmethod
    async def discover(cls, client, endpoint, declaration, log_declaration=None):
        if not isinstance(declaration, dict) or declaration.get('version') != VERSION:
            return None
        if declaration.get('contract_path') != BASE + 'contract':
            raise GatewayError('investigation_contract_invalid')
        origin = urlsplit(endpoint)._replace(path='', query='', fragment='').geturl()
        contract = await _request(client, 'GET', origin + declaration['contract_path'])
        if not isinstance(contract, dict) or contract.get('contract_version') != VERSION:
            raise GatewayError('investigation_contract_invalid')
        operations = contract.get('operations')
        schemas = contract.get('schemas')
        if not isinstance(operations, dict) or not isinstance(schemas, dict):
            raise GatewayError('investigation_contract_invalid')
        for operation, names in SCHEMAS.items():
            if (operations.get(operation) != {'method': 'POST', 'path': BASE + operation}
                    or any(not isinstance(schemas.get(name), dict) for name in names)):
                raise GatewayError('investigation_contract_invalid')
        access = cls(client, origin, schemas, log_declaration)
        access._export_policy = contract.get('export')
        return access

    def __init__(self, client, origin, schemas, log_declaration=None):
        self._client = client
        self._origin = origin
        self._schemas = schemas
        self._log_declaration = log_declaration
        self._log_schemas = None
        self._export_policy = None

    def export_fields(self):
        policy = self._export_policy
        if not isinstance(policy, dict) or policy.get('deployment_policy') != 'allow_sanitized':
            return None
        allowed = policy.get('allowed')
        if not isinstance(allowed, list):
            raise GatewayError('investigation_contract_invalid')
        return [key for key in EXPORT_RECEIPT_FIELDS if key in allowed]

    async def read_offline_evidence(self, declaration, scope, query):
        if declaration != {'version': EVIDENCE_VERSION, 'contract_path': BASE + 'evidence-contract'}:
            return {'status': 'capability_unavailable'}
        contract = await _request(self._client, 'GET', self._origin + BASE + 'evidence-contract')
        if (not isinstance(contract, dict) or contract.get('contract_version') != EVIDENCE_VERSION
                or (contract.get('operations') or {}).get('read') != {'method': 'POST', 'path': BASE + 'evidence'}):
            raise GatewayError('investigation_contract_invalid')
        policy = contract.get('export') or {}
        if policy.get('deployment_policy') != 'allow_sanitized':
            return {'status': 'export_not_authorized'}
        fields = {'contract_version', 'evidence_status', 'observed_status', 'truncated', 'first_confirmed_anomaly'}
        if not isinstance(policy.get('allowed'), list) or not fields <= set(policy['allowed']):
            raise GatewayError('investigation_contract_invalid')
        if len(query) != 1 or not all(isinstance(value, str) and value for value in query.values()):
            raise GatewayError('investigation_request_invalid')
        payload = {**scope, **query}
        schemas = contract.get('schemas') or {}
        try:
            validate(schemas['ReadRequest'], payload)
        except Exception:
            raise GatewayError('investigation_request_invalid') from None
        result = await _request(self._client, 'POST', self._origin + BASE + 'evidence', payload)
        try:
            validate(schemas['Evidence'], result)
            if (not isinstance(result, dict) or result.keys() != fields
                    or result.get('contract_version') != EVIDENCE_VERSION):
                raise ValueError()
            anomaly = result['first_confirmed_anomaly']
            if anomaly is not None and (
                not isinstance(anomaly, dict) or anomaly.keys() != {
                    'component', 'stage_category', 'observed_status', 'error_category',
                } or result['truncated'] is not False
            ):
                raise ValueError()
        except Exception:
            raise GatewayError('investigation_response_invalid') from None
        return {'status': 'available', 'projection': result}

    async def export_receipts(self, scope):
        keys = self.export_fields()
        if keys is None:
            return {'status': 'export_not_authorized', 'events': []}
        page = await self.invoke('list', {**scope, 'limit': 32})
        return {'status': 'available', 'truncated': bool(page.get('next_cursor')),
                'events': [{key: row[key] for key in keys if key in row} for row in page['receipts']]}

    async def authorize_snapshot_export(self, scope, call_ids):
        keys = self.export_fields()
        if keys is None:
            return {'status': 'export_not_authorized'}
        page = await self.invoke('list', {**scope, 'limit': 32})
        visible = {row['client_call_id'] for row in page['receipts']}
        if page.get('next_cursor'):
            missing = [call_id for call_id in call_ids if call_id not in visible]

            async def check(call_id):
                try:
                    await self.invoke('read', {**scope, 'client_call_id': call_id})
                except GatewayError as error:
                    if str(error) != 'receipt_not_visible':
                        raise
                    return None
                return call_id

            for offset in range(0, len(missing), 4):
                verified = await asyncio.gather(*(check(call_id) for call_id in missing[offset:offset + 4]))
                visible.update(call_id for call_id in verified if call_id is not None)
        return {'status': 'available', 'allowed': keys,
                'client_call_ids': [call_id for call_id in call_ids if call_id in visible]}

    async def read_logs(self, scope, query):
        """Resolve logs only when selected. Ownership is supplied by the backend."""
        declaration = self._log_declaration
        if not isinstance(declaration, dict) or declaration.get('version') != LOG_VERSION:
            raise GatewayError('investigation_logs_unavailable')
        if declaration.get('contract_path') != BASE + 'log-contract':
            raise GatewayError('investigation_contract_invalid')
        if self._log_schemas is None:
            contract = await _request(self._client, 'GET', self._origin + declaration['contract_path'])
            if (not isinstance(contract, dict) or contract.get('contract_version') != LOG_VERSION
                    or contract.get('operations', {}).get('logs') != {'method':'POST','path':BASE+'logs'}
                    or not all(isinstance(contract.get('schemas', {}).get(name), dict) for name in ('LogRequest','LogPage'))):
                raise GatewayError('investigation_contract_invalid')
            self._log_schemas = contract['schemas']
        if scope.keys() & query.keys() or sum(bool(query.get(key)) for key in ('request_id','client_call_id')) != 1:
            raise GatewayError('investigation_request_invalid')
        document = {**scope, **query}
        try:
            validate(self._log_schemas['LogRequest'], document)
        except Exception:
            raise GatewayError('investigation_request_invalid') from None
        page = await _request(self._client, 'POST', self._origin + BASE + 'logs', document)
        try:
            validate(self._log_schemas['LogPage'], page)
        except Exception:
            raise GatewayError('investigation_response_invalid') from None
        if page.get('contract_version') != LOG_VERSION or page.get('automatic_retry') is not False:
            raise GatewayError('investigation_response_invalid')
        return page

    async def invoke(self, operation, document):
        if operation not in SCHEMAS:
            raise GatewayError('investigation_operation_invalid')
        request_schema, response_schema = SCHEMAS[operation]
        if operation == 'read' and sum(bool(document.get(key)) for key in ('client_call_id', 'request_id')) != 1:
            raise GatewayError('investigation_request_invalid')
        try:
            validate(self._schemas[request_schema], document)
        except Exception:
            raise GatewayError('investigation_request_invalid') from None
        result = await _request(self._client, 'POST', self._origin + BASE + operation, document)
        try:
            validate(self._schemas[response_schema], result)
        except Exception:
            raise GatewayError('investigation_response_invalid') from None
        if operation == 'read' and (result.get('automatic_retry') is not False or
                any(result.get(key) != document[key] for key in ('request_id', 'client_call_id') if key in document)):
            raise GatewayError('investigation_response_invalid')
        return result

    async def call_registered(self, gateway, name, arguments, catalog, *, scope, diagnostics):
        """Caller supplies the durable ownership tuple and pre-registered local call ID."""
        metadata = {**scope, 'contract_version': VERSION}
        client_id = diagnostics.get('client_call_id')
        try:
            validate(self._schemas['CallMetadata'], metadata)
        except Exception:
            raise GatewayError('investigation_request_invalid') from None
        try:
            response = await gateway.call(name, arguments, catalog, diagnostics=diagnostics, investigation=metadata)
        except GatewayError as error:
            if not error.result_unknown:
                raise
            try:
                receipt = await self.invoke('read', {**scope, 'client_call_id': client_id})
            except (GatewayError, TransportError, OSError, TimeoutError):
                return {'result_state': 'unknown', 'receipt_status': 'unavailable',
                        'client_call_id': client_id, 'automatic_retry': False}
            return {'receipt': receipt}
        body = response.get('structuredContent')
        if response.get('isError') and isinstance(body, dict) and body.get('contract_version') == VERSION:
            failure = body.get('error')
            if isinstance(failure, dict) and failure.get('code') == 'call_already_registered':
                receipt = body.get('receipt')
                try:
                    validate(self._schemas['Receipt'], receipt)
                except Exception:
                    raise GatewayError('investigation_response_invalid') from None
                if receipt.get('client_call_id') != client_id or receipt.get('automatic_retry') is not False:
                    raise GatewayError('investigation_response_invalid')
                return {'receipt': receipt}
        return {'business_response': response}

async def read_bound_observation(connection, endpoint, *, instance_id, workspace, investigation_id, operation, query):
    """Resolve the private handle on the dedicated session and return only the requested observation."""
    if (connection.instance_identity or {}).get('instance_id') != instance_id:
        raise GatewayError('gateway_instance_changed')
    allowed = {'list': {'limit', 'cursor'}, 'read': {'client_call_id', 'request_id'},
               'offline_evidence': {'client_call_id', 'request_id'},
               'logs': {'client_call_id', 'request_id', 'limit', 'cursor'}, 'export': set(),
               'authorize_snapshot_export': {'client_call_ids'}}
    if operation not in allowed or not isinstance(query, dict) or query.keys() - allowed[operation]:
        raise GatewayError('investigation_request_invalid')
    access = await GatewayInvestigation.discover(connection.http_client, endpoint,
        connection.investigation, connection.investigation_logs)
    if access is None:
        raise GatewayError('investigation_contract_unavailable')
    owner = {'workspace_id': investigation_workspace_id(workspace), 'investigation_id': investigation_id}
    binding = await access.invoke('bind', {**owner, 'instance_id': instance_id, 'idempotency_key': investigation_id})
    scope = {**owner, 'binding_handle': binding['binding_handle']}
    if operation == 'logs':
        return await access.read_logs(scope, query)
    if operation == 'offline_evidence':
        return await access.read_offline_evidence(getattr(connection, 'investigation_evidence', None), scope, query)
    if operation == 'export':
        return await access.export_receipts(scope)
    if operation == 'authorize_snapshot_export':
        call_ids = query.get('client_call_ids')
        if (not isinstance(call_ids, list) or len(call_ids) > 32 or any(
                not isinstance(call_id, str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,128}', call_id)
                for call_id in call_ids) or len(set(call_ids)) != len(call_ids)):
            raise GatewayError('investigation_request_invalid')
        return await access.authorize_snapshot_export(scope, call_ids)
    return await access.invoke(operation, {**scope, **query})


async def run_bound_read_probe(gateway, *, instance_id, workspace, investigation_id,
                               tool, arguments, client_call_id, include_result=False):
    catalog = await gateway.prepare()
    if (catalog.get('instance') or {}).get('instance_id') != instance_id:
        raise GatewayError('gateway_instance_changed')
    if tool not in catalog['tools']:
        raise GatewayError('investigation_request_invalid')
    exact = (await gateway.exact_contracts([tool], catalog))[tool]
    hints = exact.get('annotations') or {}
    if not (hints.get('readOnlyHint') is True and hints.get('destructiveHint') is False
            and hints.get('openWorldHint') is False):
        raise GatewayError('investigation_access_denied')
    try:
        validate(exact['inputSchema'], arguments)
    except Exception:
        raise GatewayError('investigation_request_invalid') from None
    async with gateway.connect() as session:
        if (session.instance_identity or {}).get('instance_id') != instance_id:
            raise GatewayError('gateway_instance_changed')
        access = await GatewayInvestigation.discover(session.http_client, gateway._connection['url'],
                                                     session.investigation, session.investigation_logs)
        if access is None:
            raise GatewayError('investigation_contract_unavailable')
        owner = {'workspace_id': investigation_workspace_id(workspace), 'investigation_id': investigation_id}
        binding = await access.invoke('bind', {**owner, 'instance_id': instance_id, 'idempotency_key': investigation_id})
        scope = {**owner, 'binding_handle': binding['binding_handle']}
        trace = sha256(investigation_id.encode('utf-8')).hexdigest()[:32]
        observed = await access.call_registered(gateway, tool, arguments, catalog, scope=scope, diagnostics={
            'client_call_id': client_call_id, 'task_id': investigation_id, 'run_id': investigation_id,
            'trace_id': trace, 'parent_span_id': 'attempt:' + trace,
        })
        if observed.get('result_state') == 'unknown':
            return {**observed, **({'data_status': 'unavailable'} if include_result else {})}
        receipt = observed.get('receipt')
        if receipt is None:
            receipt = await access.invoke('read', {**scope, 'client_call_id': client_call_id})
        if not include_result:
            return receipt
        result = observed.get('business_response')
        content = result.get('structuredContent') if isinstance(result, dict) else None
        if content is None:
            return {'receipt': receipt, 'data_status': 'unavailable'}
        if len(json.dumps(content, ensure_ascii=False).encode()) > 16 * 1024:
            return {'receipt': receipt, 'data_status': 'exceeds_summary_limit'}
        return {'receipt': receipt, 'data_status': 'onsite_only', 'data': content}
