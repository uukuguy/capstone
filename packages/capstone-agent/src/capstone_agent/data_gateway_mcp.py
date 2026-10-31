"""Host-owned remote MCP resource. Credentials never cross the task boundary."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator
from referencing import Registry
from referencing.exceptions import NoSuchResource

from .application_capacity import limits, require_capacity, CapacityExceeded


_TOOL_NAME = re.compile(r'[a-z][a-z0-9_]{0,49}')
_INSTRUCTIONS_BYTES = 16384
# Agreed service entry points. Business operations never belong in this list.
_GATEWAY_ENTRY_POINTS = ('discover_gateway', 'describe_gateway_contract')

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

# These failures stop further remote probes in the admitted task. A new user
# instruction gets its own task state and can check the resource again.
TASK_STOP_ERRORS = frozenset({'gateway_timeout', 'gateway_transport_failed',
    'gateway_authentication_failed', 'gateway_endpoint_rejected', 'gateway_connection_failed', 'gateway_call_failed_no_retry',
    'gateway_catalog_invalid', 'gateway_catalog_unavailable'})
_PUBLIC_GATEWAY_ERRORS = TASK_STOP_ERRORS | {'gateway_arguments_invalid', 'gateway_output_invalid',
    'gateway_tool_not_admitted', 'gateway_policy_invalid', 'gateway_connection_config_invalid',
    'gateway_publication_changed'}


class GatewayError(ValueError):
    """A public error code, without upstream exception text."""


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False).encode()


def fingerprint(value):
    return sha256(encode(value)).hexdigest()


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
        async with httpx.AsyncClient(headers=self._connection['headers'], timeout=30,
                                     trust_env=False, follow_redirects=False) as client:
            async with streamable_http_client(self._connection['url'], http_client=client) as (reader, writer, _):
                async with ClientSession(reader, writer) as session:
                    initialized = await session.initialize()
                    experimental = initialized.capabilities.experimental
                    instance = experimental.get('data-gateway/identity') if isinstance(experimental, dict) else None
                    yield InitializedGatewaySession(session, initialized.instructions, initialized.serverInfo.model_dump(), instance)

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

    async def prepare(self):
        try:
            async with asyncio.timeout(min(60, limits.mcp_initialize_seconds + limits.mcp_catalog_seconds)):
                async with self.connect() as session:
                    catalog = await self._catalog(session)
            self._accepted[catalog['revision']] = deepcopy(catalog)
            return deepcopy(catalog)
        except GatewayError:
            raise
        except CapacityExceeded:
            raise
        except Exception as error:
            raise GatewayError(public_failure(error, 'gateway_connection_failed')) from None

    async def call(self, name, arguments, catalog, *, diagnostics=None):
        from .gateway_diagnostics import checked_diagnostics
        context = checked_diagnostics(diagnostics)
        try:
            if (self._accepted.get(catalog.get('revision')) != catalog or name not in catalog['tools']
                    or not isinstance(arguments, dict)):
                raise GatewayError('gateway_tool_not_admitted')
            require_capacity('mcp_frame_bytes', len(encode(arguments)), 'gateway_arguments')
            schema = catalog['tools'][name]
            try:
                validate(schema['inputSchema'], arguments)
            except Exception:
                raise GatewayError('gateway_arguments_invalid') from None
            async with asyncio.timeout(limits.mcp_tool_seconds):
                async with self.connect() as session:
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
