"""Resolve packaged sources against a freshly checked, thread-scoped gateway publication."""
import json
import re
import zipfile
from hashlib import file_digest
from pathlib import Path


def packaged_capstone_revision(root=Path('/opt/capstone-debug-sources')):
    try:
        entries = json.loads((root / 'manifest.json').read_text())['sources']
        return next(row['revision'] for row in entries if row['repository'] == 'capstone'
                    and re.fullmatch('[0-9a-f]{40}', row['revision']))
    except (OSError, ValueError, KeyError, TypeError, StopIteration):
        return None


def resolve_sources(publication, root=Path('/opt/capstone-debug-sources'), library=Path('/opt/capstone-debug-library')):
    path = root/'manifest.json'
    entries = json.loads(path.read_text())['sources'] if path.is_file() else []
    available = publication.get('available') is True
    instance = publication.get('catalog', {}).get('instance', {}) if available else {}
    revision = instance.get('source_sha256')
    if isinstance(revision,str) and re.fullmatch('[0-9a-f]{64}',revision):
        supplement = library/revision/'manifest.json'
        if supplement.is_file():
            catalog = json.loads(supplement.read_text())
            for item in catalog.get('sources', []):
                if (item.get('repository')=='data-gateway' and item.get('revision')==revision
                        and item.get('archive')==f'data-gateway-{revision}.zip'
                        and (supplement.parent/item['archive']).is_file()):
                    entries = [item]+[entry for entry in entries if (entry['repository'],entry['revision'])!=('data-gateway',revision)]
                    break
    match = next((row for row in entries if row['repository']=='data-gateway'
                  and revision and row['revision']==revision), None)
    return {'instance_id':instance.get('instance_id'), 'gateway_revision':revision,
            'status':('unavailable' if not available else 'unreported' if not revision else
                      'matched' if match else 'source_missing'),
            'selected':match, 'sources':entries}


def read_historical_gateway_source(instance, *, path=None, line=1, prefix='', offset=0,
                                   root=Path('/opt/capstone-debug-sources'),
                                   library=Path('/opt/capstone-debug-library')):
    revision = instance.get('source_sha256')
    if not isinstance(revision, str) or not re.fullmatch('[0-9a-f]{64}', revision):
        raise FileNotFoundError('historical_source_unavailable')
    publication = {'available': True, 'catalog': {'instance': instance}}
    selected = resolve_sources(publication, root, library)['selected']
    if selected is None or selected.get('archive') != f'data-gateway-{revision}.zip':
        raise FileNotFoundError('historical_source_unavailable')
    name = selected['archive']
    return _read_source_archive(selected, (library / revision / name, root / name), path, line, prefix, offset)


def read_historical_capstone_source(revision, *, path=None, line=1, prefix='', offset=0,
                                    root=Path('/opt/capstone-debug-sources'),
                                    library=Path('/opt/capstone-debug-library')):
    if not isinstance(revision, str) or not re.fullmatch('[0-9a-f]{40}', revision):
        raise FileNotFoundError('historical_source_unavailable')
    for directory in (library / revision, root):
        manifest = directory / 'manifest.json'
        if not manifest.is_file():
            continue
        entries = json.loads(manifest.read_text())['sources']
        selected = next((item for item in entries if item.get('repository') == 'capstone'
                         and item.get('revision') == revision and item.get('archive') == 'capstone.zip'), None)
        if selected:
            return _read_source_archive(selected, (directory / 'capstone.zip',), path, line, prefix, offset)
    raise FileNotFoundError('historical_source_unavailable')


def _read_source_archive(selected, candidates, path, line, prefix, offset):
    if type(line) is not int or not 1 <= line <= 100000 or type(offset) is not int or offset < 0:
        raise ValueError('invalid_source_range')
    revision = selected['revision']
    for candidate in candidates:
        if not candidate.is_file():
            continue
        with candidate.open('rb') as stream:
            if file_digest(stream, 'sha256').hexdigest() != selected.get('sha256'):
                continue
            stream.seek(0)
            with zipfile.ZipFile(stream) as archive:
                if path is None:
                    names = sorted(item.filename for item in archive.infolist()
                                   if not item.is_dir() and item.filename != 'release.json'
                                   and item.filename.startswith(prefix))
                    return {'revision': revision, 'files': names[offset:offset + 40],
                            'next_offset': offset + 40 if offset + 40 < len(names) else None}
                if path == 'release.json' or path not in archive.NameToInfo:
                    raise FileNotFoundError('source_path_unavailable')
                with archive.open(path) as source:
                    from itertools import islice
                    lines = [raw[:400].decode('utf-8', errors='replace').rstrip()
                             for raw in islice(source, line - 1, line + 39)]
                    return {'revision': revision, 'path': path, 'first_line': line, 'lines': lines}
    raise FileNotFoundError('historical_source_unavailable')
