"""Resolve packaged sources against a freshly checked, thread-scoped gateway publication."""
import json
from pathlib import Path


def resolve_sources(publication, root=Path('/opt/capstone-debug-sources')):
    path = root/'manifest.json'
    entries = json.loads(path.read_text())['sources'] if path.is_file() else []
    available = publication.get('available') is True
    instance = publication.get('catalog', {}).get('instance', {}) if available else {}
    revision = instance.get('source_sha256')
    match = next((row for row in entries if row['repository']=='data-gateway'
                  and revision and row['revision']==revision), None)
    return {'instance_id':instance.get('instance_id'), 'gateway_revision':revision,
            'status':('unavailable' if not available else 'unreported' if not revision else
                      'matched' if match else 'source_missing'),
            'selected':match, 'sources':entries}
