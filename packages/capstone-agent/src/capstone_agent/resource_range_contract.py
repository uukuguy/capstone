"""Portable exact resource-read receipt contract. No service or storage access."""
from hashlib import sha256
import re


class ResourceRangeRejected(ValueError):
    """An ordinary range tool rejection that need not fail its parent task."""
    def __init__(self, message, code='resource_range_rejected'):
        super().__init__(message)
        self.code = code


class ResourceRangePersistenceError(RuntimeError):
    """Required retained bytes are missing, corrupt, or cannot be saved."""


def preview_for(content, preview_bytes):
    sample=content[:preview_bytes]
    status,text='text',None
    try:
        text=sample.decode('utf-8')
        if '\x00' in text:
            status,text='binary',None
    except UnicodeDecodeError:
        status='invalid-UTF8'
    return dict(bytes_read=len(sample),truncated=len(sample)<len(content),status=status,text=text)


def checked_receipt(receipt, content, *, preview_bytes):
    fields={'schema','read_id','thread_id','attempt_id','task_id','request_id','resource','offset','length','sha256','preview'}
    if (not isinstance(receipt,dict) or set(receipt)!=fields
            or receipt['schema']!='capstone-resource-read/1'
            or not isinstance(receipt['read_id'],str) or not re.fullmatch(r'read_[a-f0-9]{32}',receipt['read_id'])
            or any(not isinstance(receipt[k],str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,128}',receipt[k]) for k in ('thread_id','attempt_id','task_id'))
            or not isinstance(receipt['request_id'],str) or not re.fullmatch(r'[a-f0-9]{64}',receipt['request_id'])
            or type(receipt['offset']) is not int or receipt['offset']<0
            or type(receipt['length']) is not int or receipt['length']!=len(content) or not content
            or receipt['sha256']!=sha256(content).hexdigest()
            or not isinstance(receipt['preview'],dict)
            or type(receipt['preview'].get('bytes_read')) is not int
            or type(receipt['preview'].get('truncated')) is not bool
            or receipt['preview']!=preview_for(content,preview_bytes)):
        raise ValueError('invalid resource range receipt')
    from .resource_manifest import checked_resource
    resource=checked_resource(receipt['resource'])
    if (resource!=receipt['resource'] or resource['thread_id']!=receipt['thread_id']
            or receipt['offset']+receipt['length']>resource['size_bytes']):
        raise ValueError('invalid resource range receipt source')
    return receipt
