"""Check an exported Debug evidence file without network access."""
import argparse
from hashlib import sha256
from hmac import compare_digest
import json
from pathlib import Path


def verify(document):
    if not isinstance(document, dict) or document.get('schema') != 'capstone-debug-evidence/1':
        raise ValueError('Unsupported debug evidence format')
    integrity = document.get('integrity')
    if not isinstance(integrity, dict) or integrity.get('algorithm') != 'sha256':
        raise ValueError('Missing SHA-256 checksum')
    content = {key: value for key, value in document.items() if key != 'integrity'}
    encoded = json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
    digest = integrity.get('digest')
    if not isinstance(digest, str) or not compare_digest(sha256(encoded.encode()).hexdigest(), digest):
        raise ValueError('Evidence checksum does not match')
    if not all(isinstance(document.get(key), str) and document[key] for key in ('investigation_id', 'thread_id')):
        raise ValueError('Missing investigation identity')
    observation = document.get('observation')
    capstone, gateway = document.get('capstone'), document.get('data_gateway')
    if not isinstance(capstone, dict) or not isinstance(gateway, dict):
        raise ValueError('Both evidence sections must be present')
    events, receipts = capstone.get('events'), gateway.get('events')
    if not isinstance(events, list) or not isinstance(receipts, list):
        raise ValueError('Invalid evidence event lists')
    through = observation.get('through') if isinstance(observation, dict) else 0
    if type(through) is not int or through < 0:
        raise ValueError('Invalid event boundary')
    last = 0
    for event in events:
        seq = event.get('seq') if isinstance(event, dict) else None
        if type(seq) is not int or not last < seq <= through:
            raise ValueError('Event is out of order or outside the investigation scope')
        last = seq
    return {'investigation_id': document['investigation_id'], 'capstone_events': len(events),
            'capstone_truncated': capstone.get('truncated') is True,
            'gateway_status': gateway.get('status'), 'gateway_receipts': len(receipts)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence', type=Path)
    args = parser.parse_args()
    try:
        result = verify(json.loads(args.evidence.read_text(encoding='utf-8')))
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
