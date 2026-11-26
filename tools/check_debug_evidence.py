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
    steps = diagnosis.get('progress', [])
    if not isinstance(steps, list):
        raise ValueError('Invalid diagnosis timeline')
    last_step = 0
    for step in steps:
        required = {'seq', 'stage', 'tool'}
        if (not isinstance(step, dict) or not required <= step.keys() <= required | {'operation', 'call_seq', 'elapsed_ms'}
                or type(step['seq']) is not int or step['seq'] <= last_step
                or step['stage'] not in ('tool_started', 'tool_finished', 'tool_failed')
                or not isinstance(step['tool'], str)
                or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,127}', step['tool'])):
            raise ValueError('Invalid diagnosis timeline step')
        if 'operation' in step and (step['tool'] != 'agent_debug_observe' or not isinstance(step['operation'], str)
                                    or not re.fullmatch(r'[a-z_]{1,32}', step['operation'])):
            raise ValueError('Invalid diagnosis tool operation')
        if 'call_seq' in step and (type(step['call_seq']) is not int or not 0 < step['call_seq'] < step['seq']):
            raise ValueError('Invalid diagnosis call sequence')
        if 'elapsed_ms' in step and (type(step['elapsed_ms']) is not int or step['elapsed_ms'] < 0):
            raise ValueError('Invalid diagnosis step duration')
        last_step = step['seq']
    cited = diagnosis.get('evidence_event_seqs', [])
    if not isinstance(cited, list) or any(type(seq) is not int or not 0 < seq <= through for seq in cited):
        raise ValueError('Diagnosis cites events outside the investigation scope')
    refs = diagnosis.get('finding_event_seqs', [])
    if not isinstance(refs, list) or any(type(seq) is not int or seq not in cited for seq in refs):
        raise ValueError('Finding cites events outside its supplied evidence')
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
    review = document.get('reviewed_export')
    if review is not None and (not isinstance(review, dict) or not (
            review == {'status': 'not_approved'} or
            set(review) == {'status', 'diagnosis_markdown', 'reproduction'} and review['status'] == 'approved'
            and isinstance(review['diagnosis_markdown'], str) and review['diagnosis_markdown'].strip()
            and isinstance(review['reproduction'], dict))):
        raise ValueError('Invalid reviewed Debug export')
    return {'investigation_id': document['investigation_id'], 'capstone_events': len(events),
            'capstone_truncated': capstone.get('truncated') is True,
            'diagnosis_events_missing_from_export': missing,
            'capstone_diagnosis_events': len(steps),
            'capstone_diagnosis_truncated': diagnosis.get('progress_truncated') is True,
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
    write('capstone-diagnosis-events.jsonl', b''.join(encode(row) for row in diagnosis.get('progress', [])))
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
             f"- Capstone 普通执行事件数：{summary['capstone_events']}",
             f"- Capstone 诊断步骤数：{summary['capstone_diagnosis_events']}",
             f"- 网关导出状态：`{identifier(summary['gateway_status'])}`",
             f"- 网关获准回执数：{summary['gateway_receipts']}",
             '- 跨侧请求关联：待核验。导出范围为时间线及获准回执字段。']
    if failure:
        lines.append(f"- 首条公开异常：事件 #{failure['seq']}（`{identifier(failure['type'])}`）。")
    elif observation:
        lines.append('- 在调查范围内未记录公开异常。')
    if (summary['capstone_truncated'] or summary['capstone_diagnosis_truncated']
            or gateway.get('truncated') is True):
        lines.append('- 证据已裁剪。完整覆盖需在现场核对。')
    lines += ['', '复验时比较首条异常与获准网关回执状态。结合证据范围判断差异。']
    review = document.get('reviewed_export', {})
    if review.get('status') == 'approved':
        lines += ['', '## 已核准的诊断结论', '', review['diagnosis_markdown']]
        (root / 'repro').mkdir(mode=0o700)
        write('repro/input.json', encode(review['reproduction']))
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
