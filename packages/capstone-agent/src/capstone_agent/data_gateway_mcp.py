"""Host-owned remote MCP resource. Credentials never cross the task boundary."""
from __future__ import annotations

import asyncio
from base64 import urlsafe_b64encode
from contextlib import asynccontextmanager
from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
from threading import RLock
from typing import Any
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator
from referencing import Registry
from referencing.exceptions import NoSuchResource

from .application_capacity import limits, require_capacity, CapacityExceeded


_TOOL_NAME = re.compile(r'[A-Za-z0-9_.-]{1,128}')
_INSTRUCTIONS_BYTES = 16384
# Agreed service entry points. Business operations never belong in this list.
_GATEWAY_ENTRY_POINTS = ('discover_gateway', 'describe_gateway_contract')
_PROGRESSIVE = 'data-gateway/progressive-discovery'

def identity_text(value):
    return isinstance(value, str) and 0 < len(value) <= 256 and not any(ord(c) < 32 or ord(c) == 127 for c in value)



def checked_instance_identity(value):
    """Project only the published v1 handshake identity; malformed means unknown."""
    if not isinstance(value, dict) or type(value.get('schema_version')) is not int or value['schema_version'] != 1:
        return None
    environment, source = value.get('environment'), value.get('data_source')
    if (not all(identity_text(value.get(key)) for key in ('instance_id', 'instance_name'))
            or type(value.get('offline')) is not bool
            or not isinstance(environment, dict) or not isinstance(source, dict)
            or not all(identity_text(environment.get(key)) for key in ('id', 'label'))
            or not identity_text(source.get('label'))):
        return None
    return {'schema_version': 1, 'instance_id': value['instance_id'], 'instance_name': value['instance_name'],
            'environment': {key: environment[key] for key in ('id', 'label')},
            'offline': value['offline'], 'data_source': {'label': source['label']}}


@dataclass(frozen=True)
class InitializedGatewaySession:
    """Connection-local initialization data; never shared between MCP sessions."""
    session: object
    instructions: str | None = None
    server_info: object = None
    instance_identity: object = None
    progressive: object = None

# These failures stop further remote probes in the admitted task. A new user
# instruction gets its own task state and can check the resource again.
TASK_STOP_ERRORS = frozenset({'gateway_timeout', 'gateway_transport_failed',
    'gateway_authentication_failed', 'gateway_endpoint_rejected', 'gateway_connection_failed', 'gateway_call_failed_no_retry',
    'gateway_catalog_invalid', 'gateway_catalog_unavailable', 'contract_publication_unavailable'})
_PUBLIC_GATEWAY_ERRORS = TASK_STOP_ERRORS | {'gateway_arguments_invalid', 'gateway_output_invalid',
    'gateway_operation_retry_blocked',
    'gateway_tool_not_admitted', 'gateway_policy_invalid', 'gateway_connection_config_invalid',
    'gateway_publication_changed', 'contract_publication_unavailable'}


class GatewayError(ValueError):
    """A public error code, without upstream exception text."""
    def __init__(self, code, request_id=None, *, validation_errors=None):
        super().__init__(code)
        self.request_id = request_id if identity_text(request_id) else None
        self.validation_errors = validation_errors or []


def argument_validation_details(error):
    """Expose bounded schema locations and types, never argument values."""
    pending, leaves = [error], []
    for _ in range(32):
        if not pending:
            break
        item = pending.pop()
        if item.context:
            pending.extend(item.context[:8])
        else:
            leaves.append(item)
    result = []
    for item in sorted(leaves, key=lambda item: len(item.absolute_path), reverse=True)[:8]:
        path = '/' + '/'.join(str(part).replace('~', '~0').replace('/', '~1') for part in item.absolute_path)
        value = item.instance
        actual = ('null' if value is None else 'boolean' if isinstance(value, bool) else
                  'object' if isinstance(value, dict) else 'array' if isinstance(value, list) else
                  'string' if isinstance(value, str) else 'integer' if isinstance(value, int) else 'number')
        detail = {'path': path[:256], 'rule': str(item.validator)[:64], 'actual_type': actual}
        if item.validator == 'type':
            detail['expected'] = item.validator_value
        result.append(detail)
    return result


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False).encode()


