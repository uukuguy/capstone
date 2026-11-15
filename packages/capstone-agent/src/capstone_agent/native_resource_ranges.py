"""Bounded application-native range transport validation."""
import base64
from hashlib import sha256
import re
from .application_capacity import limits
from .resource_manifest import checked_resource

def checked_request(value, resources):
    if not isinstance(value,dict) or set(value)!={'schema','request_id','resource_id','offset','length'}:
        raise ValueError('invalid range request')
    if value['schema']!='capstone-resource-range-request/1' or not isinstance(value['request_id'],str) or not re.fullmatch('[a-f0-9]{64}',value['request_id']):
        raise ValueError('invalid range identity')
    resource=resources.get(value['resource_id'])
    offset,length=value['offset'],value['length']
    if resource is None or type(offset) is not int or type(length) is not int or offset<0 or not 0<length<=limits.resource_read_bytes or offset+length>resource['size_bytes']:
        raise ValueError('invalid range bounds')
    return dict(value)

def checked_reply(document,request,resource,task_id):
    receipt=document['receipt']
    if not isinstance(receipt,dict) or set(receipt)!={'schema','read_id','thread_id','attempt_id','task_id','request_id','resource','offset','length','sha256','preview'}:
        raise ValueError('invalid range receipt')
    if (receipt['schema']!='capstone-resource-read/1' or receipt['task_id']!=task_id or
        receipt['thread_id']!=resource['thread_id'] or checked_resource(receipt['resource'])!=resource or
        any(type(receipt[key]) is not int for key in ('offset','length')) or
        any(receipt[key]!=request[key] for key in ('request_id','offset','length')) or
        not all(isinstance(receipt[key],str) and receipt[key] for key in ('read_id','attempt_id'))):
        raise ValueError('range receipt identity changed')
    encoded=document['content_base64']
    if not isinstance(encoded,str) or len(encoded)>4*((request['length']+2)//3):raise ValueError('range content exceeds bounds')
    data=base64.b64decode(encoded,validate=True)
    if len(data)!=request['length'] or sha256(data).hexdigest()!=receipt['sha256']:raise ValueError('range content changed')
    if not re.fullmatch(r'read_[a-f0-9]{32}',receipt['read_id']):raise ValueError('invalid range read identity')
    sample=data[:limits.resource_read_preview_bytes]
    status,text='text',None
    try:
        text=sample.decode('utf-8')
        if '\x00' in text:status,text='binary',None
    except UnicodeDecodeError:status='invalid-UTF8'
    expected={'bytes_read':len(sample),'truncated':len(sample)<len(data),'status':status,'text':text}
    preview=receipt['preview']
    if (not isinstance(preview,dict) or preview!=expected or
        type(preview.get('bytes_read')) is not int or type(preview.get('truncated')) is not bool):
        raise ValueError('range preview changed')
    return receipt,data
