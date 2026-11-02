"""Generic managed MCP transport. No provider-specific methods or business routing."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from referencing import Registry
from referencing.exceptions import NoSuchResource

from .application_capacity import limits, require_capacity


class ManagedMcpError(ValueError):
    def __init__(self, code: str, *, stage: str, executed: bool | None = False):
        self.code, self.stage, self.executed = code, stage, executed
        super().__init__(code)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def checked_endpoint(url: str) -> str:
    try:
        parsed = urlsplit(url)
        if (not isinstance(url, str) or any(ord(c) < 33 for c in url)
                or parsed.scheme not in {'http', 'https'} or not parsed.hostname
                or parsed.username is not None or parsed.password is not None
                or parsed.query or parsed.fragment or parsed.port == 0):
            raise ValueError()
    except (ValueError, TypeError, AttributeError):
        raise ManagedMcpError('resource_endpoint_invalid', stage='connection') from None
    return url


def published_tool_name(resource_id: str, remote_name: str) -> str:
    """Stable collision-resistant identity; never infer a remote name from a prefix."""
    return 'mcp_' + sha256(_canonical([resource_id, remote_name])).hexdigest()[:40]


class ManagedMcpSession:
    def __init__(self, session, initialized, *, check_access):
        self.session, self.initialized = session, initialized
        self.check_access = check_access
        self.publication = None

    async def discover(self) -> dict:
        self.check_access()
        tools, cursors, cursor = {}, set(), None
        async with asyncio.timeout(limits.mcp_catalog_seconds):
            while True:
                page = await self.session.list_tools(**({'cursor': cursor} if cursor else {}))
                for tool in page.tools:
                    document = tool.model_dump(mode='json', by_alias=True, exclude_none=True)
                    name = document.get('name')
                    if (not isinstance(name, str) or not name or any(ord(c) < 32 for c in name)
                            or name in tools or not isinstance(document.get('inputSchema'), dict)):
                        raise ManagedMcpError('resource_catalog_invalid', stage='discovery')
                    try:
                        Draft202012Validator.check_schema(document['inputSchema'])
                        if 'outputSchema' in document:
                            Draft202012Validator.check_schema(document['outputSchema'])
                    except (ValueError, SchemaError):
                        raise ManagedMcpError('resource_catalog_invalid', stage='discovery') from None
                    tools[name] = document
                require_capacity('mcp_frame_bytes', len(_canonical(tools)), 'resource.discovery')
                cursor = page.nextCursor
                if not cursor:
                    break
                if not isinstance(cursor, str) or cursor in cursors:
                    raise ManagedMcpError('resource_catalog_cursor_invalid', stage='discovery')
                cursors.add(cursor)
        instructions = self.initialized.instructions or ''
        if not isinstance(instructions, str):
            raise ManagedMcpError('resource_catalog_invalid', stage='discovery')
        publication = {'schema': 'capstone-managed-mcp-catalog/1', 'instructions': instructions,
                       'server_info': self.initialized.serverInfo.model_dump(mode='json', exclude_none=True),
                       'tools': tools}
        require_capacity('mcp_frame_bytes', len(_canonical(publication)), 'resource.discovery')
        publication['revision'] = 'sha256:' + sha256(_canonical(publication)).hexdigest()
        self.publication = publication
        return deepcopy(publication)

    async def call(self, name: str, arguments: dict, *, expected_revision: str):
        self.check_access()
        publication = await self.discover()
        if publication['revision'] != expected_revision:
            raise ManagedMcpError('resource_contract_changed', stage='admission')
        if not isinstance(name, str) or name not in publication['tools']:
            raise ManagedMcpError('resource_tool_not_admitted', stage='admission')
        if not isinstance(arguments, dict):
            raise ManagedMcpError('resource_arguments_invalid', stage='admission')
        require_capacity('mcp_frame_bytes', len(_canonical(arguments)), 'resource.arguments')
        def reject_reference(uri):
            raise NoSuchResource(ref=uri)
        validator = Draft202012Validator(publication['tools'][name]['inputSchema'],
                                         registry=Registry(retrieve=reject_reference))
        try:
            validator.validate(arguments)
        except Exception:
            raise ManagedMcpError('resource_arguments_invalid', stage='admission') from None
        self.check_access()
        # Once dispatched, a timeout/disconnect has an unknown effect. Never auto-retry.
        try:
            async with asyncio.timeout(limits.mcp_tool_seconds):
                result = await self.session.call_tool(name, arguments=arguments)
        except Exception:
            raise ManagedMcpError('resource_call_outcome_unknown', stage='execution', executed=None) from None
        document = result.model_dump(mode='json', by_alias=True, exclude_none=True)
        require_capacity('mcp_frame_bytes', len(_canonical(document)), 'resource.result')
        return document


@asynccontextmanager
async def remote_mcp_session(url: str, *, headers: dict[str, str], check_access):
    """Headers come only from protected host bindings, never from a task argument."""
    import httpx
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client
    check_access()
    checked_endpoint(url)
    async with httpx.AsyncClient(headers=headers, timeout=limits.mcp_initialize_seconds,
                                 trust_env=False, follow_redirects=False) as client:
        async with streamable_http_client(url, http_client=client) as (reader, writer, _):
            async with ClientSession(reader, writer) as session:
                async with asyncio.timeout(limits.mcp_initialize_seconds):
                    initialized = await session.initialize()
                yield ManagedMcpSession(session, initialized, check_access=check_access)


@asynccontextmanager
async def local_mcp_session(command: str, arguments: list[str], *, cwd: Path,
                            environment: dict[str, str], uid: int | None, check_access):
    """Host-selected launch. Production children use their isolated execution UID."""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    check_access()
    if not Path(command).is_absolute() or not cwd.is_dir():
        raise ManagedMcpError('resource_runtime_invalid', stage='launch')
    if os.geteuid() == 0 and (type(uid) is not int or uid < 10000):
        raise ManagedMcpError('resource_runtime_isolation_required', stage='launch')
    if uid is not None:
        if type(uid) is not int or uid < 10000:
            raise ManagedMcpError('resource_runtime_isolation_required', stage='launch')
        arguments = [f'--reuid={uid}', f'--regid={uid}', '--clear-groups', '--no-new-privs', command, *arguments]
        command = '/usr/bin/setpriv'
    # Do not copy the host environment. Secret values are individually resolved by the host.
    env = {'PATH': '/usr/local/bin:/usr/bin:/bin', 'HOME': str(cwd),
           'LANG': 'C.UTF-8', 'PYTHONDONTWRITEBYTECODE': '1', **environment}
    parameters = StdioServerParameters(command=command, args=arguments, cwd=str(cwd), env=env)
    with open(os.devnull, 'w') as errors:
        async with stdio_client(parameters, errlog=errors) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                async with asyncio.timeout(limits.mcp_initialize_seconds):
                    initialized = await session.initialize()
                yield ManagedMcpSession(session, initialized, check_access=check_access)
