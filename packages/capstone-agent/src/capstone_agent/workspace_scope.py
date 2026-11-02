"""Application-owned URL workspace names; these are shared names, not accounts."""

import re
import unicodedata
from urllib.parse import unquote

DEFAULT_WORKSPACE = 'enterprise'
WORKSPACE_HEADER = 'Capstone-Workspace'


def workspace_name(value: str) -> str:
    if not isinstance(value, str) or any(unicodedata.category(c) in {'Cc', 'Cf', 'Cs'} for c in value):
        raise ValueError('invalid workspace name')
    normalized = unicodedata.normalize('NFC', value.strip())
    if not normalized or len(normalized) > 128 or len(normalized.encode('utf-8')) > 512:
        raise ValueError('invalid workspace name')
    return normalized


def workspace_header(value: str | None) -> str:
    if value is None:
        return DEFAULT_WORKSPACE
    if len(value) > 1536 or re.search(r'%(?![0-9a-fA-F]{2})', value):
        raise ValueError('invalid workspace header')
    try:
        return workspace_name(unquote(value, encoding='utf-8', errors='strict'))
    except (UnicodeError, ValueError):
        raise ValueError('invalid workspace header') from None
