"""Fetch a configured Domain Pack's published tools and relay one call.

The general executor does not import a Domain Pack. Each family worker
publishes its own catalog and executes the call.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen


def _wake_token(operator_token: str) -> str:
    return hmac.new(operator_token.encode(), b'capstone-worker-wake-v1', hashlib.sha256).hexdigest()


def domain_tool_origins(value: str | None = None) -> dict[str, str]:
    configured = os.environ.get('CAPSTONE_DOMAIN_TOOL_ORIGINS', '') if value is None else value
    origins = {}
    for entry in configured.split(','):
        if not entry.strip():
            continue
        family, separator, origin = entry.partition('=')
        parsed = urlsplit(origin)
        if (not separator or not family or family in origins
                or parsed.scheme not in {'http', 'https'} or not parsed.hostname
                or parsed.username or parsed.password or parsed.path not in {'', '/'}
                or parsed.query or parsed.fragment):
            raise ValueError('domain tool origins are invalid')
        origins[family] = origin.rstrip('/')
    return origins


def _request(origin: str, path: str, token: str, *, body: bytes | None = None, timeout: float = 10):
    header = {'Authorization': 'Bearer ' + _wake_token(token)}
    if body is not None:
        header['Content-Type'] = 'application/json'
    request = Request(origin + path, data=body, method='POST' if body is not None else 'GET', headers=header)
    with urlopen(request, timeout=timeout) as response:
        raw = response.read(2 * 1024 * 1024 + 1)
        if len(raw) > 2 * 1024 * 1024:
            raise ValueError('domain tool response exceeds bounds')
        document = json.loads(raw.decode('utf-8'))
    if not isinstance(document, dict):
        raise ValueError('domain tool response is invalid')
    return document


def fetch_domain_catalog(origin: str, token: str, profile: dict):
    """Return one worker catalog, or None when that pack is not published here."""

    query = urlencode({'profile_id': profile['profile_id'], 'profile_version': profile['profile_version']})
    try:
        document = _request(origin, '/domain-tools/catalog?' + query, token)
    except (HTTPError, URLError, TimeoutError, OSError, ValueError):
        return None
    tools = document.get('tools')
    hashes = document.get('tool_hashes')
    if (document.get('schema') != 'capstone-domain-tool-catalog/1'
            or document.get('profile_id') != profile['profile_id']
            or document.get('profile_version') != profile['profile_version']
            or document.get('implementation_family') != profile['implementation_family']
            or not isinstance(tools, dict) or not isinstance(hashes, dict)
            or set(tools) != set(hashes) or not tools):
        return None
    for name, schema in tools.items():
        if (not isinstance(name, str) or not name or len(name) > 128
                or not isinstance(schema, dict) or set(schema) != {'description', 'inputSchema'}
                or not isinstance(schema.get('description'), str) or not schema['description']
                or not isinstance(schema.get('inputSchema'), dict)
                or not isinstance(hashes.get(name), str) or len(hashes[name]) != 64):
            return None
    return {'tools': tools, 'tool_hashes': hashes}


def load_domain_tool_catalogs(grant: dict, *, origins: dict[str, str] | None = None, token: str | None = None):
    """Load published tools for the granted packs. A missing worker omits that pack."""

    selected = origins if origins is not None else domain_tool_origins()
    secret = os.environ.get('CAPSTONE_OPERATOR_TOKEN', '') if token is None else token
    if not secret:
        return {}, {}, []
    tools, hashes, routes, mounted = {}, {}, {}, []
    for profile in grant['profiles']:
        origin = selected.get(profile['implementation_family'])
        if origin is None:
            continue
        catalog = fetch_domain_catalog(origin, secret, profile)
        if catalog is None:
            continue
        mounted.append(profile['profile_id'] + '@' + profile['profile_version'])
        for name, schema in catalog['tools'].items():
            if name in tools:
                continue
            tools[name] = schema
            hashes[name] = catalog['tool_hashes'][name]
            routes[name] = origin
    return {'tools': tools, 'tool_hashes': hashes}, routes, mounted


def invoke_domain_tool(origin: str, token: str, body: dict) -> dict:
    try:
        document = _request(origin, '/domain-tools/invoke', token, body=json.dumps(body).encode(), timeout=180)
    except (HTTPError, URLError, TimeoutError, OSError, ValueError):
        return {'ok': False, 'error': {'message': 'domain tool call failed'}}
    if document.get('ok') is True and isinstance(document.get('result'), dict):
        return document
    if document.get('ok') is False and isinstance(document.get('error'), dict):
        return document
    return {'ok': False, 'error': {'message': 'domain tool call failed'}}