def fingerprint(value):
    return sha256(encode(value)).hexdigest()


def gateway_http_timeout():
    """Keep connection setup short. A tool read may use the admitted tool budget.

    A fixed 30s client read expires before ``mcp_tool_seconds`` and is then
    recorded as ``gateway_timeout``, which stops every later gateway call in
    the same task.
    """
    import httpx
    setup = 30.0
    return httpx.Timeout(connect=setup, read=float(limits.mcp_tool_seconds), write=setup, pool=setup)


def _deny(uri):
    raise NoSuchResource(ref=uri)


def public_failure(error, fallback):
    import httpx
    pending, seen = [error], set()
    transport_failure = None
    for _ in range(32):
        if not pending:
            break
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        # MCP task groups may wrap a pre-call admission rejection during context
        # teardown. Preserve only fixed public codes, never exception messages.
        if isinstance(current, GatewayError) and str(current) in _PUBLIC_GATEWAY_ERRORS:
            return str(current)
        if getattr(getattr(current, 'response', None), 'status_code', None) in {401, 403}:
            return 'gateway_authentication_failed'
        if getattr(getattr(current, 'response', None), 'status_code', None) == 421:
            return 'gateway_endpoint_rejected'
        if isinstance(current, (TimeoutError, httpx.TimeoutException)):
            transport_failure = 'gateway_timeout'
        elif isinstance(current, httpx.TransportError) and transport_failure is None:
            transport_failure = 'gateway_transport_failed'
        pending.extend(getattr(current, 'exceptions', ()))
        if current.__cause__ is not None:
            pending.append(current.__cause__)
    return transport_failure or fallback


def validate(schema, value):
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema, registry=Registry(retrieve=_deny)).validate(value)


