"""Exercise protected range delivery through the real native HTTP server."""
import base64
from hashlib import sha256
import http.client
import json
import os
from pathlib import Path
import threading

from capstone_agent.application_capacity import limits
from capstone_agent.general_pi_server import GeneralPiHost, make_server
from capstone_agent.native_resource_references import NativeResourceReferences


def test_protected_http_range_delivery(tmp_path):
    data=b'only selected bytes'
    resource={'schema':'capstone-resource/1','thread_id':'thr_test','resource_id':'resource_'+'a'*32,
        'version':1,'file_name':'large.bin','size_bytes':10000000,'sha256':'b'*64}
    def runner(*args):raise AssertionError('No model is needed for control delivery')
    host=GeneralPiHost(root=tmp_path/'host',identity={'engine':'fixture'},run_task=runner)
    inputs=tmp_path/'inputs';inputs.mkdir()
    port=NativeResourceReferences(tmp_path/'port',inputs,'task',[resource],host.resource_staging,
        os.getuid(),os.getgid(),attempt_id='attempt')
    runner.task_resource_references={'task':port}
    request={'schema':'capstone-resource-range-request/1','request_id':'a'*64,
        'resource_id':resource['resource_id'],'offset':4000,'length':len(data)}
    (port.root/'range-requests'/('a'*64+'.json')).write_text(json.dumps(request))
    assert port.pending_ranges()==[request]
    receipt={'schema':'capstone-resource-read/1','read_id':'read_test','thread_id':'thr_test',
        'attempt_id':'attempt','task_id':'task','request_id':request['request_id'],'resource':resource,
        'offset':request['offset'],'length':len(data),'sha256':sha256(data).hexdigest(),
        'preview':{'bytes_read':len(data),'truncated':False,'status':'text','text':data.decode()}}
    document={'task_id':'task','request':request,'receipt':receipt,
        'content_base64':base64.b64encode(data).decode()}
    server=make_server(host,control_token='fixture-private',address=('127.0.0.1',0))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    def post(value, *, token='fixture-private', claimed_length=None):
        connection=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=2)
        raw=json.dumps(value).encode()
        headers={'Content-Length':str(claimed_length or len(raw))}
        if token:headers['Authorization']='Bearer '+token
        try:
            connection.request('POST','/range-inputs',body=raw,headers=headers)
            response=connection.getresponse()
            return response.status,json.loads(response.read())
        finally:connection.close()
    try:
        assert post(document,token=None)[0]==401
        assert post({**document,'task_id':'foreign'})[0]==400
        assert post(document,claimed_length=limits.resource_read_bytes*2+65537)[0]==400
        assert not list((inputs).iterdir())
        assert post(document)==(200,{'ok':True})
        response=json.loads((port.root/'range-responses'/('a'*64+'.json')).read_text())
        assert response['receipt']==receipt
        assert Path(response['path']).read_bytes()==data
        assert Path(response['path']).stat().st_mode&0o222==0
        assert post(document)==(200,{'ok':True})
        assert post({**document,'content_base64':base64.b64encode(b'x'*len(data)).decode()})[0]==400
        assert list(host.resource_staging.root.iterdir())==[]
    finally:
        server.shutdown();server.server_close();thread.join(2)
