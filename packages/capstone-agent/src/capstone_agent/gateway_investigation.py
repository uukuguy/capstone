"""Backend-only access to a gateway's declared investigation HTTP contract."""
import json
from urllib.parse import urlsplit

from .application_capacity import require_capacity
from .data_gateway_mcp import GatewayError, validate


VERSION = 'gateway-investigation/1'
LOG_VERSION = 'gateway-investigation-logs/1'
BASE = '/investigations/v1/'
SCHEMAS = {'bind': ('BindRequest', 'BindingResponse'), 'read': ('ReadRequest', 'Receipt'),
           'list': ('ListRequest', 'ReceiptPage'), 'close': ('ScopeRequest', 'CloseResponse')}


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
        return cls(client, origin, schemas, log_declaration)

    def __init__(self, client, origin, schemas, log_declaration=None):
        self._client = client
        self._origin = origin
        self._schemas = schemas
        self._log_declaration = log_declaration
        self._log_schemas = None

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
            receipt = await self.invoke('read', {**scope, 'client_call_id': client_id})
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
               'logs': {'client_call_id', 'request_id', 'limit', 'cursor'}}
    if operation not in allowed or not isinstance(query, dict) or query.keys() - allowed[operation]:
        raise GatewayError('investigation_request_invalid')
    access = await GatewayInvestigation.discover(connection.http_client, endpoint,
        connection.investigation, connection.investigation_logs)
    if access is None:
        raise GatewayError('investigation_contract_unavailable')
    owner = {'workspace_id': workspace, 'investigation_id': investigation_id}
    binding = await access.invoke('bind', {**owner, 'instance_id': instance_id, 'idempotency_key': investigation_id})
    scope = {**owner, 'binding_handle': binding['binding_handle']}
    if operation == 'logs':
        return await access.read_logs(scope, query)
    return await access.invoke(operation, {**scope, **query})
