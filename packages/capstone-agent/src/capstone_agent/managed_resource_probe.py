"""MCP discovery and calls behind installer UID and kernel egress enforcement."""
import asyncio
import json
import os
from pathlib import Path
import shutil
import sys
from .managed_resource_mcp import remote_mcp_session, local_mcp_session, ManagedMcpError


async def exchange(context,call=None):
    async with context as session:
        catalog=await session.discover()
        if call is not None:
            return await session.call(call['name'],call['arguments'],expected_revision=call['catalog_revision'])
        return {**catalog,'tools':list(catalog['tools'].values())}


async def probe(url):
    return await exchange(remote_mcp_session(url,headers={},check_access=lambda:None))


async def invoke(document):
    if document['kind']=='mcp_remote':
        context=remote_mcp_session(document['source']['locator'],headers={},check_access=lambda:None)
    else:
        package=Path(document['package']);runtime=document['runtime'];entry=package/runtime['entrypoint']
        interpreter={'.py':'python3','.mjs':'node','.js':'node','.cjs':'node'}.get(entry.suffix)
        command=shutil.which(interpreter) if interpreter else str(entry)
        if not command:raise ValueError('resource_runtime_unavailable')
        context=local_mcp_session(command,([str(entry)] if interpreter else [])+runtime['arguments'],
            cwd=package,environment={},uid=None,check_access=lambda:None)
    return await exchange(context,document.get('call'))


if __name__=='__main__':
    if os.geteuid()<2**31:raise RuntimeError('resource_installer_isolation_required')
    try:
        value=asyncio.run(invoke(json.load(sys.stdin))) if sys.argv[1]=='--invoke' else asyncio.run(probe(sys.argv[1]))
        print(json.dumps({'ok':True,'result':value}))
    except ManagedMcpError as error:
        print(json.dumps({'ok':False,'error':{'code':str(error),'stage':error.stage,'executed':error.executed}}))
