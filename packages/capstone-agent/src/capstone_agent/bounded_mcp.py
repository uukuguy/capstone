"""Fixed prepared MCP transport. Observations are external task data."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path
import sys

from jsonschema import Draft202012Validator
from referencing import Registry
from referencing.exceptions import NoSuchResource

from .runtime_resources import content_hash, safe_path
from .resource_installation import private_environment, verify_source_tree

MAX_BYTES = 128 * 1024


def _deny(uri):
    raise NoSuchResource(ref=uri)


def validate_arguments(name, arguments, schemas, hashes):
    if name not in schemas or content_hash(schemas[name]) != hashes.get(name):
        raise ValueError('MCP tool identity changed')
    if not isinstance(arguments, dict) or len(json.dumps(arguments, allow_nan=False).encode()) > MAX_BYTES:
        raise ValueError('MCP arguments exceed bounds')
    try:
        schema = schemas[name]['inputSchema']
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema, registry=Registry(retrieve=_deny)).validate(arguments)
    except Exception:
        raise ValueError('MCP arguments do not match the local schema') from None


async def serve(config: dict):
    # The host selects this immutable config. Native tool parameters cannot
    # select the executable, descriptor, server or transport.
    from mcp import ClientSession, StdioServerParameters  # pyright: ignore[reportMissingImports]
    from mcp.client.stdio import stdio_client  # pyright: ignore[reportMissingImports]
    config = config['mcp']
    install, work = Path(config['install']), Path(config['workspace'])
    descriptor = config['descriptor']
    if content_hash(descriptor) != config['descriptor_sha256']:
        raise ValueError('accepted descriptor changed')
    if descriptor['server'] != 'sources/PowerMCP/pandapower/panda_mcp.py':
        raise ValueError('MCP server changed')
    verify_source_tree(install, descriptor['source_files'])
    interpreter = install / 'venv/bin/python'
    if hashlib.sha256(interpreter.resolve().read_bytes()).hexdigest() != descriptor['runtime_identity']['base_interpreter_sha256']:
        raise ValueError('MCP interpreter changed')
    env = private_environment(work / '.mcp')
    env['POWERIO_MCP_ALLOWED_ROOTS'] = os.pathsep.join((str(work), config['input_root']))
    parameters = StdioServerParameters(command=str(interpreter),
        args=[str(safe_path(install, descriptor['server']))], cwd=str(work), env=env)
    async with stdio_client(parameters) as streams:
        async with ClientSession(*streams) as session:
            await asyncio.wait_for(session.initialize(), 60)
            listing = await asyncio.wait_for(session.list_tools(), 30)
            schemas = {tool.name: tool.model_dump(mode='json', by_alias=True, exclude_none=True) for tool in listing.tools}
            if schemas != descriptor['tool_schemas'] or {name: content_hash(schema) for name, schema in schemas.items()} != descriptor['tool_schema_hashes']:
                raise ValueError('MCP publication changed')
            print(json.dumps({'type': 'mcp_ready', 'tool_schema_hashes': descriptor['tool_schema_hashes']}), flush=True)
            calls = 0
            while line := await asyncio.to_thread(sys.stdin.buffer.readline, MAX_BYTES + 1):
                calls += 1
                if calls > 32:
                    raise ValueError('MCP call limit exceeded')
                if len(line) > MAX_BYTES:
                    raise ValueError('MCP frame exceeds bounds')
                request = json.loads(line)
                name, arguments = request['name'], request['arguments']
                try:
                    validate_arguments(name, arguments, schemas, descriptor['tool_schema_hashes'])
                except ValueError:
                    print(json.dumps({'error': 'invalid_tool_arguments'}), flush=True)
                    continue
                # A timeout ends this connection. Never retry a possible mutation.
                try:
                    result = await asyncio.wait_for(session.call_tool(name, arguments=arguments), 30)
                except BaseException:
                    print(json.dumps({'error': 'tool_outcome_unknown_no_retry'}), flush=True)
                    raise
                value = result.model_dump(mode='json', by_alias=True, exclude_none=True)
                body = json.dumps(value, allow_nan=False).encode()
                if len(body) > MAX_BYTES:
                    raise ValueError('MCP result exceeds bounds; outcome unknown')
                if 'outputSchema' in schemas[name] and result.structured_content is not None:
                    try:
                        Draft202012Validator(schemas[name]['outputSchema'], registry=Registry(retrieve=_deny)).validate(result.structured_content)
                    except Exception:
                        raise ValueError('MCP output schema failed; outcome unknown') from None
                frame = json.dumps({'result_json': body.decode(), 'is_error': result.is_error, 'observation': {
                    'kind': 'external_mcp_observation', 'task_id': config['task_id'],
                    'parent_attempt_id': config['parent_attempt_id'],
                    'descriptor_sha256': config['descriptor_sha256'], 'tool': name,
                    'tool_schema_sha256': descriptor['tool_schema_hashes'][name],
                    'output_sha256': hashlib.sha256(body).hexdigest()}})
                if len(frame.encode()) > MAX_BYTES:
                    raise ValueError('MCP result envelope exceeds bounds; outcome unknown')
                print(frame, flush=True)


def main():
    try:
        asyncio.run(serve(json.loads(Path(sys.argv[1]).read_text())))
    except BaseException:
        # No raw server error, file content or environment enters public output.
        print(json.dumps({'error': 'mcp_connection_failed_no_retry'}), flush=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
