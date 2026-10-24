"""Versioned input resource identity, independent of model context size."""
from pathlib import PurePosixPath
import re

from .application_capacity import limits


def checked_resource(value):
    if not isinstance(value, dict):
        raise ValueError('invalid resource manifest')
    required = {'schema', 'resource_id', 'version', 'thread_id', 'file_name', 'size_bytes', 'sha256'}
    if (not required <= value.keys() or value['schema'] != 'capstone-resource/1'
            or not isinstance(value['resource_id'], str)
            or not re.fullmatch(r'resource_[a-f0-9]{32}', value['resource_id'])
            or type(value['version']) is not int or value['version'] != 1
            or not isinstance(value['thread_id'], str)
            or not re.fullmatch(r'[a-z][a-z0-9_-]{0,63}', value['thread_id'])
            or type(value['size_bytes']) is not int or value['size_bytes'] <= 0
            or not isinstance(value['sha256'], str) or not re.fullmatch(r'[a-f0-9]{64}', value['sha256'])
            or not isinstance(value['file_name'], str) or not value['file_name']
            or len(value['file_name'].encode()) > 255
            or PurePosixPath(value['file_name']).name != value['file_name']
            or '\\' in value['file_name'] or any(ord(c) < 32 or ord(c) == 127 for c in value['file_name'])):
        raise ValueError('invalid resource manifest')
    return {key: value[key] for key in sorted(required)}
