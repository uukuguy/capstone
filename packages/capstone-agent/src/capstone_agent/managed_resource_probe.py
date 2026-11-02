"""MCP transport under an isolated UID, with one connection per task/version."""
import asyncio
import json
import os
from pathlib import Path
import shutil
import sys
from .managed_resource_mcp import remote_mcp_session, local_mcp_session, ManagedMcpError


def context(document):
    if document['kind']=='mcp_remote':
        return remote_mcp_session(document['source']['locator'],headers=document.get('protected',{}).get('headers',{}),check_access=lambda:None)
    package=Path(document['package']);runtime=document['runtime'];entry=package/runtime['entrypoint']
    interpreter={'.py':'python3','.mjs':'node','.js':'node','.cjs':'node'}.get(entry.suffix)
    command=shutil.which(interpreter) if interpreter else str(entry)
    if not command:raise ManagedMcpError('resource_runtime_unavailable',stage='launch',executed=False)
    from .managed_resource_dependencies import dependency_environment, runtime_compatibility
    return local_mcp_session(command,([str(entry)] if interpreter else [])+runtime['arguments'],
        cwd=package,environment={**dependency_environment(package,runtime_compatibility()),
            **document.get('protected',{}).get('environment',{})},uid=None,check_access=lambda:None)


async def exchange(session,call):
    if call is not None:
        return await session.call(call['name'],call['arguments'],expected_revision=call['catalog_revision'])
    catalog=await session.discover()
    return {**catalog,'tools':list(catalog['tools'].values())}


def failure(error,*,identifier=None,started=False):
    return {'ok':False,**({'id':identifier} if identifier is not None else {}),
            'error':{'code':error.code if isinstance(error,ManagedMcpError) else 'resource_call_outcome_unknown' if started else 'resource_connection_failed',
                     'stage':error.stage if isinstance(error,ManagedMcpError) else 'execution' if started else 'discovery',
                     'executed':error.executed if isinstance(error,ManagedMcpError) else None if started else False}}


async def invoke(document):
    started=False
    try:
        async with context(document) as session:
            started=document.get('call') is not None
            return {'ok':True,'result':await exchange(session,document.get('call'))}
    except ManagedMcpError as error:return failure(error)
    except Exception as error:return failure(error,started=started)


async def serve(initial):
    message=None
    try:
        line=await asyncio.to_thread(sys.stdin.readline)
        if not line:return
        message=json.loads(line)
        async with context(initial) as session:
            while True:
                try:
                    async with asyncio.timeout(message['timeout_seconds']):
                        result=await exchange(session,message.get('call'))
                    receipt={'ok':True,'id':message['id'],'result':result}
                except Exception as error:
                    receipt=failure(error,identifier=message['id'],started=message.get('call') is not None)
                print(json.dumps(receipt,ensure_ascii=False),flush=True)
                line=await asyncio.to_thread(sys.stdin.readline)
                if not line:return
                message=json.loads(line)
    except Exception as error:
        if message is not None:print(json.dumps(failure(error,identifier=message['id']),ensure_ascii=False),flush=True)


if __name__=='__main__':
    if os.geteuid()<2**31:raise RuntimeError('resource_installer_isolation_required')
    if sys.argv[1]=='--serve':asyncio.run(serve(json.loads(sys.stdin.readline())))
    else:print(json.dumps(asyncio.run(invoke(json.load(sys.stdin))),ensure_ascii=False))