class DataGatewayMcp:
    def __init__(self, connection_path: Path, policy: dict, *, connect=None):
        self.connection_path = Path(connection_path)
        self.policy = deepcopy(policy)
        allowed = policy.get('allowed_tools', [])
        # v1 supports existing private configurations only. Production uses v2:
        # application authorization of safe effects on this fixed trusted service.
        legacy = (set(policy) == {'schema', 'resource_id', 'namespace', 'allowed_tools'}
            and policy.get('schema') == 'capstone-data-gateway/1'
            and isinstance(allowed, list) and bool(allowed)
            and all(isinstance(n, str) and _TOOL_NAME.fullmatch(n) for n in allowed)
            and len(set(allowed)) == len(allowed))
        dynamic = (set(policy) == {'schema', 'resource_id', 'namespace', 'admission'}
            and policy.get('schema') == 'capstone-data-gateway/2'
            and policy.get('admission') == 'trusted-service-safe-effects')
        if (not (legacy or dynamic) or policy.get('resource_id') != 'data-gateway'
                or policy.get('namespace') != 'data_gateway_'):
            raise GatewayError('gateway_policy_invalid')
        try:
            path = self.connection_path
            if path.is_symlink() or path.stat().st_mode & 0o077:
                raise ValueError()
            if path.stat().st_size > 16384:
                raise ValueError()
            connection = json.loads(path.read_text())
            address = urlsplit(connection['url'])
            if address.port is not None and not 0 < address.port <= 65535:
                raise ValueError()
            if (not {'transport', 'url', 'headers'} <= set(connection) or set(connection) - {'transport', 'url', 'headers', 'name'}
                    or ('name' in connection and not identity_text(connection['name']))
                    or connection['transport'] != 'streamable-http'
                    or address.scheme not in {'http', 'https'} or not address.hostname
                    or address.username or address.password or address.query or address.fragment
                    or not isinstance(connection['headers'], dict)
                    or set(connection['headers']) != {'Authorization'}
                    or not isinstance(connection['headers']['Authorization'], str)
                    or not connection['headers']['Authorization'].startswith('Bearer ')
                    or len(connection['headers']['Authorization']) < 15
                    or any(c in connection['headers']['Authorization'] for c in '\r\n')):
                raise ValueError()
        except Exception:
            raise GatewayError('gateway_connection_config_invalid') from None
        self._connection = connection
        self.connect = connect or self._connect
        self._accepted = {}
        self._exact_sections = {}
        self._exact_lock = RLock()

    def public_identity(self):
        address = urlsplit(self._connection['url'])
        hostname = address.hostname
        host = f'[{hostname}]' if ':' in hostname else hostname
        result = {'display_address': f'{host}:{address.port or (443 if address.scheme == "https" else 80)}'}
        if self._connection.get('name'):
            result['connection_name'] = self._connection['name']
        return result

    @asynccontextmanager
    async def _connect(self):
        import httpx
        from mcp import ClientSession
        from mcp.client.streamable_http import streamable_http_client
        async with httpx.AsyncClient(headers=self._connection['headers'], timeout=gateway_http_timeout(),
                                     trust_env=False, follow_redirects=False) as client:
            async with streamable_http_client(self._connection['url'], http_client=client) as (reader, writer, _):
                async with ClientSession(reader, writer) as session:
                    initialized = await session.initialize()
                    experimental = initialized.capabilities.experimental
                    instance = experimental.get('data-gateway/identity') if isinstance(experimental, dict) else None
                    declaration = experimental.get(_PROGRESSIVE) if isinstance(experimental, dict) else None
                    yield InitializedGatewaySession(session, initialized.instructions, initialized.serverInfo.model_dump(), instance, declaration)

    def _progressive_declaration(self, connection):
        declaration = getattr(connection, 'progressive', None)
        if not isinstance(declaration, dict) or declaration.get('version') != '1':
            return None
        try:
            if (declaration['transport'] != 'resources/read'
                    or declaration['request_encoding'] != 'base64url-unpadded-utf8-json'
                    or declaration['fingerprint_version'] != 'canonical-json-sha256/1'
                    or checked_instance_identity(declaration['identity']) is None
                    or not all(identity_text(declaration[k]) for k in ('publication_revision', 'access_view_id'))):
                raise ValueError()
            for key in ('catalog_items', 'catalog_bytes', 'batch_items', 'batch_bytes', 'request_bytes'):
                if type(declaration['limits'][key]) is not int or declaration['limits'][key] <= 0:
                    raise ValueError()
            for operation in ('catalog', 'contracts', 'check'):
                entry = declaration['entries'][operation]
                # Only service-owned metadata resource URIs, never endpoints or files.
                uri = entry['uri_template']
                if (not isinstance(uri, str) or not uri.startswith('gateway://discovery/')
                        or uri.count('{request}') != 1 or len(uri) > 512):
                    raise ValueError()
                Draft202012Validator.check_schema(entry['input_schema'])
        except (KeyError, TypeError, ValueError):
            raise GatewayError('gateway_catalog_invalid') from None
        return deepcopy(declaration)

    async def _progressive_request(self, connection, declaration, operation, arguments):
        entry = declaration['entries'][operation]
        try:
            validate(entry['input_schema'], arguments)
            raw = encode(arguments)
            if len(raw) > min(declaration['limits']['request_bytes'], limits.mcp_frame_bytes):
                raise ValueError()
            uri = entry['uri_template'].replace('{request}', urlsafe_b64encode(raw).decode().rstrip('='))
            from pydantic import AnyUrl
            session: Any = getattr(connection, 'session', connection)
            result = await session.read_resource(AnyUrl(uri))
            if len(result.contents) != 1 or not isinstance(getattr(result.contents[0], 'text', None), str):
                raise ValueError()
            body = result.contents[0].text
            maximum = declaration['limits']['batch_bytes' if operation == 'contracts' else 'catalog_bytes']
            if len(body.encode()) > min(maximum, limits.mcp_frame_bytes):
                raise ValueError()
            packet = json.loads(body)
            if (not isinstance(packet, dict) or packet.get('protocol_version') != '1'
                    or packet.get('source_accessed') is not False):
                raise ValueError()
            if packet.get('access_view_id') != declaration['access_view_id']:
                raise GatewayError('gateway_publication_changed')
            if packet.get('status') == 'error':
                code = packet.get('error', {}).get('code')
                raise GatewayError('gateway_publication_changed' if code in {
                    'publication_changed', 'authorization_view_changed', 'tool_contract_changed'} else 'gateway_catalog_invalid')
            if packet.get('status') not in ('ok', 'partial'):
                raise ValueError()
            if operation != 'check' and packet.get('publication_revision') != declaration['publication_revision']:
                raise GatewayError('gateway_publication_changed')
            return packet
        except GatewayError:
            raise
        except (ValueError, TypeError, KeyError, AttributeError):
            raise GatewayError('gateway_catalog_invalid') from None

    async def _prepare_progressive(self, connection, declaration):
        tools, cursors, cursor = {}, set(), None
        for _ in range(128):
            arguments = {'view': 'tools', 'publication_revision': declaration['publication_revision']}
            if cursor:
                arguments['cursor'] = cursor
            packet = await self._progressive_request(connection, declaration, 'catalog', arguments)
            items = packet.get('items')
            if (packet.get('view') != 'tools' or not isinstance(items, list)
                    or len(items) > declaration['limits']['catalog_items']):
                raise GatewayError('gateway_catalog_invalid')
            for item in items:
                if (not isinstance(item, dict) or not isinstance(item.get('name'), str)
                        or not _TOOL_NAME.fullmatch(item['name'])
                        or not all(identity_text(item.get(k)) for k in ('tool_key', 'tool_contract_revision', 'summary_revision'))
                        or item.get('output_schema_state') not in ('declared', 'absent')
                        or not isinstance(item.get('section_fingerprints'), dict)):
                    raise GatewayError('gateway_catalog_invalid')
                name = self.policy['namespace'] + item['name']
                if name in tools:
                    raise GatewayError('gateway_catalog_invalid')
                effects = item.get('effects')
                if self.policy['schema'] == 'capstone-data-gateway/1':
                    admitted = item['name'] in self.policy['allowed_tools']
                else:
                    admitted = (isinstance(effects, dict) and type(effects.get('readOnlyHint')) is bool
                                and effects.get('destructiveHint') is False and effects.get('openWorldHint') is False)
                if admitted:
                    capability = item.get('capability') or {}
                    description = capability.get('semantics', {}).get('purpose', item['name'])
                    tools[name] = {'name': item['name'], 'description': description, 'annotations': effects,
                        '_meta': {'data-gateway/capability': capability,
                                  'data-gateway/toolset': item.get('toolset_id')}, 'progressive': deepcopy(item)}
            cursor = packet.get('next_cursor')
            if not cursor:
                if packet.get('truncated') is not False:
                    raise GatewayError('gateway_catalog_invalid')
                break
            if (not isinstance(cursor, str) or not 0 < len(cursor) <= 16384
                    or any(ord(c) < 32 for c in cursor) or cursor in cursors or not items):
                raise GatewayError('gateway_catalog_invalid')
            cursors.add(cursor)
        else:
            raise GatewayError('gateway_catalog_invalid')
        if not tools:
            raise GatewayError('gateway_catalog_unavailable')
        value = {'resource_id': self.policy['resource_id'], 'tools': tools,
                 'tool_hashes': {name: item['progressive']['tool_contract_revision'] for name, item in tools.items()},
                 'entry_tools': [], 'instructions': getattr(connection, 'instructions', '') or '',
                 'instance': checked_instance_identity(declaration['identity']), 'progressive': declaration}
        require_capacity('mcp_frame_bytes', len(encode(value)), 'gateway_catalog')
        return {**value, 'revision': fingerprint(value)}

    async def exact_contracts(self, names, catalog, *, connection=None):
        """Resolve selected schemas without changing the admitted metadata snapshot."""
        if (self._accepted.get(catalog.get('revision')) != catalog or not isinstance(names, list)
                or any(name not in catalog['tools'] for name in names)):
            raise GatewayError('gateway_tool_not_admitted')
        if 'progressive' not in catalog:
            return {name: deepcopy(catalog['tools'][name]) for name in names}
        if connection is None:
            async with self.connect() as connected:
                return await self.exact_contracts(names, catalog, connection=connected)
        declaration = catalog['progressive']
        current = self._progressive_declaration(connection)
        if current != declaration:
            raise GatewayError('gateway_publication_changed')
        pending, selected, resolved_sections = [], {}, {}
        for name in dict.fromkeys(names):
            item = catalog['tools'][name]['progressive']
            key = (declaration['identity']['instance_id'], declaration['access_view_id'],
                   item['tool_key'], item['tool_contract_revision'])
            with self._exact_lock:
                sections = deepcopy(self._exact_sections.get(key, {}))
            resolved_sections[key] = sections
            needed = [s for s in ('input_schema', 'output_schema')
                      if s not in sections and (s != 'output_schema' or item['output_schema_state'] == 'declared')]
            selected[name] = (item, key)
            if needed:
                pending.append({'tool_key': item['tool_key'], 'tool_contract_revision': item['tool_contract_revision'], 'sections': needed})
        batch_size = min(8, declaration['limits']['batch_items'])
        for start in range(0, len(pending), batch_size):
            requests = pending[start:start + batch_size]
            packet = await self._progressive_request(connection, declaration, 'contracts',
                {'publication_revision': declaration['publication_revision'], 'requests': requests})
            items = packet.get('items')
            if not isinstance(items, list) or len(items) != len(requests):
                raise GatewayError('gateway_catalog_invalid')
            staged = []
            for request, response in zip(requests, items):
                item, key = next((i, k) for i, k in selected.values() if i['tool_key'] == request['tool_key'])
                if (not isinstance(response, dict) or response.get('status') != 'ok'
                        or any(response.get(k) != item.get(k) for k in ('tool_key', 'name', 'id', 'registration_id',
                            'provider_id', 'toolset_id', 'tool_contract_revision', 'output_schema_state'))
                        or set(response.get('sections', {})) != set(request['sections'])):
                    raise GatewayError('gateway_catalog_invalid')
                sections = response['sections']
                for section, body in sections.items():
                    digest = fingerprint(body)
                    if (digest != item['section_fingerprints'].get(section)
                            or digest != response.get('section_fingerprints', {}).get(section)
                            or not isinstance(body, (dict, bool))):
                        raise GatewayError('gateway_catalog_invalid')
                    Draft202012Validator.check_schema(body)
                staged.append((key, sections))
            for key, sections in staged:
                resolved_sections[key].update(deepcopy(sections))
                with self._exact_lock:
                    self._exact_sections.pop(key, None)
                    self._exact_sections[key] = deepcopy(resolved_sections[key])
                    while sum(len(encode(value)) for value in self._exact_sections.values()) > limits.history_context_bytes:
                        self._exact_sections.pop(next(iter(self._exact_sections)))
        result = {}
        for name, (item, key) in selected.items():
            sections = resolved_sections[key]
            result[name] = {**deepcopy(catalog['tools'][name]), 'inputSchema': deepcopy(sections['input_schema'])}
            if item['output_schema_state'] == 'declared':
                result[name]['outputSchema'] = deepcopy(sections['output_schema'])
        return result

    async def _catalog(self, session, *, tool_name=None):
        instructions = getattr(session, 'instructions', None) if hasattr(session, 'session') else None
        server_info = getattr(session, 'server_info', None)
        instance = checked_instance_identity(getattr(session, 'instance_identity', None))
        session = getattr(session, 'session', session)
        if tool_name is None:
            if instructions is None:
                instructions = ''
            if not isinstance(instructions, str) or len(instructions.encode('utf-8')) > _INSTRUCTIONS_BYTES:
                raise GatewayError('gateway_catalog_invalid')
        schemas, cursor, seen_names, seen_cursors = {}, None, set(), set()
        for _ in range(16):
            page = await session.list_tools(**({'cursor': cursor} if cursor else {}))
            for tool in page.tools:
                if tool_name is not None and tool.name != tool_name.removeprefix(self.policy['namespace']):
                    continue
                if (not isinstance(tool.name, str) or not _TOOL_NAME.fullmatch(tool.name)
                        or tool.name in seen_names):
                    raise GatewayError('gateway_catalog_invalid')
                seen_names.add(tool.name)
                name = self.policy['namespace'] + tool.name
                document = tool.model_dump(mode='json', by_alias=True, exclude_none=True)
                if self.policy['schema'] == 'capstone-data-gateway/1':
                    if tool.name not in self.policy['allowed_tools']:
                        continue
                else:
                    effects = document.get('annotations')
                    if (not isinstance(effects, dict)
                            or type(effects.get('readOnlyHint')) is not bool
                            or effects.get('destructiveHint') is not False
                            or effects.get('openWorldHint') is not False):
                        continue
                try:
                    if document['name'] != tool.name:
                        raise ValueError()
                    # Admission validates schemas. At call time compare the full
                    # published contract first, so even an invalid changed schema
                    # remains a rejection of this tool rather than the whole task.
                    if tool_name is None:
                        Draft202012Validator.check_schema(document['inputSchema'])
                        if 'outputSchema' in document:
                            Draft202012Validator.check_schema(document['outputSchema'])
                except Exception:
                    raise GatewayError('gateway_catalog_invalid') from None
                schemas[name] = document
            next_cursor = page.nextCursor
            if not next_cursor:
                break
            if not isinstance(next_cursor, str) or next_cursor in seen_cursors:
                raise GatewayError('gateway_catalog_invalid')
            seen_cursors.add(next_cursor)
            cursor = next_cursor
        else:
            raise GatewayError('gateway_catalog_invalid')
        if tool_name is None and not schemas:
            raise GatewayError('gateway_catalog_unavailable')
        value = {'resource_id': self.policy['resource_id'], 'tools': schemas,
                 'tool_hashes': {n: fingerprint(s) for n, s in schemas.items()}}
        if tool_name is None:
            value['entry_tools'] = [self.policy['namespace'] + entry for entry in _GATEWAY_ENTRY_POINTS
                                    if self.policy['namespace'] + entry in schemas]
            value['instructions'] = instructions
            if instance is not None:
                value['instance'] = instance
            if isinstance(server_info, dict):
                value['server_info'] = {key: server_info[key] for key in ('name', 'version') if identity_text(server_info.get(key))}
        require_capacity('mcp_frame_bytes', len(encode(value)), 'gateway_catalog')
        return {**value, 'revision': fingerprint(value)}

    async def _publication(self, connection, tool):
        session = getattr(connection, 'session', connection)
        response = await session.call_tool(tool, arguments={})
        value = response.model_dump(mode='json', by_alias=True, exclude_none=True)
        require_capacity('mcp_frame_bytes', len(encode(value)), 'gateway_contract')
        body = value.get('structuredContent')
        if not isinstance(body, dict):
            try:
                body = json.loads(next(item['text'] for item in value.get('content', []) if item.get('type') == 'text'))
            except Exception:
                raise GatewayError('gateway_catalog_invalid') from None
        request_id = body.get('provenance', {}).get('request_id')
        if value.get('isError') or body.get('status') == 'error':
            raise GatewayError('contract_publication_unavailable', request_id)
        data = body.get('data', {})
        stamp = data.get('contract_updated_at')
        from datetime import datetime
        try:
            if not isinstance(stamp, str) or datetime.fromisoformat(stamp).utcoffset() is None:
                raise ValueError()
        except (ValueError, TypeError):
            raise GatewayError('gateway_catalog_invalid', request_id) from None
        if tool == 'check_gateway_contract':
            if not {'instance_id', 'contract_updated_at'} <= set(data) or not identity_text(data.get('instance_id')):
                raise GatewayError('gateway_catalog_invalid', request_id)
            return deepcopy(data)
        return stamp

    async def _prepare_connected(self, session):
        declaration = self._progressive_declaration(session)
        if declaration is not None:
            catalog = await self._prepare_progressive(session, declaration)
            self._accepted[catalog['revision']] = deepcopy(catalog)
            return catalog
        catalog = await self._catalog(session)
        if self.policy['namespace'] + 'check_gateway_contract' in catalog['tools']:
            before = await self._publication(session, 'check_gateway_contract')
            # The first list detects supported publication guards. Bracket the
            # admitted catalog with those guards; model discovery and complete
            # usage contracts are not prerequisites for host admission.
            catalog = await self._catalog(session)
            after = await self._publication(session, 'check_gateway_contract')
            if not isinstance(after, dict):
                raise GatewayError('gateway_catalog_invalid')
            instance = catalog.get('instance', {}).get('instance_id')
            if (before != after
                    or (instance and instance != after['instance_id'])):
                raise GatewayError('gateway_publication_changed')
            catalog.pop('revision')
            catalog['contract_publication'] = after
            catalog['revision'] = fingerprint(catalog)
        self._accepted[catalog['revision']] = deepcopy(catalog)
        return deepcopy(catalog)

    async def refresh_catalog(self, catalog):
        if self._accepted.get(catalog.get('revision')) != catalog:
            raise GatewayError('gateway_tool_not_admitted')
        try:
            async with asyncio.timeout(limits.mcp_catalog_seconds):
                async with self.connect() as session:
                    if 'progressive' in catalog:
                        declaration = self._progressive_declaration(session)
                        if declaration == catalog['progressive']:
                            return deepcopy(catalog)
                        return await self._prepare_connected(session)
                    if 'contract_publication' in catalog:
                        current = await self._publication(session, 'check_gateway_contract')
                        if current == catalog['contract_publication']:
                            return deepcopy(catalog)
                    return await self._prepare_connected(session)
        except GatewayError:
            raise
        except Exception as error:
            raise GatewayError(public_failure(error, 'gateway_connection_failed')) from None

    async def prepare(self):
        try:
            async with asyncio.timeout(min(60, limits.mcp_initialize_seconds + limits.mcp_catalog_seconds)):
                async with self.connect() as session:
                    catalog = await self._prepare_connected(session)
            self._accepted[catalog['revision']] = deepcopy(catalog)
            return deepcopy(catalog)
        except GatewayError:
            raise
        except CapacityExceeded:
            raise
        except Exception as error:
            raise GatewayError(public_failure(error, 'gateway_connection_failed')) from None

    def contract_context_entry(self, name, arguments, result, catalog):
        """Recognize only the registered gateway's exact contract-lookup protocol."""
        if (self._accepted.get(catalog.get('revision')) != catalog
                or catalog['tools'].get(name, {}).get('name') != _GATEWAY_ENTRY_POINTS[1]
                or set(arguments) - {'tool_name', 'section', 'expected_revision'}):
            return None
        targets = [(registered, schema) for registered, schema in catalog['tools'].items()
                   if arguments.get('tool_name') in (registered, schema.get('name'))]
        if len(targets) != 1:
            return None
        target, schema = targets[0]
        section = arguments.get('section', 'complete')
        body = result.get('structuredContent', {})
        data = body.get('data') if isinstance(body, dict) else None
        if (not isinstance(section, str) or section not in {'complete', 'usage', 'input_schema', 'output_schema'}
                or not isinstance(body, dict) or result.get('isError') is True
                or body.get('status') not in {'ok', 'success'}
                or not isinstance(data, dict) or data.get('name') != schema['name']
                or data.get('section', 'complete') != section
                or not identity_text(data.get('contract_revision'))
                or arguments.get('expected_revision') not in (None, data['contract_revision'])):
            return None
        return {'catalog_revision': catalog['revision'], 'lookup_tool': name, 'tool': target,
                'section': section, 'contract_revision': data['contract_revision'], 'data': deepcopy(data)}

    async def call(self, name, arguments, catalog, *, diagnostics=None):
        from .gateway_diagnostics import checked_diagnostics
        context = checked_diagnostics(diagnostics)
        try:
            if (self._accepted.get(catalog.get('revision')) != catalog or name not in catalog['tools']
                    or not isinstance(arguments, dict)):
                raise GatewayError('gateway_tool_not_admitted')
            require_capacity('mcp_frame_bytes', len(encode(arguments)), 'gateway_arguments')
            schema = catalog['tools'][name]
            # The adapter owns transport names. Contract lookup parameters use
            # source names from this connection, never a guessed prefix strip.
            if schema['name'] == 'describe_gateway_contract':
                target = arguments.get('tool_name')
                published = catalog['tools'].get(target) if isinstance(target, str) else None
                if published is not None:
                    if (target != published['name'] and any(
                            item['name'] == target for item in catalog['tools'].values())):
                        raise GatewayError('gateway_arguments_invalid')
                    arguments = {**arguments, 'tool_name': published['name']}
            if 'progressive' in catalog:
                async with asyncio.timeout(limits.mcp_tool_seconds):
                    async with self.connect() as connection:
                        schemas = await self.exact_contracts([name], catalog, connection=connection)
                        schema = schemas[name]
                        try:
                            validate(schema['inputSchema'], arguments)
                        except Exception as error:
                            from jsonschema.exceptions import ValidationError
                            raise GatewayError('gateway_arguments_invalid', validation_errors=(
                                argument_validation_details(error) if isinstance(error, ValidationError) else [])) from None
                        from mcp import types
                        declaration = catalog['progressive']
                        item = schema['progressive']
                        metadata = {_PROGRESSIVE: {'version': '1', 'access_view_id': declaration['access_view_id'],
                            'expected_publication_revision': declaration['publication_revision'],
                            'expected_tool_contract_revision': item['tool_contract_revision']}}
                        if context is not None:
                            metadata['gateway/diagnostics'] = context
                        active: Any = getattr(connection, 'session', connection)
                        response = await active.send_request(types.ClientRequest(types.CallToolRequest(
                            params=types.CallToolRequestParams(name=schema['name'], arguments=arguments,
                                _meta=types.RequestParams.Meta.model_validate(metadata)))), types.CallToolResult)
                        value = response.model_dump(mode='json', by_alias=True, exclude_none=True)
                        require_capacity('mcp_frame_bytes', len(encode(value)), 'gateway_result')
                        if not value.get('isError') and 'outputSchema' in schema:
                            try:
                                validate(schema['outputSchema'], value.get('structuredContent'))
                            except Exception:
                                raise GatewayError('gateway_output_invalid') from None
                        return value
            try:
                validate(schema['inputSchema'], arguments)
            except Exception as error:
                from jsonschema.exceptions import ValidationError
                details = argument_validation_details(error) if isinstance(error, ValidationError) else []
                raise GatewayError('gateway_arguments_invalid', validation_errors=details) from None
            async with asyncio.timeout(limits.mcp_tool_seconds):
                async with self.connect() as session:
                    expected_instance = catalog.get('instance', {}).get('instance_id')
                    actual_instance = checked_instance_identity(getattr(session, 'instance_identity', None))
                    if expected_instance and (not actual_instance or actual_instance['instance_id'] != expected_instance):
                        raise GatewayError('gateway_publication_changed')
                    current = await self._catalog(session, tool_name=name)
                    # The caller's whole grant was checked above. Publication
                    # drift matters only for the exact tool being invoked.
                    if current['tools'].get(name) != schema:
                        raise GatewayError('gateway_publication_changed')
                    active_session: Any = getattr(session, 'session', session)
                    response = await active_session.call_tool(schema['name'], arguments=arguments,
                        **({'meta': {'gateway/diagnostics': context}} if context is not None else {}))
                    value = response.model_dump(mode='json', by_alias=True, exclude_none=True)
            require_capacity('mcp_frame_bytes', len(encode(value)), 'gateway_result')
            if not value.get('isError') and 'outputSchema' in schema:
                try:
                    validate(schema['outputSchema'], value.get('structuredContent'))
                except Exception:
                    raise GatewayError('gateway_output_invalid') from None
            return value
        except GatewayError:
            raise
        except CapacityExceeded:
            raise
        except Exception as error:
            raise GatewayError(public_failure(error, 'gateway_call_failed_no_retry')) from None
