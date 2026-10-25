"""Host-owned remote MCP resource. Credentials never cross the task boundary."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator
from referencing import Registry
from referencing.exceptions import NoSuchResource

from .application_capacity import limits, require_capacity, CapacityExceeded


MODEL_TOOLS = frozenset({'discover_network_models', 'inspect_network_model', 'build_network_model',
                        'get_network_model_job', 'get_network_model_artifact', 'read_network_model_artifact'})


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
    pending, seen = [error], set()
    for _ in range(32):
        if not pending:
            break
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        if getattr(getattr(current, 'response', None), 'status_code', None) in {401, 403}:
            return 'gateway_authentication_failed'
        pending.extend(getattr(current, 'exceptions', ()))
        if current.__cause__ is not None:
            pending.append(current.__cause__)
    return fallback


def validate(schema, value):
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema, registry=Registry(retrieve=_deny)).validate(value)


class DataGatewayMcp:
    def __init__(self, connection_path: Path, policy: dict, *, connect=None):
        self.connection_path = Path(connection_path)
        self.policy = deepcopy(policy)
        allowed = policy.get('allowed_tools', [])
        if (set(policy) != {'schema', 'resource_id', 'namespace', 'allowed_tools'}
                or policy['schema'] != 'capstone-data-gateway/1'
                or policy['resource_id'] != 'data-gateway' or policy['namespace'] != 'data_gateway_'
                or not isinstance(allowed, list) or not allowed or len(set(allowed)) != len(allowed)
                or any(not isinstance(n, str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,49}', n)
                       or n in MODEL_TOOLS for n in allowed)):
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
            if (set(connection) != {'transport', 'url', 'headers'}
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

    @asynccontextmanager
    async def _connect(self):
        import httpx
        from mcp import ClientSession
        from mcp.client.streamable_http import streamable_http_client
        async with httpx.AsyncClient(headers=self._connection['headers'], timeout=30,
                                     trust_env=False, follow_redirects=False) as client:
            async with streamable_http_client(self._connection['url'], http_client=client) as (reader, writer, _):
                async with ClientSession(reader, writer) as session:
                    await session.initialize()
                    yield session

    async def _catalog(self, session):
        schemas, cursor = {}, None
        for _ in range(16):
            page = await session.list_tools(**({'cursor': cursor} if cursor else {}))
            for tool in page.tools:
                if tool.name not in self.policy['allowed_tools']:
                    continue
                name = self.policy['namespace'] + tool.name
                if name in schemas:
                    raise GatewayError('gateway_catalog_invalid')
                document = tool.model_dump(mode='json', by_alias=True, exclude_none=True)
                Draft202012Validator.check_schema(document['inputSchema'])
                if 'outputSchema' in document:
                    Draft202012Validator.check_schema(document['outputSchema'])
                schemas[name] = document
            next_cursor = page.nextCursor
            if not next_cursor:
                break
            if next_cursor == cursor:
                raise GatewayError('gateway_catalog_invalid')
            cursor = next_cursor
        else:
            raise GatewayError('gateway_catalog_invalid')
        if not schemas or 'data_gateway_discover_data_capabilities' not in schemas:
            raise GatewayError('gateway_catalog_unavailable')
        value = {'resource_id': self.policy['resource_id'], 'tools': schemas,
                 'tool_hashes': {n: fingerprint(s) for n, s in schemas.items()}}
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

    async def call(self, name, arguments, catalog):
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
                    if await self._catalog(session) != catalog:
                        raise GatewayError('gateway_publication_changed')
                    response = await session.call_tool(schema['name'], arguments=arguments)
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
