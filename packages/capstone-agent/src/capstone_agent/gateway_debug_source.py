"""Read a source archive from one authorized MCP session into private staging."""
import base64
import errno
import hashlib
import json
import re
import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

from pydantic import AnyUrl

from .data_gateway_mcp import GatewayError


BASE = 'gateway://debug-source/v1/'
VERSION = 'gateway-debug-source/1'
CHUNK = 131072
MAX_BYTES = 33554432


async def _read(connection, suffix):
    response = await connection.session.read_resource(AnyUrl(BASE + suffix))
    if len(response.contents) != 1:
        raise ValueError('Invalid source resource')
    item = response.contents[0]
    if str(item.uri) != BASE + suffix or not isinstance(item.text, str) or len(item.text) > CHUNK * 2:
        raise ValueError('Invalid source resource')
    packet = json.loads(item.text)
    if packet.get('status') == 'error':
        code = packet.get('error', {}).get('code')
        if code in ('access_denied', 'version_missing', 'temporarily_unavailable', 'invalid_request'):
            raise GatewayError('debug_source_' + code)
        raise ValueError('Invalid source error')
    return packet


def _verify_archive(path, revision):
    with zipfile.ZipFile(path) as archive:
        names = set()
        for entry in archive.infolist():
            name = entry.filename
            parts = PurePosixPath(name)
            if (entry.compress_type != zipfile.ZIP_STORED or entry.file_size != entry.compress_size
                    or entry.file_size > MAX_BYTES or entry.is_dir() or parts.is_absolute()
                    or '..' in parts.parts or str(parts) != name or chr(92) in name
                    or stat.S_ISLNK(entry.external_attr >> 16) or name in names):
                raise ValueError('Invalid source archive entry')
            names.add(name)
        index = json.loads(archive.read('release.json'))
        files = index['files_sha256']
        if index['source_sha256'] != revision or not files or set(files) != names - {'release.json'}:
            raise ValueError('Invalid source file index')
        for name, digest in files.items():
            with archive.open(name) as stream:
                if hashlib.file_digest(stream, 'sha256').hexdigest() != digest:
                    raise ValueError('Invalid source file checksum')
        return len(files)


async def download_gateway_source(connection, revision, path):
    """Use an exclusive temporary path. Return metadata only after verification."""
    if not isinstance(revision, str) or not re.fullmatch('[a-f0-9]{64}', revision):
        raise ValueError('Invalid source revision')
    if (connection.instance_identity or {}).get('source_sha256') != revision:
        raise GatewayError('debug_source_version_missing')
    declaration = connection.debug_source or {}
    if declaration.get('version') != VERSION:
        raise GatewayError('debug_source_unavailable')
    contract = await _read(connection, 'contract')
    from jsonschema import Draft202012Validator
    defs = contract['$defs']
    Draft202012Validator(defs['Declaration']).validate(declaration)
    manifest = await _read(connection, revision + '/manifest')
    Draft202012Validator(defs['Manifest']).validate(manifest)
    size = manifest['archive_bytes']
    count = manifest['chunk_count']
    if (manifest['source_sha256'] != revision or not 0 < size <= MAX_BYTES
            or manifest['chunk_bytes'] != CHUNK or count != (size + CHUNK - 1) // CHUNK):
        raise ValueError('Invalid source dimensions')
    digest = hashlib.sha256()
    with path.open('xb') as output:
        for index in range(count):
            block = await _read(connection, revision + '/' + str(index))
            Draft202012Validator(defs['Chunk']).validate(block)
            offset = index * CHUNK
            data = base64.b64decode(block['data_base64'], validate=True)
            if (block['source_sha256'] != revision or block['archive_sha256'] != manifest['archive_sha256']
                    or block['index'] != index or block['offset'] != offset or block['eof'] != (index == count - 1)
                    or len(data) != min(CHUNK, size - offset)):
                raise ValueError('Invalid source chunk')
            output.write(data)
            digest.update(data)
    if digest.hexdigest() != manifest['archive_sha256']:
        raise ValueError('Invalid source archive checksum')
    return {'repository': 'data-gateway', 'revision': revision, 'sha256': digest.hexdigest(),
            'entries': _verify_archive(path, revision), 'archive': path.name}

async def cache_gateway_source(connection, library):
    """Publish verified source for the current authorized session by atomic rename."""
    identity = connection.instance_identity or {}
    revision = identity.get('source_sha256')
    if not isinstance(revision, str) or not re.fullmatch('[a-f0-9]{64}', revision):
        raise GatewayError('debug_source_version_missing')
    if (connection.debug_source or {}).get('version') != VERSION:
        raise GatewayError('debug_source_unavailable')
    library.mkdir(parents=True, exist_ok=True)
    destination = library/revision
    filename = f'data-gateway-{revision}.zip'
    def cached():
        manifest = destination/'manifest.json'
        if manifest.is_file():
            for row in json.loads(manifest.read_text())['sources']:
                if (row['repository'] == 'data-gateway' and row['revision'] == revision
                        and row['archive'] == filename and (destination/filename).is_file()):
                    return row
        return None
    existing = cached()
    if existing:
        return existing
    with tempfile.TemporaryDirectory(dir=library) as temporary:
        candidate = Path(temporary)/'verified'
        candidate.mkdir()
        row = await download_gateway_source(connection, revision, candidate/filename)
        (candidate/'manifest.json').write_text(json.dumps({'schema':'capstone-debug-sources/1','sources':[row]}))
        try:
            candidate.rename(destination)
        except OSError as error:
            if error.errno not in (errno.EEXIST, errno.ENOTEMPTY):
                raise
            existing = cached()
            if not existing:
                raise
            return existing
        return row
