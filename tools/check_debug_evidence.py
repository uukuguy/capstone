"""Check an exported Debug evidence file without network access."""
import argparse
from hashlib import sha256
from hmac import compare_digest
import json
from pathlib import Path
import re
import tempfile


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
    snapshot_id = document.get('snapshot_id')
    if snapshot_id is not None:
        snapshot = {key: content.get(key) for key in ('schema', 'thread_id', 'investigation_id',
                                                      'observation', 'diagnosis', 'capstone')}
        encoded = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
        if not isinstance(snapshot_id, str) or not compare_digest(sha256(encoded.encode()).hexdigest(), snapshot_id):
            raise ValueError('Diagnostic snapshot checksum does not match')
    if not all(isinstance(document.get(key), str) and document[key] for key in ('investigation_id', 'thread_id')):
        raise ValueError('Missing investigation identity')
    observation = document.get('observation')
    capstone, gateway = document.get('capstone'), document.get('data_gateway')
    if not isinstance(capstone, dict) or not isinstance(gateway, dict):
        raise ValueError('Both evidence sections must be present')
    events, receipts = capstone.get('events'), gateway.get('events')
    if not isinstance(events, list) or not isinstance(receipts, list) or any(not isinstance(row, dict) for row in receipts):
        raise ValueError('Invalid evidence event lists')
    through = observation.get('through') if isinstance(observation, dict) else 0
    if type(through) is not int or through < 0:
        raise ValueError('Invalid event boundary')
    last = 0
    event_seqs = set()
    for event in events:
        seq = event.get('seq') if isinstance(event, dict) else None
        if type(seq) is not int or not last < seq <= through:
            raise ValueError('Event is out of order or outside the investigation scope')
        last = seq
        event_seqs.add(seq)
    failure = observation.get('first_failure') if isinstance(observation, dict) else None
    if failure is not None:
        if (not isinstance(failure, dict) or type(failure.get('seq')) is not int
                or not 0 < failure['seq'] <= through or not isinstance(failure.get('type'), str)):
            raise ValueError('First failure is outside the investigation scope')
        if failure['seq'] not in event_seqs and capstone.get('truncated') is not True:
            raise ValueError('First failure is missing from a complete timeline')
    diagnosis = document.get('diagnosis', {})
    if not isinstance(diagnosis, dict):
        raise ValueError('Invalid diagnosis record')
    cited = diagnosis.get('evidence_event_seqs', [])
    if not isinstance(cited, list) or any(type(seq) is not int or not 0 < seq <= through for seq in cited):
        raise ValueError('Diagnosis cites events outside the investigation scope')
    missing = sorted(set(cited) - event_seqs)
    if missing and capstone.get('truncated') is not True:
        raise ValueError('Diagnosis cites missing events in a complete timeline')
    prior = document.get('previous_gateway_evidence')
    if prior is not None:
        if (not isinstance(prior, dict) or not isinstance(prior.get('events'), list)
                or not isinstance(observation, dict) or not prior.get('investigation_id')
                or prior['investigation_id'] != observation.get('previous_investigation_id')
                or prior['investigation_id'] != diagnosis.get('gateway_investigation_id')):
            raise ValueError('Prior gateway evidence is outside the diagnosis scope')
    return {'investigation_id': document['investigation_id'], 'capstone_events': len(events),
            'capstone_truncated': capstone.get('truncated') is True,
            'diagnosis_events_missing_from_export': missing,
            'gateway_status': gateway.get('status'), 'gateway_receipts': len(receipts),
            'previous_gateway_receipts': len(prior['events']) if prior is not None else 0}


def import_evidence(document, parent):
    summary = verify(document)
    root = Path(tempfile.mkdtemp(prefix='capstone-debug-', dir=parent))
    members = {}

    def write(name, value):
        with (root / name).open('xb') as stream:
            stream.write(value)
        members[name] = sha256(value).hexdigest()

    def encode(value):
        return (json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False) + '\n').encode('utf-8')

    capstone = document['capstone']
    gateway = document['data_gateway']
    observation = document.get('observation') or {}
    diagnosis = document.get('diagnosis') or {}
    failure = observation.get('first_failure')
    write('evidence.json', encode(document))
    write('capstone-events.jsonl', b''.join(encode(row) for row in capstone['events']))
    write('gateway-events.jsonl', b''.join(encode(row) for row in gateway['events']))
    prior = document.get('previous_gateway_evidence')
    if prior is not None:
        write('previous-gateway-events.jsonl', b''.join(encode(row) for row in prior['events']))
    correlation = {'schema': 'capstone-debug-offline-correlation/1',
                   'investigation_id': document['investigation_id'],
                   'attempt_id': observation.get('attempt_id'),
                   'through': observation.get('through'),
                   'gateway_investigation_id': diagnosis.get('gateway_investigation_id'),
                   'gateway_export_status': gateway.get('status'),
                   'request_correlation': {'status': 'unverified', 'links': []}}
    write('correlation.json', encode(correlation))

    def identifier(value):
        return value if isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_.:-]{1,128}', value) else '未记录'

    lines = ['# Debug 证据摘要', '',
             f"- 调查 ID：`{identifier(document['investigation_id'])}`",
             f"- Capstone 事件数：{summary['capstone_events']}",
             f"- 网关导出状态：`{identifier(summary['gateway_status'])}`",
             f"- 网关获准回执数：{summary['gateway_receipts']}",
             '- 跨侧请求关联：待核验。导出范围为时间线及获准回执字段。']
    if failure:
        lines.append(f"- 首条公开异常：事件 #{failure['seq']}（`{identifier(failure['type'])}`）。")
    elif observation:
        lines.append('- 在调查范围内未记录公开异常。')
    if summary['capstone_truncated'] or gateway.get('truncated') is True:
        lines.append('- 证据已裁剪。完整覆盖需在现场核对。')
    lines += ['', '复验时比较首条异常与获准网关回执状态。结合证据范围判断差异。']
    write('diagnosis.md', ('\n'.join(lines) + '\n').encode('utf-8'))
    manifest = {'schema': 'capstone-debug-offline-import/1',
                'evidence_sha256': document['integrity']['digest'],
                'snapshot_id': document.get('snapshot_id'),
                'thread_id': document['thread_id'], 'observation': document.get('observation'),
                'source_evidence': document.get('diagnosis', {}).get('source_evidence', {}),
                'gateway_scope': gateway.get('scope'), 'summary': summary, 'files_sha256': members}
    (root / 'manifest.json').write_bytes(encode(manifest))
    return root


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence', type=Path)
    parser.add_argument('--import-to', type=Path, metavar='DIRECTORY',
                        help='Create a private replay directory inside an existing directory')
    args = parser.parse_args()
    try:
        document = json.loads(args.evidence.read_text(encoding='utf-8'))
        result = verify(document)
        if args.import_to is not None:
            result['import_directory'] = str(import_evidence(document, args.import_to))
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
