import sys,time
from pathlib import Path
import pytest
from capstone_agent.managed_resource_session import ManagedResourceSession
from capstone_agent.managed_resource_mcp import ManagedMcpError


def test_session_keeps_server_state_across_calls_and_closes(tmp_path):
    program='''import json,sys
initial=json.loads(sys.stdin.readline());count=0
for line in sys.stdin:
 message=json.loads(line);count+=1
 print(json.dumps({'ok':True,'id':message['id'],'result':{'count':count}}),flush=True)
'''
    cleaned=[]
    session=ManagedResourceSession([sys.executable,'-u','-c',program],cwd=tmp_path,environment={},initial={},cleanup=lambda:cleaned.append(True))
    try:
        assert session.exchange(None,deadline=time.monotonic()+2)=={'count':1}
        assert session.exchange({'name':'second'},deadline=time.monotonic()+2)=={'count':2}
    finally:session.close()
    assert cleaned==[True]
    assert session.process.poll() is not None
    with pytest.raises(ManagedMcpError,match='closed'):session.exchange(None,deadline=time.monotonic()+1)


def test_broken_call_is_unknown_and_not_replayed(tmp_path):
    program='''import sys
sys.stdin.readline();sys.stdin.readline();sys.exit(1)
'''
    session=ManagedResourceSession([sys.executable,'-u','-c',program],cwd=tmp_path,environment={},initial={},cleanup=lambda:None)
    try:
        with pytest.raises(ManagedMcpError) as caught:session.exchange({'name':'one'},deadline=time.monotonic()+2)
        assert caught.value.executed is None
        assert caught.value.code=='resource_call_outcome_unknown'
        assert session.closed
    finally:session.close()
