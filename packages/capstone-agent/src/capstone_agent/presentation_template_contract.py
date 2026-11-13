"""Shared application file-processing contract; independent of upload quotas."""
import re
from pathlib import PurePosixPath

CHUNK_BYTES = 1024 * 1024
PROCESSING_BYTES = 32 * 1024 * 1024
EXPANDED_BYTES = 128 * 1024 * 1024
PRESENTATION_LIBRARY_CAPABILITY = {'schema': 'capstone-presentation-library/1', 'tool': 'agent_presentations'}


def checked_template_reference(value):
    if (not isinstance(value, dict) or set(value) != {'template_id', 'version', 'sha256'}
            or not isinstance(value['template_id'], str)
            or not re.fullmatch(r'(?:state-grid|tpl_[a-f0-9]{32})', value['template_id'])
            or not isinstance(value['sha256'], str) or not re.fullmatch(r'[a-f0-9]{64}', value['sha256'])
            or value['version'] != 'sha256:' + value['sha256']):
        raise ValueError('template_identity_changed')
    return dict(value)


def checked_template_descriptor(value):
    fields = {'schema', 'template_id', 'version', 'sha256', 'size_bytes', 'file_name', 'name', 'scope'}
    if (not isinstance(value, dict) or set(value) != fields
            or value.get('schema') != 'capstone-presentation-template/1'
            or type(value.get('size_bytes')) is not int or not 0 < value['size_bytes'] <= PROCESSING_BYTES
            or value.get('scope') not in {'builtin', 'session', 'library'}
            or not isinstance(value.get('file_name'), str) or len(value['file_name']) > 255
            or PurePosixPath(value['file_name']).name != value['file_name'] or '\\' in value['file_name']
            or not isinstance(value.get('name'), str) or not 0 < len(value['name']) <= 160):
        raise ValueError('template_identity_changed')
    checked_template_reference({k: value[k] for k in ('template_id', 'version', 'sha256')})
    return dict(value)
